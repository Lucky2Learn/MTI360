"""Platform user administration data access (T01-07; D7-2, D7-3, D7-5).

Core statements only. Which rows they reach is decided by the transaction
kind (``lookup.admin_target_transaction`` for writes, the anonymous lookup
with a token key for invitation acceptance) and Row-Level Security
(migrations ``0006`` and ``0007``). Every authenticated platform principal
may read the directory (``platform_users`` and ``platform_user_roles``);
credentials, MFA factors and other users' sessions stay out of reach.
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, cast

from sqlalchemy import (
    ColumnElement,
    Table,
    and_,
    delete,
    exists,
    func,
    insert,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_id
from app.core.pagination import SortField
from app.modules.platform_identity.domain import PlatformUserStatus
from app.modules.platform_identity.models import (
    PlatformUser,
    PlatformUserCredential,
    PlatformUserInvitation,
    PlatformUserRole,
)
from app.modules.platform_identity.roles import GUARDIAN_ROLE, PlatformRole

USERS = cast(Table, PlatformUser.__table__)
ROLES = cast(Table, PlatformUserRole.__table__)
CREDENTIALS = cast(Table, PlatformUserCredential.__table__)
INVITATIONS = cast(Table, PlatformUserInvitation.__table__)

GUARDIAN_LOCK: Final = 7_007_000_001
"""Transaction advisory lock serialising changes that could remove the last active
guardian (D7-5): concurrent suspensions or demotions cannot both pass."""

SORT_COLUMNS: Final = {
    "display_name": USERS.c.display_name,
    "email": USERS.c.email,
    "status": USERS.c.status,
    "created_at": USERS.c.created_at,
}


def escape_like(value: str) -> str:
    r"""``value`` as a literal inside an ``ILIKE`` pattern (escape character ``\``)."""
    return value.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def _rowcount(result: object) -> int:
    return cast(CursorResult[object], result).rowcount


@dataclass(frozen=True, slots=True)
class AdminUserRow:
    id: uuid.UUID
    email: str
    display_name: str
    status: PlatformUserStatus
    roles: tuple[PlatformRole, ...]
    created_at: datetime
    updated_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class InvitationRow:
    id: uuid.UUID
    user_id: uuid.UUID
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None


def _roles_column() -> Any:
    return (
        select(func.coalesce(func.array_agg(ROLES.c.role_code), text("ARRAY[]::varchar[]")))
        .where(ROLES.c.platform_user_id == USERS.c.id)
        .scalar_subquery()
    )


def _row(row: Any) -> AdminUserRow:
    return AdminUserRow(
        id=row.id,
        email=row.email,
        display_name=row.display_name,
        status=PlatformUserStatus(row.status),
        roles=tuple(sorted(PlatformRole(code) for code in row.roles)),
        created_at=row.created_at,
        updated_at=row.updated_at,
        version=row.version,
    )


def _columns() -> tuple[Any, ...]:
    return (
        USERS.c.id,
        USERS.c.email,
        USERS.c.display_name,
        USERS.c.status,
        _roles_column().label("roles"),
        USERS.c.created_at,
        USERS.c.updated_at,
        USERS.c.version,
    )


# --- Directory --------------------------------------------------------------------------------


async def list_users(
    db: AsyncSession,
    *,
    search: str | None,
    status: PlatformUserStatus | None,
    role: PlatformRole | None,
    sort: Sequence[SortField],
    limit: int,
    offset: int,
) -> tuple[list[AdminUserRow], int]:
    conditions: list[ColumnElement[bool]] = []
    if search:
        pattern = f"%{escape_like(search)}%"
        conditions.append(
            or_(
                USERS.c.display_name.ilike(pattern, escape="\\"),
                USERS.c.email.ilike(pattern, escape="\\"),
            )
        )
    if status is not None:
        conditions.append(USERS.c.status == status.value)
    if role is not None:
        conditions.append(
            exists().where(ROLES.c.platform_user_id == USERS.c.id, ROLES.c.role_code == role.value)
        )
    where = and_(*conditions) if conditions else None
    total_query = select(func.count()).select_from(USERS)
    query = select(*_columns())
    if where is not None:
        total_query = total_query.where(where)
        query = query.where(where)
    order = [
        SORT_COLUMNS[field.name].desc() if field.descending else SORT_COLUMNS[field.name].asc()
        for field in sort
    ]
    query = query.order_by(*order, USERS.c.id).limit(limit).offset(offset)
    total = int((await db.execute(total_query)).scalar_one())
    rows = (await db.execute(query)).all()
    return [_row(row) for row in rows], total


async def user(db: AsyncSession, user_id: uuid.UUID) -> AdminUserRow | None:
    row = (await db.execute(select(*_columns()).where(USERS.c.id == user_id))).one_or_none()
    return _row(row) if row else None


async def email_taken(db: AsyncSession, email: str) -> bool:
    return bool(await db.scalar(select(exists().where(USERS.c.email == email))))


async def active_guardians(db: AsyncSession, *, excluding: uuid.UUID) -> int:
    """Active guardian-role users other than ``excluding`` (under :func:`lock_guardians`)."""
    query = (
        select(func.count())
        .select_from(USERS.join(ROLES, ROLES.c.platform_user_id == USERS.c.id))
        .where(
            ROLES.c.role_code == GUARDIAN_ROLE.value,
            USERS.c.status == PlatformUserStatus.ACTIVE.value,
            USERS.c.id != excluding,
        )
    )
    return int((await db.execute(query)).scalar_one())


async def lock_guardians(db: AsyncSession) -> None:
    await db.execute(select(func.pg_advisory_xact_lock(GUARDIAN_LOCK)))


# --- Writes (administration target transaction) --------------------------------------------------


async def insert_user(
    db: AsyncSession, user_id: uuid.UUID, *, email: str, display_name: str
) -> None:
    await db.execute(
        insert(USERS).values(
            id=user_id,
            email=email,
            display_name=display_name,
            status=PlatformUserStatus.INVITED.value,
            version=1,
        )
    )


async def update_user(
    db: AsyncSession, user_id: uuid.UUID, *, version: int, values: dict[str, object]
) -> int:
    """Optimistic update: 0 when the version is stale (or the row is not reachable)."""
    result = await db.execute(
        update(USERS)
        .where(USERS.c.id == user_id, USERS.c.version == version)
        .values(**values, version=USERS.c.version + 1, updated_at=func.now())
    )
    return _rowcount(result)


async def set_roles(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    add: Iterable[PlatformRole],
    remove: Iterable[PlatformRole],
) -> None:
    removed = [role.value for role in remove]
    if removed:
        await db.execute(
            delete(ROLES).where(ROLES.c.platform_user_id == user_id, ROLES.c.role_code.in_(removed))
        )
    added = [{"id": new_id(), "platform_user_id": user_id, "role_code": role.value} for role in add]
    if added:
        await db.execute(insert(ROLES), added)


# --- Invitations ---------------------------------------------------------------------------


async def insert_invitation(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    token_hash: str,
    expires_at: datetime,
    invited_by: uuid.UUID | None,
) -> uuid.UUID:
    invitation_id = new_id()
    await db.execute(
        insert(INVITATIONS).values(
            id=invitation_id,
            platform_user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            invited_by=invited_by,
        )
    )
    return invitation_id


async def revoke_open_invitations(db: AsyncSession, user_id: uuid.UUID, now: datetime) -> int:
    result = await db.execute(
        update(INVITATIONS)
        .where(
            INVITATIONS.c.platform_user_id == user_id,
            INVITATIONS.c.accepted_at.is_(None),
            INVITATIONS.c.revoked_at.is_(None),
        )
        .values(revoked_at=now, updated_at=func.now())
    )
    return _rowcount(result)


async def invitation_history(db: AsyncSession, user_id: uuid.UUID) -> tuple[bool, bool]:
    """(was ever invited, ever accepted) for one user."""
    row = (
        await db.execute(
            select(
                func.count(),
                func.count(INVITATIONS.c.accepted_at),
            ).where(INVITATIONS.c.platform_user_id == user_id)
        )
    ).one()
    return int(row[0]) > 0, int(row[1]) > 0


async def invitation_by_hash(db: AsyncSession, token_hash: str) -> InvitationRow | None:
    row = (
        await db.execute(
            select(
                INVITATIONS.c.id,
                INVITATIONS.c.platform_user_id,
                INVITATIONS.c.expires_at,
                INVITATIONS.c.accepted_at,
                INVITATIONS.c.revoked_at,
            ).where(INVITATIONS.c.token_hash == token_hash)
        )
    ).one_or_none()
    return InvitationRow(*row) if row else None


async def accept_invitation(db: AsyncSession, invitation_id: uuid.UUID, now: datetime) -> int:
    """Mark the invitation accepted if it is still open and unexpired (single use)."""
    result = await db.execute(
        update(INVITATIONS)
        .where(
            INVITATIONS.c.id == invitation_id,
            INVITATIONS.c.accepted_at.is_(None),
            INVITATIONS.c.revoked_at.is_(None),
            INVITATIONS.c.expires_at > now,
        )
        .values(accepted_at=now, updated_at=func.now())
    )
    return _rowcount(result)


async def activate_invited_user(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        update(USERS)
        .where(USERS.c.id == user_id, USERS.c.status == PlatformUserStatus.INVITED.value)
        .values(
            status=PlatformUserStatus.ACTIVE.value,
            version=USERS.c.version + 1,
            updated_at=func.now(),
        )
    )
    return _rowcount(result)


async def create_credential(
    db: AsyncSession, user_id: uuid.UUID, password_hash: str, now: datetime
) -> None:
    await db.execute(
        insert(CREDENTIALS).values(
            id=new_id(),
            platform_user_id=user_id,
            password_hash=password_hash,
            password_changed_at=now,
        )
    )
