"""Identity data access (T01-04). Repositories never commit.

Every query states its own predicate (email, token hash, user or tenant) in
addition to Row-Level Security. Two kinds of queries cannot use the automatic
tenant ORM filter, because they run before a tenant is active, and use Core
statements with an explicit predicate instead (decision D03):

* the user's own memberships across tenants (``user_id = :user``);
* an invitation and its membership by token hash.

Mutations of credentials and sessions are single atomic UPDATE statements
(no read-modify-write), so concurrent sign-ins cannot lose an increment.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import Table, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.domain import (
    CampusScope,
    MembershipStatus,
    SessionRevokeReason,
    UserStatus,
)
from app.modules.identity.models import (
    MembershipCampus,
    PasswordResetToken,
    TenantMembership,
    User,
    UserCredential,
    UserInvitation,
    UserSession,
)
from app.modules.institute.models import Campus
from app.modules.tenants.models import Tenant

USERS = cast(Table, User.__table__)
CREDENTIALS = cast(Table, UserCredential.__table__)
MEMBERSHIPS = cast(Table, TenantMembership.__table__)
MEMBERSHIP_CAMPUSES = cast(Table, MembershipCampus.__table__)
SESSIONS = cast(Table, UserSession.__table__)
RESET_TOKENS = cast(Table, PasswordResetToken.__table__)
INVITATIONS = cast(Table, UserInvitation.__table__)
TENANTS = cast(Table, Tenant.__table__)
CAMPUSES = cast(Table, Campus.__table__)


# --- Records -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LoginCandidate:
    user_id: uuid.UUID
    status: UserStatus
    password_hash: str | None
    locked_until: datetime | None


@dataclass(frozen=True, slots=True)
class MembershipView:
    membership_id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_status: str
    status: MembershipStatus
    campus_scope: CampusScope
    selected_campus_count: int


@dataclass(frozen=True, slots=True)
class CampusView:
    id: uuid.UUID
    name: str
    code: str


@dataclass(frozen=True, slots=True)
class SessionRow:
    id: uuid.UUID
    user_id: uuid.UUID
    active_tenant_id: uuid.UUID | None
    active_campus_id: uuid.UUID | None
    last_seen_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class InvitationRow:
    id: uuid.UUID
    tenant_id: uuid.UUID
    membership_id: uuid.UUID
    user_id: uuid.UUID
    membership_status: MembershipStatus
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class ResetTokenRow:
    id: uuid.UUID
    user_id: uuid.UUID
    expires_at: datetime
    used_at: datetime | None
    invalidated_at: datetime | None


# --- Users and credentials -----------------------------------------------------------------


async def login_candidate(session: AsyncSession, email: str) -> LoginCandidate | None:
    row = (
        await session.execute(
            select(
                USERS.c.id, USERS.c.status, CREDENTIALS.c.password_hash, CREDENTIALS.c.locked_until
            )
            .select_from(USERS.outerjoin(CREDENTIALS, CREDENTIALS.c.user_id == USERS.c.id))
            .where(USERS.c.email == email)
        )
    ).one_or_none()
    if row is None:
        return None
    return LoginCandidate(row.id, UserStatus(row.status), row.password_hash, row.locked_until)


async def user_identity(
    session: AsyncSession, user_id: uuid.UUID
) -> tuple[str, str, UserStatus] | None:
    """(display name, email, status) of a user."""
    row = (
        await session.execute(
            select(USERS.c.display_name, USERS.c.email, USERS.c.status).where(USERS.c.id == user_id)
        )
    ).one_or_none()
    return (row.display_name, row.email, UserStatus(row.status)) if row else None


async def has_credential(session: AsyncSession, user_id: uuid.UUID) -> bool:
    count = (
        await session.execute(
            select(func.count()).select_from(CREDENTIALS).where(CREDENTIALS.c.user_id == user_id)
        )
    ).scalar_one()
    return count > 0


async def record_failed_login(session: AsyncSession, user_id: uuid.UUID, now: datetime) -> int:
    """Count one failure unless the account is locked; return the new count (0 if locked)."""
    count = (
        await session.execute(
            update(CREDENTIALS)
            .where(CREDENTIALS.c.user_id == user_id)
            .where((CREDENTIALS.c.locked_until.is_(None)) | (CREDENTIALS.c.locked_until <= now))
            .values(failed_login_count=CREDENTIALS.c.failed_login_count + 1)
            .returning(CREDENTIALS.c.failed_login_count)
        )
    ).scalar_one_or_none()
    return int(count or 0)


async def lock_account(session: AsyncSession, user_id: uuid.UUID, until: datetime) -> None:
    await session.execute(
        update(CREDENTIALS).where(CREDENTIALS.c.user_id == user_id).values(locked_until=until)
    )


async def record_successful_login(
    session: AsyncSession, user_id: uuid.UUID, new_hash: str | None
) -> None:
    values: dict[str, object] = {"failed_login_count": 0, "locked_until": None}
    if new_hash is not None:
        values["password_hash"] = new_hash
    await session.execute(
        update(CREDENTIALS).where(CREDENTIALS.c.user_id == user_id).values(**values)
    )


async def set_password(
    session: AsyncSession, user_id: uuid.UUID, password_hash: str, now: datetime
) -> int:
    result = await session.execute(
        update(CREDENTIALS)
        .where(CREDENTIALS.c.user_id == user_id)
        .values(
            password_hash=password_hash,
            password_changed_at=now,
            failed_login_count=0,
            locked_until=None,
        )
    )
    return int(result.rowcount)  # type: ignore[attr-defined]


async def create_credential(
    session: AsyncSession, user_id: uuid.UUID, password_hash: str, now: datetime
) -> None:
    await session.execute(
        insert(CREDENTIALS).values(
            id=uuid.uuid7(), user_id=user_id, password_hash=password_hash, password_changed_at=now
        )
    )


# --- Memberships and campuses ------------------------------------------------------------


async def memberships_of_user(session: AsyncSession, user_id: uuid.UUID) -> list[MembershipView]:
    """The user's memberships in every tenant, with tenant name and status (D03)."""
    selected = (
        select(func.count())
        .select_from(MEMBERSHIP_CAMPUSES)
        .where(MEMBERSHIP_CAMPUSES.c.membership_id == MEMBERSHIPS.c.id)
        .scalar_subquery()
    )
    rows = (
        await session.execute(
            select(
                MEMBERSHIPS.c.id,
                MEMBERSHIPS.c.tenant_id,
                TENANTS.c.name,
                TENANTS.c.status,
                MEMBERSHIPS.c.status.label("membership_status"),
                MEMBERSHIPS.c.campus_scope,
                selected.label("selected_campus_count"),
            )
            .select_from(MEMBERSHIPS.join(TENANTS, TENANTS.c.id == MEMBERSHIPS.c.tenant_id))
            .where(MEMBERSHIPS.c.user_id == user_id)
            .order_by(TENANTS.c.name, TENANTS.c.id)
        )
    ).all()
    return [
        MembershipView(
            row.id,
            row.tenant_id,
            row.name,
            row.status,
            MembershipStatus(row.membership_status),
            CampusScope(row.campus_scope),
            int(row.selected_campus_count),
        )
        for row in rows
    ]


async def permitted_campuses(
    session: AsyncSession, tenant_id: uuid.UUID, membership_id: uuid.UUID, scope: CampusScope
) -> list[CampusView]:
    """The campuses a membership may use in the active tenant, sorted by name (D04)."""
    statement = select(CAMPUSES.c.id, CAMPUSES.c.name, CAMPUSES.c.code).where(
        CAMPUSES.c.tenant_id == tenant_id
    )
    if scope is CampusScope.SELECTED:
        statement = statement.where(
            CAMPUSES.c.id.in_(
                select(MEMBERSHIP_CAMPUSES.c.campus_id).where(
                    MEMBERSHIP_CAMPUSES.c.membership_id == membership_id,
                    MEMBERSHIP_CAMPUSES.c.tenant_id == tenant_id,
                )
            )
        )
    rows = (await session.execute(statement.order_by(CAMPUSES.c.name, CAMPUSES.c.id))).all()
    return [CampusView(row.id, row.name, row.code) for row in rows]


async def activate_membership(
    session: AsyncSession, tenant_id: uuid.UUID, membership_id: uuid.UUID, now: datetime
) -> int:
    result = await session.execute(
        update(MEMBERSHIPS)
        .where(
            MEMBERSHIPS.c.tenant_id == tenant_id,
            MEMBERSHIPS.c.id == membership_id,
            MEMBERSHIPS.c.status == MembershipStatus.INVITED.value,
        )
        .values(
            status=MembershipStatus.ACTIVE.value,
            joined_at=now,
            version=MEMBERSHIPS.c.version + 1,
        )
    )
    return int(result.rowcount)  # type: ignore[attr-defined]


# --- Sessions ---------------------------------------------------------------------------


def _session_row(row: object) -> SessionRow:
    return SessionRow(
        row.id,  # type: ignore[attr-defined]
        row.user_id,  # type: ignore[attr-defined]
        row.active_tenant_id,  # type: ignore[attr-defined]
        row.active_campus_id,  # type: ignore[attr-defined]
        row.last_seen_at,  # type: ignore[attr-defined]
        row.idle_expires_at,  # type: ignore[attr-defined]
        row.absolute_expires_at,  # type: ignore[attr-defined]
        row.revoked_at,  # type: ignore[attr-defined]
    )


_SESSION_COLUMNS = (
    SESSIONS.c.id,
    SESSIONS.c.user_id,
    SESSIONS.c.active_tenant_id,
    SESSIONS.c.active_campus_id,
    SESSIONS.c.last_seen_at,
    SESSIONS.c.idle_expires_at,
    SESSIONS.c.absolute_expires_at,
    SESSIONS.c.revoked_at,
)


async def session_by_token_hash(session: AsyncSession, token_hash: str) -> SessionRow | None:
    row = (
        await session.execute(select(*_SESSION_COLUMNS).where(SESSIONS.c.token_hash == token_hash))
    ).one_or_none()
    return _session_row(row) if row else None


async def create_session(
    session: AsyncSession,
    *,
    token_hash: str,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID | None,
    campus_id: uuid.UUID | None,
    now: datetime,
    idle_expires_at: datetime,
    absolute_expires_at: datetime,
    ip: str | None,
    user_agent: str | None,
) -> uuid.UUID:
    session_id = uuid.uuid7()
    await session.execute(
        insert(SESSIONS).values(
            id=session_id,
            token_hash=token_hash,
            user_id=user_id,
            realm="tenant",
            active_tenant_id=tenant_id,
            active_campus_id=campus_id,
            created_at=now,
            last_seen_at=now,
            idle_expires_at=idle_expires_at,
            absolute_expires_at=absolute_expires_at,
            ip=ip,
            user_agent=user_agent[:256] if user_agent else None,
        )
    )
    return session_id


async def touch_session(
    session: AsyncSession,
    session_id: uuid.UUID,
    *,
    now: datetime,
    idle_expires_at: datetime,
) -> None:
    await session.execute(
        update(SESSIONS)
        .where(SESSIONS.c.id == session_id, SESSIONS.c.revoked_at.is_(None))
        .values(last_seen_at=now, idle_expires_at=idle_expires_at)
    )


async def set_session_context(
    session: AsyncSession,
    session_id: uuid.UUID,
    *,
    tenant_id: uuid.UUID | None,
    campus_id: uuid.UUID | None,
) -> None:
    await session.execute(
        update(SESSIONS)
        .where(SESSIONS.c.id == session_id, SESSIONS.c.revoked_at.is_(None))
        .values(active_tenant_id=tenant_id, active_campus_id=campus_id)
    )


async def revoke_session(
    session: AsyncSession, session_id: uuid.UUID, reason: SessionRevokeReason, now: datetime
) -> int:
    result = await session.execute(
        update(SESSIONS)
        .where(SESSIONS.c.id == session_id, SESSIONS.c.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason=reason.value)
    )
    return int(result.rowcount)  # type: ignore[attr-defined]


async def revoke_user_sessions(
    session: AsyncSession, user_id: uuid.UUID, reason: SessionRevokeReason, now: datetime
) -> int:
    result = await session.execute(
        update(SESSIONS)
        .where(SESSIONS.c.user_id == user_id, SESSIONS.c.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason=reason.value)
    )
    return int(result.rowcount)  # type: ignore[attr-defined]


# --- Password reset tokens ----------------------------------------------------------------


async def replace_reset_token(
    session: AsyncSession,
    user_id: uuid.UUID,
    token_hash: str,
    *,
    now: datetime,
    expires_at: datetime,
) -> None:
    """Invalidate the user's open reset tokens and store a new one."""
    await session.execute(
        update(RESET_TOKENS)
        .where(
            RESET_TOKENS.c.user_id == user_id,
            RESET_TOKENS.c.used_at.is_(None),
            RESET_TOKENS.c.invalidated_at.is_(None),
        )
        .values(invalidated_at=now)
    )
    await session.execute(
        insert(RESET_TOKENS).values(
            id=uuid.uuid7(),
            user_id=user_id,
            token_hash=token_hash,
            created_at=now,
            expires_at=expires_at,
        )
    )


async def reset_token_by_hash(session: AsyncSession, token_hash: str) -> ResetTokenRow | None:
    row = (
        await session.execute(
            select(
                RESET_TOKENS.c.id,
                RESET_TOKENS.c.user_id,
                RESET_TOKENS.c.expires_at,
                RESET_TOKENS.c.used_at,
                RESET_TOKENS.c.invalidated_at,
            ).where(RESET_TOKENS.c.token_hash == token_hash)
        )
    ).one_or_none()
    return ResetTokenRow(*row) if row else None


async def consume_reset_token(session: AsyncSession, token_id: uuid.UUID, now: datetime) -> int:
    """Mark the token used if it is still open and unexpired (single use)."""
    result = await session.execute(
        update(RESET_TOKENS)
        .where(
            RESET_TOKENS.c.id == token_id,
            RESET_TOKENS.c.used_at.is_(None),
            RESET_TOKENS.c.invalidated_at.is_(None),
            RESET_TOKENS.c.expires_at > now,
        )
        .values(used_at=now)
    )
    return int(result.rowcount)  # type: ignore[attr-defined]


# --- Invitations --------------------------------------------------------------------------


async def invitation_by_hash(session: AsyncSession, token_hash: str) -> InvitationRow | None:
    row = (
        await session.execute(
            select(
                INVITATIONS.c.id,
                INVITATIONS.c.tenant_id,
                INVITATIONS.c.membership_id,
                MEMBERSHIPS.c.user_id,
                MEMBERSHIPS.c.status,
                INVITATIONS.c.expires_at,
                INVITATIONS.c.accepted_at,
                INVITATIONS.c.revoked_at,
            )
            .select_from(
                INVITATIONS.join(
                    MEMBERSHIPS,
                    (MEMBERSHIPS.c.id == INVITATIONS.c.membership_id)
                    & (MEMBERSHIPS.c.tenant_id == INVITATIONS.c.tenant_id),
                )
            )
            .where(INVITATIONS.c.token_hash == token_hash)
        )
    ).one_or_none()
    if row is None:
        return None
    return InvitationRow(
        row.id,
        row.tenant_id,
        row.membership_id,
        row.user_id,
        MembershipStatus(row.status),
        row.expires_at,
        row.accepted_at,
        row.revoked_at,
    )


async def accept_invitation(
    session: AsyncSession, tenant_id: uuid.UUID, invitation_id: uuid.UUID, now: datetime
) -> int:
    """Mark accepted if still open (concurrent acceptances: exactly one wins)."""
    result = await session.execute(
        update(INVITATIONS)
        .where(
            INVITATIONS.c.tenant_id == tenant_id,
            INVITATIONS.c.id == invitation_id,
            INVITATIONS.c.accepted_at.is_(None),
            INVITATIONS.c.revoked_at.is_(None),
            INVITATIONS.c.expires_at > now,
        )
        .values(accepted_at=now)
    )
    return int(result.rowcount)  # type: ignore[attr-defined]


async def activate_invited_user(
    session: AsyncSession, user_id: uuid.UUID, display_name: str | None, now: datetime
) -> int:
    """INVITED → ACTIVE (new account) or verify the email (existing account)."""
    values: dict[str, object] = {
        "email_verified_at": func.coalesce(USERS.c.email_verified_at, now),
        "version": USERS.c.version + 1,
    }
    if display_name is not None:
        values["display_name"] = display_name
        values["status"] = UserStatus.ACTIVE.value
    result = await session.execute(
        update(USERS)
        .where(USERS.c.id == user_id, USERS.c.status != UserStatus.DISABLED.value)
        .values(**values)
    )
    return int(result.rowcount)  # type: ignore[attr-defined]


async def tenant_name(session: AsyncSession, tenant_id: uuid.UUID) -> tuple[str, str] | None:
    row = (
        await session.execute(
            select(TENANTS.c.name, TENANTS.c.status).where(TENANTS.c.id == tenant_id)
        )
    ).one_or_none()
    return (row.name, row.status) if row else None


def tenant_ids(memberships: Sequence[MembershipView]) -> list[uuid.UUID]:
    return [membership.tenant_id for membership in memberships]
