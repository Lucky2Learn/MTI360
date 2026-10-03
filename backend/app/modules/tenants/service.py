"""Tenant administration for the platform (T01-07; D7-1, D7-6 … D7-8, D15).

* **List and detail** — the registry (platform realm reads every tenant). The
  detail adds the primary administrator through the owner scope (D7-8).
* **Provision** (D7-1) — one provisioning transaction creates the tenant
  (``TRIAL``), its primary campus, its system roles (``clone_system_roles``),
  the owner's ``INVITED`` membership with the owner template role and a 7-day
  invitation. An owner email with an existing tenant account gets an
  "existing account" invitation; its identity and credential never change
  (D7-7). The invitation email is sent after commit (D10).
* **Suspend / reactivate** (D15, D7-6) — ``tenants/domain.py`` transitions with
  a reason and the current ``version``; suspension revokes, in the same
  transaction, every live session whose active institute is the tenant.
* **Resend the owner invitation** (D7-8) — only while the owner has not joined.

Each operation authorizes first; step-up for suspend and reactivate is enforced
by ``authorize`` (D6-5). Changes are audited in their own transaction.
"""

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import NoReturn

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditTarget, write_audit_event
from app.core.authz import authorize
from app.core.context import current_context
from app.core.db.session import context_transaction
from app.core.errors import ConflictError, ErrorDetail, NotFoundError, ValidationFailedError
from app.core.pagination import SortField
from app.integrations.email import EmailMessage, EmailSender
from app.modules.access import repository as access_repo
from app.modules.access.service import clone_system_roles
from app.modules.access.templates import OWNER_TEMPLATE
from app.modules.identity.domain import (
    INVITATION_TTL,
    InvalidEmailError,
    MembershipStatus,
    UserStatus,
    normalize_email,
)
from app.modules.identity.lookup import LookupKey, lookup_transaction
from app.modules.identity.tokens import TokenPurpose, new_token, token_hash
from app.modules.institute.models import CAMPUS_CODE_MAX_LENGTH, CAMPUS_CODE_PATTERN
from app.modules.platform_identity.domain import clean_display_name, clean_reason
from app.modules.platform_identity.service import PlatformIdentityService
from app.modules.tenants import events
from app.modules.tenants import repository as repo
from app.modules.tenants.domain import (
    InvalidTenantTransitionError,
    TenantStatus,
    TenantTransition,
    transition,
)
from app.modules.tenants.permissions import (
    TENANT_CREATE,
    TENANT_REACTIVATE,
    TENANT_READ,
    TENANT_SUSPEND,
)
from app.modules.tenants.scopes import (
    provisioning_transaction,
    publish_owner,
    publish_suspension_target,
)
from app.modules.tenants.templates import invitation_link, owner_invitation_email

NAME_MAX_LENGTH = 200
_CAMPUS_CODE = re.compile(CAMPUS_CODE_PATTERN)


@dataclass(frozen=True, slots=True)
class TenantPage:
    items: list[repo.TenantRow]
    total: int


@dataclass(frozen=True, slots=True)
class TenantDetail:
    tenant: repo.TenantRow
    owner: repo.OwnerRow | None


@dataclass(frozen=True, slots=True)
class ProvisionedCampus:
    id: uuid.UUID
    name: str
    code: str


@dataclass(frozen=True, slots=True)
class ProvisionedTenant:
    detail: TenantDetail
    campus: ProvisionedCampus
    owner_account: str
    """``new`` or ``existing`` (D7-7)."""
    email: EmailMessage


@dataclass(frozen=True, slots=True)
class ProvisionRequest:
    name: str
    campus_name: str
    campus_code: str
    owner_email: str
    owner_display_name: str


def _invalid(field: str, code: str, message: str) -> ValidationFailedError:
    return ValidationFailedError(details=[ErrorDetail(field=field, code=code, message=message)])


def _name(value: str, field: str) -> str:
    cleaned = clean_display_name(value)
    if cleaned is None:
        raise _invalid(field, "invalid", f"Enter a name of up to {NAME_MAX_LENGTH} characters.")
    return cleaned


def _stale() -> NoReturn:
    raise ConflictError("This institute was changed by someone else. Reload and try again.")


class TenantAdmin:
    """Platform tenant administration (``/api/v1/platform/tenants``)."""

    def __init__(self, platform: PlatformIdentityService, *, invitation_secret: str) -> None:
        self.platform = platform
        self._invitation_secret = invitation_secret

    @property
    def email_sender(self) -> EmailSender:
        return self.platform.email_sender

    def _invitation(
        self, *, to: str, display_name: str, institute: str
    ) -> tuple[str, EmailMessage]:
        token = new_token()
        message = owner_invitation_email(
            to=to,
            display_name=display_name,
            institute=institute,
            link=invitation_link(self.platform.config.app_base_url, token),
        )
        return token_hash(self._invitation_secret, TokenPurpose.INVITATION, token), message

    async def _detail(self, db: AsyncSession, tenant_id: uuid.UUID) -> TenantDetail:
        found = await repo.tenant(db, tenant_id)
        if found is None:
            raise NotFoundError()
        owner = None
        if found.owner_membership_id is not None:
            await publish_owner(db, found.owner_membership_id)
            owner = await repo.owner(db, found.owner_membership_id)
        return TenantDetail(found, owner)

    # --- registry -------------------------------------------------------------------------

    async def list_tenants(
        self,
        *,
        search: str | None,
        status: TenantStatus | None,
        sort: Sequence[SortField],
        limit: int,
        offset: int,
    ) -> TenantPage:
        context = current_context()
        authorize(context, TENANT_READ)
        async with context_transaction(self.platform.factory, context) as db:
            items, total = await repo.list_tenants(
                db, search=search, status=status, sort=sort, limit=limit, offset=offset
            )
        return TenantPage(items, total)

    async def get_tenant(self, tenant_id: uuid.UUID) -> TenantDetail:
        context = current_context()
        authorize(context, TENANT_READ)
        async with context_transaction(self.platform.factory, context) as db:
            return await self._detail(db, tenant_id)

    # --- provisioning (D7-1, D7-7) ------------------------------------------------------------

    def _validated(self, request: ProvisionRequest) -> ProvisionRequest:
        code = request.campus_code.strip().upper()
        if len(code) > CAMPUS_CODE_MAX_LENGTH or not _CAMPUS_CODE.fullmatch(code):
            raise _invalid(
                "campus.code",
                "invalid",
                "Use up to 32 letters, digits or hyphens, starting with a letter or digit.",
            )
        try:
            email = normalize_email(request.owner_email)
        except InvalidEmailError:
            raise _invalid("owner.email", "invalid", "Enter a valid email address.") from None
        return ProvisionRequest(
            name=_name(request.name, "name"),
            campus_name=_name(request.campus_name, "campus.name"),
            campus_code=code,
            owner_email=email,
            owner_display_name=_name(request.owner_display_name, "owner.display_name"),
        )

    async def provision(self, raw: ProvisionRequest) -> ProvisionedTenant:
        context = current_context()
        authorize(context, TENANT_CREATE)
        request = self._validated(raw)
        async with lookup_transaction(
            self.platform.factory,
            request_id=context.request_id,
            key=LookupKey.email(request.owner_email),
        ) as db:
            existing = await repo.user_by_email(db, request.owner_email)
        if existing is not None and existing[1] is UserStatus.DISABLED:
            raise ConflictError("This email belongs to a disabled account and cannot be invited.")
        tenant_id = uuid.uuid7()
        hashed, message = self._invitation(
            to=request.owner_email,
            display_name=request.owner_display_name,
            institute=request.name,
        )
        now = self.platform.now()
        try:
            async with provisioning_transaction(
                self.platform.factory, context=context, tenant_id=tenant_id
            ) as db:
                await repo.insert_tenant(db, tenant_id, request.name)
                campus_id = await repo.insert_campus(
                    db, tenant_id, name=request.campus_name, code=request.campus_code
                )
                roles = await clone_system_roles(db, tenant_id)
                if existing is None:
                    user_id = uuid.uuid7()
                    await repo.insert_invited_user(
                        db,
                        user_id,
                        email=request.owner_email,
                        display_name=request.owner_display_name,
                    )
                else:
                    user_id = existing[0]
                membership_id = await repo.insert_owner_membership(db, tenant_id, user_id)
                await access_repo.assign(db, tenant_id, membership_id, roles[OWNER_TEMPLATE.value])
                await repo.insert_invitation(
                    db,
                    tenant_id,
                    membership_id,
                    token_hash=hashed,
                    expires_at=now + INVITATION_TTL,
                )
                await repo.set_owner(db, tenant_id, membership_id)
                account = "new" if existing is None else "existing"
                await write_audit_event(
                    db,
                    events.TENANT_CREATED,
                    target=AuditTarget("tenant", tenant_id),
                    metadata={"campus_code": request.campus_code},
                )
                await write_audit_event(
                    db,
                    events.OWNER_INVITED,
                    target=AuditTarget("tenant_membership", membership_id),
                    metadata={"account": account},
                )
                detail = await self._detail(db, tenant_id)
        except IntegrityError:  # the owner email was registered concurrently
            raise ConflictError("The institute could not be created. Try again.") from None
        campus = ProvisionedCampus(campus_id, request.campus_name, request.campus_code)
        return ProvisionedTenant(detail, campus, account, message)

    # --- lifecycle (D15, D7-6) ---------------------------------------------------------------

    async def _transition(
        self, tenant_id: uuid.UUID, action: TenantTransition, *, reason: str, version: int
    ) -> TenantDetail:
        context = current_context()
        authorize(
            context, TENANT_SUSPEND if action is TenantTransition.SUSPEND else TENANT_REACTIVATE
        )
        cleaned = clean_reason(reason)
        if cleaned is None:
            raise _invalid("reason", "reason_required", "Give a reason of up to 500 characters.")
        async with context_transaction(self.platform.factory, context) as db:
            found = await repo.tenant(db, tenant_id)
            if found is None:
                raise NotFoundError()
            try:
                target = transition(found.status, action)
            except InvalidTenantTransitionError:
                verb = "suspended" if action is TenantTransition.SUSPEND else "reactivated"
                raise ConflictError(
                    f"An institute in status {found.status.value} cannot be {verb}."
                ) from None
            if not await repo.set_status(db, tenant_id, version=version, status=target):
                _stale()
            metadata: dict[str, object] = {"reason": cleaned, "from": found.status.value}
            if action is TenantTransition.SUSPEND:
                await publish_suspension_target(db, tenant_id)
                metadata["revoked"] = await repo.revoke_tenant_sessions(
                    db, tenant_id, self.platform.now()
                )
            await write_audit_event(
                db,
                events.TENANT_SUSPENDED
                if action is TenantTransition.SUSPEND
                else events.TENANT_REACTIVATED,
                target=AuditTarget("tenant", tenant_id),
                metadata=metadata,
            )
            return await self._detail(db, tenant_id)

    async def suspend(self, tenant_id: uuid.UUID, *, reason: str, version: int) -> TenantDetail:
        return await self._transition(
            tenant_id, TenantTransition.SUSPEND, reason=reason, version=version
        )

    async def reactivate(self, tenant_id: uuid.UUID, *, reason: str, version: int) -> TenantDetail:
        return await self._transition(
            tenant_id, TenantTransition.REACTIVATE, reason=reason, version=version
        )

    # --- owner invitation resend (D7-8) ------------------------------------------------------

    async def resend_owner_invitation(self, tenant_id: uuid.UUID) -> EmailMessage:
        context = current_context()
        authorize(context, TENANT_CREATE)
        now = self.platform.now()
        async with context_transaction(self.platform.factory, context) as db:
            detail = await self._detail(db, tenant_id)
            owner = detail.owner
            if owner is None or owner.membership_status is not MembershipStatus.INVITED:
                raise ConflictError("The institute's administrator has already joined.")
            if owner.user_status is UserStatus.DISABLED:
                raise ConflictError(
                    "This email belongs to a disabled account and cannot be invited."
                )
            hashed, message = self._invitation(
                to=owner.email, display_name=owner.display_name, institute=detail.tenant.name
            )
            revoked = await repo.revoke_open_invitations(db, owner.membership_id, now)
            await repo.insert_invitation(
                db,
                tenant_id,
                owner.membership_id,
                token_hash=hashed,
                expires_at=now + INVITATION_TTL,
            )
            await write_audit_event(
                db,
                events.OWNER_INVITATION_RESENT,
                target=AuditTarget("tenant_membership", owner.membership_id),
                metadata={"revoked": revoked},
            )
        return message
