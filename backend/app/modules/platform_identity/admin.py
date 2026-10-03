"""Platform user administration (T01-07; locked decisions D7-2 … D7-5, D6-3).

Every operation authorizes the caller first (``authorize``: permission and,
for the D6-5/D7-4 permissions, a fresh step-up), then works in an
**administration target transaction** (``lookup.admin_target_transaction``)
that opens exactly one platform user to Row-Level Security (D7-2). The
directory itself (users and roles) is readable by any platform principal.

* **Create** (D7-3): a new user is ``INVITED`` with roles and no credential;
  a single-use invitation (HMAC, 7 days) is emailed after commit. The first
  sign-in after acceptance requires MFA enrolment (D6-1, D6-4).
* **Update**: display name and roles, optimistic ``version``.
* **Suspend / reactivate** (D7-4): reason and ``version``; suspension revokes
  the user's sessions and open invitations in the same transaction;
  reactivation never touches MFA.
* **Self-protection** (D7-5): no suspension, role change or MFA reset of one's
  own account; the last active guardian (Super Admin) is never suspended or demoted
  (serialised by a transaction advisory lock).
* **Invitation acceptance**: public, generic ``404`` for every unusable token.

Administrative changes are audited in their own transaction (ADR-0013 §4).
Nothing returned, logged or audited contains a token, password or hash.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import NoReturn

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditTarget, record_security_event, write_audit_event
from app.core.authz import authorize
from app.core.context import RequestContext, current_context
from app.core.db.session import context_transaction
from app.core.errors import (
    ConflictError,
    ErrorDetail,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from app.core.pagination import SortField
from app.integrations.email import EmailMessage
from app.modules.identity.domain import (
    PASSWORD_MESSAGES,
    InvalidEmailError,
    mask_email,
    normalize_email,
    password_problem,
)
from app.modules.identity.passwords import common_passwords
from app.modules.identity.tokens import TokenPurpose, is_well_formed, new_token
from app.modules.platform_identity import admin_repository as admin_repo
from app.modules.platform_identity import events
from app.modules.platform_identity import repository as repo
from app.modules.platform_identity.domain import (
    PLATFORM_INVITATION_TTL,
    PlatformSessionRevokeReason,
    PlatformUserStatus,
    clean_display_name,
    clean_reason,
    reactivated_status,
)
from app.modules.platform_identity.lookup import (
    PlatformLookupKey,
    admin_target_transaction,
    platform_lookup_transaction,
)
from app.modules.platform_identity.permissions import (
    PLATFORM_USER_CREATE,
    PLATFORM_USER_REACTIVATE,
    PLATFORM_USER_READ,
    PLATFORM_USER_SUSPEND,
    PLATFORM_USER_UPDATE,
)
from app.modules.platform_identity.roles import GUARDIAN_ROLE, PlatformRole
from app.modules.platform_identity.service import (
    MfaResetResult,
    PlatformIdentityService,
    PlatformRequestInfo,
)
from app.modules.platform_identity.templates import (
    platform_invitation_email,
    platform_invitation_link,
)

AdminUser = admin_repo.AdminUserRow


@dataclass(frozen=True, slots=True)
class UserPage:
    items: list[AdminUser]
    total: int


@dataclass(frozen=True, slots=True)
class CreatedUser:
    user: AdminUser
    email: EmailMessage


@dataclass(frozen=True, slots=True)
class InvitationPreview:
    email: str
    """Masked: the invitee recognises it; a token holder learns nothing more."""


def _invalid(field: str, code: str, message: str) -> ValidationFailedError:
    return ValidationFailedError(details=[ErrorDetail(field=field, code=code, message=message)])


def _reason(reason: str) -> str:
    cleaned = clean_reason(reason)
    if cleaned is None:
        raise _invalid("reason", "reason_required", "Give a reason of up to 500 characters.")
    return cleaned


def _display_name(name: str) -> str:
    cleaned = clean_display_name(name)
    if cleaned is None:
        raise _invalid("display_name", "invalid", "Enter a name of up to 200 characters.")
    return cleaned


def _roles(roles: Sequence[PlatformRole]) -> frozenset[PlatformRole]:
    if not roles:
        raise _invalid("roles", "required", "Choose at least one role.")
    return frozenset(roles)


def _stale() -> NoReturn:
    raise ConflictError("This platform user was changed by someone else. Reload and try again.")


class PlatformUserAdmin:
    """Platform user administration on top of the platform identity service."""

    def __init__(self, identity: PlatformIdentityService) -> None:
        self.identity = identity

    def _refuse_self(self, context: RequestContext, target: uuid.UUID, action: str) -> None:
        if context.principal_id == target:
            record_security_event(
                events.SELF_ACTION_REFUSED,
                target=AuditTarget("platform_user", target),
                metadata={"action": action},
            )
            raise PermissionDeniedError()

    async def _target(self, db: AsyncSession, user_id: uuid.UUID) -> AdminUser:
        found = await admin_repo.user(db, user_id)
        if found is None:
            raise NotFoundError()
        return found

    async def _keep_a_super_admin(self, db: AsyncSession, target: AdminUser) -> None:
        """D7-5: refuse to leave the platform without an active guardian role holder."""
        if GUARDIAN_ROLE not in target.roles:
            return
        await admin_repo.lock_guardians(db)
        if await admin_repo.active_guardians(db, excluding=target.id) == 0:
            raise ConflictError("The platform must keep at least one active Super Admin.")

    def _invitation(self, to: str, display_name: str) -> tuple[str, EmailMessage]:
        token = new_token()
        message = platform_invitation_email(
            to=to,
            display_name=display_name,
            link=platform_invitation_link(self.identity.config.app_base_url, token),
        )
        return self.identity.hash_token(TokenPurpose.PLATFORM_INVITATION, token), message

    # --- directory ----------------------------------------------------------------------

    async def list_users(
        self,
        *,
        search: str | None,
        status: PlatformUserStatus | None,
        role: PlatformRole | None,
        sort: Sequence[SortField],
        limit: int,
        offset: int,
    ) -> UserPage:
        context = current_context()
        authorize(context, PLATFORM_USER_READ)
        async with context_transaction(self.identity.factory, context) as db:
            items, total = await admin_repo.list_users(
                db,
                search=search,
                status=status,
                role=role,
                sort=sort,
                limit=limit,
                offset=offset,
            )
        return UserPage(items, total)

    async def get_user(self, user_id: uuid.UUID) -> AdminUser:
        context = current_context()
        authorize(context, PLATFORM_USER_READ)
        async with context_transaction(self.identity.factory, context) as db:
            return await self._target(db, user_id)

    # --- create and invitations (D7-3) ---------------------------------------------------

    async def create_user(
        self, raw_email: str, display_name: str, roles: Sequence[PlatformRole]
    ) -> CreatedUser:
        context = current_context()
        authorize(context, PLATFORM_USER_CREATE)
        try:
            email = normalize_email(raw_email)
        except InvalidEmailError:
            raise _invalid("email", "invalid", "Enter a valid email address.") from None
        name = _display_name(display_name)
        wanted = _roles(roles)
        user_id = uuid.uuid7()
        token_hash, message = self._invitation(email, name)
        now = self.identity.now()
        try:
            async with admin_target_transaction(
                self.identity.factory, context=context, target_user_id=user_id
            ) as db:
                if await admin_repo.email_taken(db, email):
                    raise ConflictError("A platform user with this email already exists.")
                await admin_repo.insert_user(db, user_id, email=email, display_name=name)
                await admin_repo.set_roles(db, user_id, add=sorted(wanted), remove=())
                await admin_repo.insert_invitation(
                    db,
                    user_id,
                    token_hash=token_hash,
                    expires_at=now + PLATFORM_INVITATION_TTL,
                    invited_by=context.principal_id,
                )
                target = AuditTarget("platform_user", user_id)
                await write_audit_event(
                    db,
                    events.USER_CREATED,
                    target=target,
                    metadata={"roles": sorted(role.value for role in wanted)},
                )
                await write_audit_event(db, events.INVITATION_SENT, target=target)
                created = await self._target(db, user_id)
        except IntegrityError:  # the email was taken concurrently
            raise ConflictError("A platform user with this email already exists.") from None
        return CreatedUser(created, message)

    async def resend_invitation(self, user_id: uuid.UUID) -> EmailMessage:
        """A new invitation for an ``INVITED`` user; the open one stops working."""
        context = current_context()
        authorize(context, PLATFORM_USER_CREATE)
        now = self.identity.now()
        async with admin_target_transaction(
            self.identity.factory, context=context, target_user_id=user_id
        ) as db:
            target = await self._target(db, user_id)
            if target.status is not PlatformUserStatus.INVITED:
                raise ConflictError("Only invited users who have not joined can be re-invited.")
            token_hash, message = self._invitation(target.email, target.display_name)
            revoked = await admin_repo.revoke_open_invitations(db, user_id, now)
            await admin_repo.insert_invitation(
                db,
                user_id,
                token_hash=token_hash,
                expires_at=now + PLATFORM_INVITATION_TTL,
                invited_by=context.principal_id,
            )
            audit_target = AuditTarget("platform_user", user_id)
            if revoked:
                await write_audit_event(
                    db, events.INVITATION_REVOKED, target=audit_target, metadata={"count": revoked}
                )
            await write_audit_event(
                db, events.INVITATION_SENT, target=audit_target, metadata={"resent": True}
            )
        return message

    async def _open_invitation(
        self, token: str, info: PlatformRequestInfo
    ) -> tuple[admin_repo.InvitationRow, repo.PlatformIdentity, PlatformLookupKey]:
        if not is_well_formed(token):
            raise NotFoundError()
        key = PlatformLookupKey.token_hash(
            self.identity.hash_token(TokenPurpose.PLATFORM_INVITATION, token)
        )
        async with platform_lookup_transaction(
            self.identity.factory, request_id=info.request_id, key=key
        ) as db:
            invitation = await admin_repo.invitation_by_hash(db, key.value)
            person = await repo.identity(db, invitation.user_id) if invitation else None
        if (
            invitation is None
            or person is None
            or invitation.accepted_at is not None
            or invitation.revoked_at is not None
            or invitation.expires_at <= self.identity.now()
            or person.status is not PlatformUserStatus.INVITED
        ):
            raise NotFoundError()
        return invitation, person, key

    async def preview_invitation(self, token: str, info: PlatformRequestInfo) -> InvitationPreview:
        await self.identity.rate_limit("ip", "invitation", info.ip)
        _, person, _ = await self._open_invitation(token, info)
        return InvitationPreview(mask_email(person.email))

    async def accept_invitation(self, token: str, password: str, info: PlatformRequestInfo) -> None:
        """Set the first password; the account becomes ``ACTIVE`` and must enrol MFA next."""
        await self.identity.rate_limit("ip", "invitation", info.ip)
        problem = password_problem(password, common_passwords())
        if problem is not None:
            raise _invalid("password", problem.value, PASSWORD_MESSAGES[problem])
        invitation, _, key = await self._open_invitation(token, info)
        password_hash = await self.identity.hasher.hash(password)
        try:
            async with platform_lookup_transaction(
                self.identity.factory, request_id=info.request_id, key=key
            ) as db:
                now = self.identity.now()
                if not await admin_repo.accept_invitation(db, invitation.id, now):
                    raise NotFoundError()
                if not await admin_repo.activate_invited_user(db, invitation.user_id):
                    raise NotFoundError()
                await admin_repo.create_credential(db, invitation.user_id, password_hash, now)
        except IntegrityError:  # a credential exists already
            raise NotFoundError() from None
        record_security_event(
            events.INVITATION_ACCEPTED, target=AuditTarget("platform_user", invitation.user_id)
        )

    # --- update (roles, name) ------------------------------------------------------------

    async def update_user(
        self,
        user_id: uuid.UUID,
        *,
        version: int,
        display_name: str | None,
        roles: Sequence[PlatformRole] | None,
    ) -> AdminUser:
        context = current_context()
        authorize(context, PLATFORM_USER_UPDATE)
        name = _display_name(display_name) if display_name is not None else None
        wanted = _roles(roles) if roles is not None else None
        async with admin_target_transaction(
            self.identity.factory, context=context, target_user_id=user_id
        ) as db:
            target = await self._target(db, user_id)
            current = frozenset(target.roles)
            add = sorted(wanted - current) if wanted is not None else []
            remove = sorted(current - wanted) if wanted is not None else []
            if add or remove:
                self._refuse_self(context, user_id, "change_roles")
                if GUARDIAN_ROLE in remove and target.status is PlatformUserStatus.ACTIVE:
                    await self._keep_a_super_admin(db, target)
            values: dict[str, object] = {}
            if name is not None and name != target.display_name:
                values["display_name"] = name
            # The version moves on every accepted change, roles included.
            if not await admin_repo.update_user(db, user_id, version=version, values=values):
                _stale()
            await admin_repo.set_roles(db, user_id, add=add, remove=remove)
            metadata: dict[str, object] = {}
            if "display_name" in values:
                metadata["display_name_changed"] = True
            if add:
                metadata["roles_added"] = [role.value for role in add]
            if remove:
                metadata["roles_removed"] = [role.value for role in remove]
            await write_audit_event(
                db,
                events.USER_UPDATED,
                target=AuditTarget("platform_user", user_id),
                metadata=metadata,
            )
            return await self._target(db, user_id)

    # --- suspend and reactivate (D7-4, D7-5) ---------------------------------------------

    async def suspend_user(self, user_id: uuid.UUID, *, reason: str, version: int) -> AdminUser:
        context = current_context()
        authorize(context, PLATFORM_USER_SUSPEND)
        cleaned = _reason(reason)
        self._refuse_self(context, user_id, "suspend")
        now = self.identity.now()
        async with admin_target_transaction(
            self.identity.factory, context=context, target_user_id=user_id
        ) as db:
            target = await self._target(db, user_id)
            if target.status is PlatformUserStatus.SUSPENDED:
                raise ConflictError("This platform user is already suspended.")
            if target.status is PlatformUserStatus.ACTIVE:
                await self._keep_a_super_admin(db, target)
            if not await admin_repo.update_user(
                db,
                user_id,
                version=version,
                values={"status": PlatformUserStatus.SUSPENDED.value},
            ):
                _stale()
            sessions = await repo.revoke_user_sessions(
                db, user_id, PlatformSessionRevokeReason.ADMIN_SUSPENDED, now
            )
            invitations = await admin_repo.revoke_open_invitations(db, user_id, now)
            audit_target = AuditTarget("platform_user", user_id)
            await write_audit_event(
                db,
                events.USER_SUSPENDED,
                target=audit_target,
                metadata={"reason": cleaned, "revoked": sessions},
            )
            if invitations:
                await write_audit_event(
                    db,
                    events.INVITATION_REVOKED,
                    target=audit_target,
                    metadata={"count": invitations},
                )
            return await self._target(db, user_id)

    async def reactivate_user(self, user_id: uuid.UUID, *, reason: str, version: int) -> AdminUser:
        context = current_context()
        authorize(context, PLATFORM_USER_REACTIVATE)
        cleaned = _reason(reason)
        self._refuse_self(context, user_id, "reactivate")
        async with admin_target_transaction(
            self.identity.factory, context=context, target_user_id=user_id
        ) as db:
            target = await self._target(db, user_id)
            if target.status is not PlatformUserStatus.SUSPENDED:
                raise ConflictError("Only suspended platform users can be reactivated.")
            invited, accepted = await admin_repo.invitation_history(db, user_id)
            status = reactivated_status(invited=invited, accepted=accepted)
            if not await admin_repo.update_user(
                db, user_id, version=version, values={"status": status.value}
            ):
                _stale()
            await write_audit_event(
                db,
                events.USER_REACTIVATED,
                target=AuditTarget("platform_user", user_id),
                metadata={"reason": cleaned, "status": status.value},
            )
            return await self._target(db, user_id)

    # --- MFA reset (D6-3) -------------------------------------------------------------------

    async def reset_mfa(self, user_id: uuid.UUID, reason: str) -> MfaResetResult:
        """The T01-06 capability (permission, step-up, reason, self-refusal, audit)."""
        context = current_context()
        authorize(context, PLATFORM_USER_UPDATE)
        if context.principal_id == user_id:
            self._refuse_self(context, user_id, "reset_mfa")
        return await self.identity.reset_mfa(user_id, reason)
