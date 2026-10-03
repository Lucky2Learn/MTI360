"""Tenant member administration (T01-08; locked decisions D8-1, D8-3, D8-4).

Every operation authorizes the caller first (``authorize``), then works in one
transaction with the request's trusted context (tenant realm, active tenant,
principal): the tenant is never a parameter, and another tenant's membership
is not found.

* **Invitation (D8-1).** An existing account (found with the T01-04 email
  lookup) is reused unchanged; a ``DISABLED`` one is refused (``409``). A new
  person's ``INVITED`` identity is created only inside the **invitee scope**:
  this module alone publishes ``app.tenant_invitee_user_id`` for one
  server-generated ID, after authorization (migration 0008; a static test
  enforces the single publisher). The membership (``INVITED``), its campus
  scope, the initial roles (through the access service: ``role.assign`` and
  the no-escalation rule) and a 7-day single-use invitation (HMAC, T01-04
  acceptance flow) are created in the same transaction; the email is sent
  after commit (D10).
* **Lifecycle (D8-3).** ``ACTIVE ⇄ SUSPENDED`` (``member.suspend``),
  ``INVITED | ACTIVE | SUSPENDED → REVOKED`` (``member.revoke``; open
  invitations revoked), ``REVOKED → INVITED`` by re-invitation of the same
  row (``member.invite``). Every transition takes the membership ``version``.
  Sessions are **not** revoked: session resolution re-checks the membership
  on every request and removes access to the tenant.
* **Protection (D8-4).** No suspension, revocation, campus-scope change or
  role removal on one's own membership (``403``); the last ACTIVE owner is
  never suspended, revoked or stripped of the owner role (``409``, per-tenant
  advisory lock in the access service).

Nothing returned, logged or audited contains a token. Global identity and
credentials are never changed (D14).
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, NoReturn

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditTarget, write_audit_event
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
from app.integrations.email import EmailMessage, EmailSender
from app.modules.access import service as access
from app.modules.identity import events
from app.modules.identity import members_repository as repo
from app.modules.identity.domain import (
    INVITATION_TTL,
    CampusScope,
    InvalidEmailError,
    InvalidMembershipTransitionError,
    MembershipAction,
    MembershipStatus,
    UserStatus,
    membership_transition,
    normalize_email,
)
from app.modules.identity.lookup import LookupKey, lookup_transaction
from app.modules.identity.permissions import (
    MEMBER_INVITE,
    MEMBER_READ,
    MEMBER_REVOKE,
    MEMBER_SUSPEND,
    MEMBER_UPDATE,
)
from app.modules.identity.repository import login_candidate, tenant_name
from app.modules.identity.service import IdentityService
from app.modules.identity.templates import invitation_link, member_invitation_email
from app.modules.identity.tokens import TokenPurpose, new_token

TENANT_INVITEE_USER_ID: Final = "app.tenant_invitee_user_id"
"""D8-1: the one ``INVITED`` identity a tenant transaction may create (migration 0008)."""
DISPLAY_NAME_MAX_LENGTH: Final = 200
MAX_INITIAL_ROLES: Final = 20
MAX_SELECTED_CAMPUSES: Final = 100

_SET_LOCAL = text("SELECT set_config(:name, :value, true)")

Member = repo.MemberRow


@dataclass(frozen=True, slots=True)
class MemberPage:
    items: list[Member]
    total: int


@dataclass(frozen=True, slots=True)
class Invited:
    member: Member
    account: str
    """``new`` or ``existing``."""
    email: EmailMessage


def _invalid(field: str, code: str, message: str) -> ValidationFailedError:
    return ValidationFailedError(details=[ErrorDetail(field=field, code=code, message=message)])


def _tenant(context: RequestContext) -> uuid.UUID:
    if context.tenant_id is None:  # authorize() already refused; keeps types honest
        raise PermissionDeniedError()
    return context.tenant_id


def _display_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned or len(cleaned) > DISPLAY_NAME_MAX_LENGTH:
        raise _invalid("display_name", "invalid", "Enter a name of up to 200 characters.")
    return cleaned


def _stale() -> NoReturn:
    raise ConflictError("This member was changed by someone else. Reload and try again.")


async def _publish_invitee(db: AsyncSession, user_id: uuid.UUID) -> None:
    """D8-1: open ``users`` INSERT for exactly this ``INVITED`` identity."""
    await db.execute(_SET_LOCAL, {"name": TENANT_INVITEE_USER_ID, "value": str(user_id)})


class MemberAdmin:
    """Tenant member administration (``/api/v1/members``)."""

    def __init__(self, identity: IdentityService) -> None:
        self.identity = identity

    @property
    def email_sender(self) -> EmailSender:
        return self.identity.email_sender

    # --- helpers ------------------------------------------------------------------------

    async def _member(self, db: AsyncSession, membership_id: uuid.UUID) -> Member:
        found = await repo.member(db, _tenant(current_context()), membership_id)
        if found is None:
            raise NotFoundError()
        return found

    async def _campus_scope(
        self, db: AsyncSession, scope: CampusScope, campus_ids: Sequence[uuid.UUID]
    ) -> list[uuid.UUID]:
        """Validated campus selection: ``SELECTED`` needs 1..100 campuses of this tenant."""
        if scope is CampusScope.ALL:
            if campus_ids:
                raise _invalid(
                    "campus_ids", "not_allowed", "Leave campuses empty for all campuses."
                )
            return []
        unique = list(dict.fromkeys(campus_ids))
        if not unique or len(unique) > MAX_SELECTED_CAMPUSES:
            raise _invalid("campus_ids", "required", "Choose at least one campus.")
        found = await repo.tenant_campuses(db, _tenant(current_context()), unique)
        if found != set(unique):
            raise _invalid("campus_ids", "unknown", "Choose campuses of this institute.")
        return unique

    async def _invitation(
        self, db: AsyncSession, member: Member, *, now_revoke: bool
    ) -> tuple[EmailMessage, int]:
        """A new invitation for ``member`` (open ones revoked first); its email."""
        tenant_id = _tenant(current_context())
        now = self.identity.now()
        revoked = (
            await repo.revoke_open_invitations(db, tenant_id, member.id, now) if now_revoke else 0
        )
        token = new_token()
        await repo.insert_invitation(
            db,
            tenant_id,
            member.id,
            token_hash=self.identity.hash_token(TokenPurpose.INVITATION, token),
            expires_at=now + INVITATION_TTL,
        )
        institute = await tenant_name(db, tenant_id)
        message = member_invitation_email(
            to=member.email,
            display_name=member.display_name,
            institute=institute[0] if institute else "your institute",
            link=invitation_link(self.identity.config.app_base_url, token),
        )
        return message, revoked

    async def _transition(
        self,
        db: AsyncSession,
        member: Member,
        action: MembershipAction,
        *,
        version: int,
    ) -> MembershipStatus:
        try:
            target = membership_transition(member.status, action)
        except InvalidMembershipTransitionError:
            raise ConflictError(
                f"A member in status {member.status.value} cannot be {_PAST[action]}."
            ) from None
        if not await repo.set_status(
            db,
            member.tenant_id,
            member.id,
            version=version,
            current=member.status,
            target=target,
        ):
            _stale()
        return target

    # --- directory ----------------------------------------------------------------------

    async def list_members(
        self,
        *,
        search: str | None,
        status: MembershipStatus | None,
        sort: Sequence[SortField],
        limit: int,
        offset: int,
    ) -> MemberPage:
        context = current_context()
        authorize(context, MEMBER_READ)
        async with context_transaction(self.identity.factory, context) as db:
            items, total = await repo.list_members(
                db,
                _tenant(context),
                search=search,
                status=status,
                sort=sort,
                limit=limit,
                offset=offset,
            )
        return MemberPage(items, total)

    async def get_member(self, membership_id: uuid.UUID) -> Member:
        context = current_context()
        authorize(context, MEMBER_READ)
        async with context_transaction(self.identity.factory, context) as db:
            member = await self._member(db, membership_id)
            authorize(context, MEMBER_READ, member)
            return member

    # --- invitation (D8-1) ------------------------------------------------------------------

    async def invite(
        self,
        *,
        raw_email: str,
        display_name: str,
        role_ids: Sequence[uuid.UUID],
        campus_scope: CampusScope,
        campus_ids: Sequence[uuid.UUID],
    ) -> Invited:
        context = current_context()
        authorize(context, MEMBER_INVITE)
        tenant_id = _tenant(context)
        try:
            email = normalize_email(raw_email)
        except InvalidEmailError:
            raise _invalid("email", "invalid", "Enter a valid email address.") from None
        name = _display_name(display_name)
        roles = list(dict.fromkeys(role_ids))
        if len(roles) > MAX_INITIAL_ROLES:
            raise _invalid("role_ids", "too_many", "Choose at most 20 roles.")
        async with lookup_transaction(
            self.identity.factory, request_id=context.request_id, key=LookupKey.email(email)
        ) as db:
            existing = await login_candidate(db, email)
        if existing is not None and existing.status is UserStatus.DISABLED:
            raise ConflictError("This email belongs to a disabled account and cannot be invited.")
        try:
            async with context_transaction(self.identity.factory, context) as db:
                campuses = await self._campus_scope(db, campus_scope, campus_ids)
                if existing is None:
                    user_id = uuid.uuid7()
                    await _publish_invitee(db, user_id)
                    await repo.insert_invited_user(db, user_id, email=email, display_name=name)
                else:
                    user_id = existing.user_id
                    if await repo.membership_of_user(db, tenant_id, user_id) is not None:
                        raise ConflictError(
                            "This person is already a member of the institute. "
                            "Re-invite a removed member from their member page."
                        )
                membership_id = await repo.insert_membership(
                    db,
                    tenant_id,
                    user_id,
                    campus_scope=campus_scope,
                    invited_by=context.principal_id,
                )
                await repo.replace_campuses(
                    db, tenant_id, membership_id, campuses, self.identity.now()
                )
                account = "new" if existing is None else "existing"
                await write_audit_event(
                    db,
                    events.MEMBER_INVITED,
                    target=AuditTarget("tenant_membership", membership_id),
                    metadata={
                        "account": account,
                        "campus_scope": campus_scope.value,
                        "campus_count": len(campuses),
                        "role_count": len(roles),
                    },
                )
                for role_id in roles:  # role.assign and no-escalation, audited
                    await access.assign_role(db, membership_id, role_id)
                member = await self._member(db, membership_id)
                message, _ = await self._invitation(db, member, now_revoke=False)
        except IntegrityError:  # the email or the membership was created concurrently
            raise ConflictError("This person could not be invited. Reload and try again.") from None
        return Invited(member, account, message)

    async def resend_invitation(self, membership_id: uuid.UUID) -> EmailMessage:
        """A new invitation while the member has not joined; the previous link stops working."""
        context = current_context()
        authorize(context, MEMBER_INVITE)
        async with context_transaction(self.identity.factory, context) as db:
            member = await self._member(db, membership_id)
            if member.status is not MembershipStatus.INVITED:
                raise ConflictError("Only invited members who have not joined can be re-sent.")
            if member.user_status is UserStatus.DISABLED:
                raise ConflictError("This email belongs to a disabled account.")
            message, revoked = await self._invitation(db, member, now_revoke=True)
            await write_audit_event(
                db,
                events.MEMBER_INVITATION_RESENT,
                target=AuditTarget("tenant_membership", member.id),
                metadata={"revoked": revoked},
            )
        return message

    async def reinvite(self, membership_id: uuid.UUID, *, version: int) -> Invited:
        """``REVOKED → INVITED`` on the same membership row, with a new invitation (D8-3)."""
        context = current_context()
        authorize(context, MEMBER_INVITE)
        async with context_transaction(self.identity.factory, context) as db:
            member = await self._member(db, membership_id)
            if member.user_status is UserStatus.DISABLED:
                raise ConflictError(
                    "This email belongs to a disabled account and cannot be invited."
                )
            await self._transition(db, member, MembershipAction.REINVITE, version=version)
            message, revoked = await self._invitation(db, member, now_revoke=True)
            await write_audit_event(
                db,
                events.MEMBER_REINVITED,
                target=AuditTarget("tenant_membership", member.id),
                metadata={"revoked": revoked},
            )
            refreshed = await self._member(db, membership_id)
        return Invited(refreshed, "existing", message)

    # --- lifecycle (D8-3, D8-4) ---------------------------------------------------------

    async def suspend(self, membership_id: uuid.UUID, *, version: int) -> Member:
        context = current_context()
        authorize(context, MEMBER_SUSPEND)
        async with context_transaction(self.identity.factory, context) as db:
            member = await self._member(db, membership_id)
            access.refuse_self(context, member.user_id, member.id, "suspend")
            if member.status is MembershipStatus.ACTIVE:
                await access.keep_an_owner(db, member.id)
            await self._transition(db, member, MembershipAction.SUSPEND, version=version)
            await write_audit_event(
                db, events.MEMBER_SUSPENDED, target=AuditTarget("tenant_membership", member.id)
            )
            return await self._member(db, membership_id)

    async def reinstate(self, membership_id: uuid.UUID, *, version: int) -> Member:
        context = current_context()
        authorize(context, MEMBER_SUSPEND)
        async with context_transaction(self.identity.factory, context) as db:
            member = await self._member(db, membership_id)
            await self._transition(db, member, MembershipAction.REINSTATE, version=version)
            await write_audit_event(
                db, events.MEMBER_REINSTATED, target=AuditTarget("tenant_membership", member.id)
            )
            return await self._member(db, membership_id)

    async def revoke(self, membership_id: uuid.UUID, *, version: int) -> Member:
        context = current_context()
        authorize(context, MEMBER_REVOKE)
        async with context_transaction(self.identity.factory, context) as db:
            member = await self._member(db, membership_id)
            access.refuse_self(context, member.user_id, member.id, "revoke")
            if member.status is MembershipStatus.ACTIVE:
                await access.keep_an_owner(db, member.id)
            previous = member.status
            await self._transition(db, member, MembershipAction.REVOKE, version=version)
            invitations = await repo.revoke_open_invitations(
                db, member.tenant_id, member.id, self.identity.now()
            )
            await write_audit_event(
                db,
                events.MEMBER_REVOKED,
                target=AuditTarget("tenant_membership", member.id),
                metadata={"from": previous.value, "invitations_revoked": invitations},
            )
            return await self._member(db, membership_id)

    # --- campus scope and roles ----------------------------------------------------------

    async def set_campus_scope(
        self,
        membership_id: uuid.UUID,
        *,
        scope: CampusScope,
        campus_ids: Sequence[uuid.UUID],
        version: int,
    ) -> Member:
        context = current_context()
        authorize(context, MEMBER_UPDATE)
        async with context_transaction(self.identity.factory, context) as db:
            member = await self._member(db, membership_id)
            access.refuse_self(context, member.user_id, member.id, "change_campus_scope")
            campuses = await self._campus_scope(db, scope, campus_ids)
            if not await repo.set_campus_scope(
                db, member.tenant_id, member.id, version=version, scope=scope
            ):
                _stale()
            await repo.replace_campuses(
                db, member.tenant_id, member.id, campuses, self.identity.now()
            )
            await write_audit_event(
                db,
                events.MEMBER_CAMPUS_SCOPE_CHANGED,
                target=AuditTarget("tenant_membership", member.id),
                metadata={
                    "from": member.campus_scope.value,
                    "to": scope.value,
                    "campus_count": len(campuses),
                },
            )
            return await self._member(db, membership_id)

    async def assign_role(self, membership_id: uuid.UUID, role_id: uuid.UUID) -> Member:
        """``role.assign`` with the no-escalation rule (access service)."""
        context = current_context()
        async with context_transaction(self.identity.factory, context) as db:
            await access.assign_role(db, membership_id, role_id)
            return await self._member(db, membership_id)

    async def remove_role(self, membership_id: uuid.UUID, role_id: uuid.UUID) -> Member:
        """``role.assign``; never one's own roles (403) or the last owner's owner role (409)."""
        context = current_context()
        async with context_transaction(self.identity.factory, context) as db:
            await access.remove_role(db, membership_id, role_id)
            return await self._member(db, membership_id)


_PAST: Final = {
    MembershipAction.SUSPEND: "suspended",
    MembershipAction.REINSTATE: "reinstated",
    MembershipAction.REVOKE: "removed",
    MembershipAction.REINVITE: "re-invited",
}
