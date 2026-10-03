"""Member administration data access (T01-08; D8-1, D8-3, D8-4).

Core statements in the request's tenant transaction. Every statement filters
on the trusted ``tenant_id`` explicitly, and Row-Level Security enforces the
same boundary: another tenant's membership, invitation or campus is simply
not found. ``users`` rows are visible only for members of the active tenant
(0004) and inserted only through the D8-1 invitee key (0008).
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, cast

from sqlalchemy import ColumnElement, Table, and_, func, insert, or_, select, true, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_id
from app.core.pagination import SortField
from app.modules.access.models import MembershipRole, Role
from app.modules.identity.domain import CampusScope, MembershipStatus, UserStatus
from app.modules.identity.models import MembershipCampus, TenantMembership, User, UserInvitation
from app.modules.institute.models import Campus

USERS = cast(Table, User.__table__)
MEMBERSHIPS = cast(Table, TenantMembership.__table__)
MEMBERSHIP_CAMPUSES = cast(Table, MembershipCampus.__table__)
INVITATIONS = cast(Table, UserInvitation.__table__)
CAMPUSES = cast(Table, Campus.__table__)
ROLES = cast(Table, Role.__table__)
MEMBERSHIP_ROLES = cast(Table, MembershipRole.__table__)

SORT_COLUMNS: Final = {
    "display_name": USERS.c.display_name,
    "email": USERS.c.email,
    "status": MEMBERSHIPS.c.status,
    "created_at": MEMBERSHIPS.c.created_at,
}


def _rowcount(result: object) -> int:
    return cast(CursorResult[object], result).rowcount


def escape_like(value: str) -> str:
    r"""``value`` as a literal inside an ``ILIKE`` pattern (escape character ``\``)."""
    return value.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


@dataclass(frozen=True, slots=True)
class MemberRole:
    id: uuid.UUID
    name: str
    is_system: bool


@dataclass(frozen=True, slots=True)
class MemberRow:
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    display_name: str
    user_status: UserStatus
    status: MembershipStatus
    campus_scope: CampusScope
    created_at: datetime
    joined_at: datetime | None
    version: int
    roles: tuple[MemberRole, ...] = ()
    campus_ids: tuple[uuid.UUID, ...] = ()
    campus_id: uuid.UUID | None = None  # memberships are tenant-wide (AuthzResource)


_COLUMNS = (
    MEMBERSHIPS.c.id,
    MEMBERSHIPS.c.tenant_id,
    MEMBERSHIPS.c.user_id,
    USERS.c.email,
    USERS.c.display_name,
    USERS.c.status.label("user_status"),
    MEMBERSHIPS.c.status,
    MEMBERSHIPS.c.campus_scope,
    MEMBERSHIPS.c.created_at,
    MEMBERSHIPS.c.joined_at,
    MEMBERSHIPS.c.version,
)
_FROM = MEMBERSHIPS.join(USERS, USERS.c.id == MEMBERSHIPS.c.user_id)


async def _details(db: AsyncSession, tenant_id: uuid.UUID, rows: Sequence[Any]) -> list[MemberRow]:
    ids = [row.id for row in rows]
    roles: dict[uuid.UUID, list[MemberRole]] = {member_id: [] for member_id in ids}
    campuses: dict[uuid.UUID, list[uuid.UUID]] = {member_id: [] for member_id in ids}
    if ids:
        role_rows = await db.execute(
            select(MEMBERSHIP_ROLES.c.membership_id, ROLES.c.id, ROLES.c.name, ROLES.c.is_system)
            .select_from(
                MEMBERSHIP_ROLES.join(
                    ROLES,
                    (ROLES.c.tenant_id == MEMBERSHIP_ROLES.c.tenant_id)
                    & (ROLES.c.id == MEMBERSHIP_ROLES.c.role_id),
                )
            )
            .where(
                MEMBERSHIP_ROLES.c.tenant_id == tenant_id,
                MEMBERSHIP_ROLES.c.membership_id.in_(ids),
            )
            .order_by(ROLES.c.is_system.desc(), ROLES.c.name, ROLES.c.id)
        )
        for row in role_rows:
            roles[row.membership_id].append(MemberRole(row.id, row.name, row.is_system))
        campus_rows = await db.execute(
            select(MEMBERSHIP_CAMPUSES.c.membership_id, MEMBERSHIP_CAMPUSES.c.campus_id)
            .where(
                MEMBERSHIP_CAMPUSES.c.tenant_id == tenant_id,
                MEMBERSHIP_CAMPUSES.c.membership_id.in_(ids),
                MEMBERSHIP_CAMPUSES.c.removed_at.is_(None),
            )
            .order_by(MEMBERSHIP_CAMPUSES.c.campus_id)
        )
        for row in campus_rows:
            campuses[row.membership_id].append(row.campus_id)
    return [
        MemberRow(
            id=row.id,
            tenant_id=row.tenant_id,
            user_id=row.user_id,
            email=row.email,
            display_name=row.display_name,
            user_status=UserStatus(row.user_status),
            status=MembershipStatus(row.status),
            campus_scope=CampusScope(row.campus_scope),
            created_at=row.created_at,
            joined_at=row.joined_at,
            version=row.version,
            roles=tuple(roles[row.id]),
            campus_ids=tuple(campuses[row.id]) if row.campus_scope == "SELECTED" else (),
        )
        for row in rows
    ]


# --- Directory ---------------------------------------------------------------------------


async def list_members(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    search: str | None,
    status: MembershipStatus | None,
    sort: Sequence[SortField],
    limit: int,
    offset: int,
) -> tuple[list[MemberRow], int]:
    conditions: list[ColumnElement[bool]] = [MEMBERSHIPS.c.tenant_id == tenant_id]
    if search:
        pattern = f"%{escape_like(search)}%"
        conditions.append(
            or_(
                USERS.c.display_name.ilike(pattern, escape="\\"),
                USERS.c.email.ilike(pattern, escape="\\"),
            )
        )
    if status is not None:
        conditions.append(MEMBERSHIPS.c.status == status.value)
    where = and_(*conditions)
    total = int(
        (await db.execute(select(func.count()).select_from(_FROM).where(where))).scalar_one()
    )
    order = [
        SORT_COLUMNS[field.name].desc() if field.descending else SORT_COLUMNS[field.name].asc()
        for field in sort
    ]
    rows = (
        await db.execute(
            select(*_COLUMNS)
            .select_from(_FROM)
            .where(where)
            .order_by(*order, MEMBERSHIPS.c.id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return await _details(db, tenant_id, rows), total


async def member(
    db: AsyncSession, tenant_id: uuid.UUID, membership_id: uuid.UUID
) -> MemberRow | None:
    row = (
        await db.execute(
            select(*_COLUMNS)
            .select_from(_FROM)
            .where(MEMBERSHIPS.c.tenant_id == tenant_id, MEMBERSHIPS.c.id == membership_id)
        )
    ).one_or_none()
    if row is None:
        return None
    return (await _details(db, tenant_id, [row]))[0]


async def membership_of_user(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> uuid.UUID | None:
    return cast(
        uuid.UUID | None,
        await db.scalar(
            select(MEMBERSHIPS.c.id).where(
                MEMBERSHIPS.c.tenant_id == tenant_id, MEMBERSHIPS.c.user_id == user_id
            )
        ),
    )


async def tenant_campuses(
    db: AsyncSession, tenant_id: uuid.UUID, campus_ids: Iterable[uuid.UUID]
) -> set[uuid.UUID]:
    """The given campus IDs that exist in the tenant (others are not found)."""
    ids = list(campus_ids)
    if not ids:
        return set()
    rows = await db.scalars(
        select(CAMPUSES.c.id).where(CAMPUSES.c.tenant_id == tenant_id, CAMPUSES.c.id.in_(ids))
    )
    return set(rows)


# --- Invitation writes ----------------------------------------------------------------------


async def insert_invited_user(
    db: AsyncSession, user_id: uuid.UUID, *, email: str, display_name: str
) -> None:
    """D8-1: only inside the invitee scope that ``members`` opens for this ``user_id``."""
    await db.execute(
        insert(USERS).values(
            id=user_id,
            email=email,
            display_name=display_name,
            status=UserStatus.INVITED.value,
            version=1,
        )
    )


async def insert_membership(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    campus_scope: CampusScope,
    invited_by: uuid.UUID | None,
) -> uuid.UUID:
    membership_id = new_id()
    await db.execute(
        insert(MEMBERSHIPS).values(
            id=membership_id,
            tenant_id=tenant_id,
            user_id=user_id,
            status=MembershipStatus.INVITED.value,
            campus_scope=campus_scope.value,
            invited_by=invited_by,
            version=1,
        )
    )
    return membership_id


async def replace_campuses(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    membership_id: uuid.UUID,
    campus_ids: Iterable[uuid.UUID],
    now: datetime,
) -> None:
    """Make ``campus_ids`` the membership's selected campuses.

    Rows are never deleted (T01-04 D16): campuses leaving the selection get
    ``removed_at``; campuses (re)joining it are inserted or have it cleared.
    """
    wanted = set(campus_ids)
    mine = (MEMBERSHIP_CAMPUSES.c.tenant_id == tenant_id) & (
        MEMBERSHIP_CAMPUSES.c.membership_id == membership_id
    )
    await db.execute(
        update(MEMBERSHIP_CAMPUSES)
        .where(
            mine,
            MEMBERSHIP_CAMPUSES.c.removed_at.is_(None),
            MEMBERSHIP_CAMPUSES.c.campus_id.not_in(wanted) if wanted else true(),
        )
        .values(removed_at=now, updated_at=func.now())
    )
    if not wanted:
        return
    await db.execute(
        update(MEMBERSHIP_CAMPUSES)
        .where(
            mine,
            MEMBERSHIP_CAMPUSES.c.removed_at.is_not(None),
            MEMBERSHIP_CAMPUSES.c.campus_id.in_(wanted),
        )
        .values(removed_at=None, updated_at=func.now())
    )
    present = set(await db.scalars(select(MEMBERSHIP_CAMPUSES.c.campus_id).where(mine)))
    values = [
        {"id": new_id(), "tenant_id": tenant_id, "membership_id": membership_id, "campus_id": c}
        for c in sorted(wanted - present)
    ]
    if values:
        await db.execute(insert(MEMBERSHIP_CAMPUSES), values)


async def insert_invitation(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    membership_id: uuid.UUID,
    *,
    token_hash: str,
    expires_at: datetime,
) -> None:
    await db.execute(
        insert(INVITATIONS).values(
            id=new_id(),
            tenant_id=tenant_id,
            membership_id=membership_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )


async def revoke_open_invitations(
    db: AsyncSession, tenant_id: uuid.UUID, membership_id: uuid.UUID, now: datetime
) -> int:
    result = await db.execute(
        update(INVITATIONS)
        .where(
            INVITATIONS.c.tenant_id == tenant_id,
            INVITATIONS.c.membership_id == membership_id,
            INVITATIONS.c.accepted_at.is_(None),
            INVITATIONS.c.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    return _rowcount(result)


# --- Lifecycle and campus scope (optimistic) ----------------------------------------------------


async def set_status(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    membership_id: uuid.UUID,
    *,
    version: int,
    current: MembershipStatus,
    target: MembershipStatus,
) -> int:
    """0 when the version is stale or the status changed meanwhile."""
    result = await db.execute(
        update(MEMBERSHIPS)
        .where(
            MEMBERSHIPS.c.tenant_id == tenant_id,
            MEMBERSHIPS.c.id == membership_id,
            MEMBERSHIPS.c.version == version,
            MEMBERSHIPS.c.status == current.value,
        )
        .values(status=target.value, version=MEMBERSHIPS.c.version + 1, updated_at=func.now())
    )
    return _rowcount(result)


async def set_campus_scope(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    membership_id: uuid.UUID,
    *,
    version: int,
    scope: CampusScope,
) -> int:
    result = await db.execute(
        update(MEMBERSHIPS)
        .where(
            MEMBERSHIPS.c.tenant_id == tenant_id,
            MEMBERSHIPS.c.id == membership_id,
            MEMBERSHIPS.c.version == version,
        )
        .values(campus_scope=scope.value, version=MEMBERSHIPS.c.version + 1, updated_at=func.now())
    )
    return _rowcount(result)
