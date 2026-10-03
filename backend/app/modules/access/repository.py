"""RBAC data access (T01-05).

Core statements on the access tables. Every statement filters on the
trusted ``tenant_id`` explicitly, and Row-Level Security (migration ``0005``)
enforces the same boundary in the database: another tenant's role or
membership is simply not found.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Final, cast

from sqlalchemy import Table, delete, exists, func, insert, literal, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_id
from app.modules.access.models import MembershipRole, Role, RolePermission
from app.modules.identity.models import TenantMembership

ROLES = cast(Table, Role.__table__)
ROLE_PERMISSIONS = cast(Table, RolePermission.__table__)
MEMBERSHIP_ROLES = cast(Table, MembershipRole.__table__)
MEMBERSHIPS = cast(Table, TenantMembership.__table__)


@dataclass(frozen=True, slots=True)
class RoleRow:
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    is_system: bool
    version: int
    campus_id: uuid.UUID | None = None  # roles are tenant-wide (AuthzResource)
    template_code: str | None = None


@dataclass(frozen=True, slots=True)
class MembershipRow:
    id: uuid.UUID
    tenant_id: uuid.UUID
    campus_id: uuid.UUID | None = None  # memberships are tenant-wide (AuthzResource)
    user_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class AssignedRole:
    name: str
    is_system: bool
    permission_code: str | None


async def role(db: AsyncSession, tenant_id: uuid.UUID, role_id: uuid.UUID) -> RoleRow | None:
    row = (
        await db.execute(
            select(
                ROLES.c.id,
                ROLES.c.tenant_id,
                ROLES.c.name,
                ROLES.c.description,
                ROLES.c.is_system,
                ROLES.c.version,
                ROLES.c.template_code,
            ).where(ROLES.c.tenant_id == tenant_id, ROLES.c.id == role_id)
        )
    ).one_or_none()
    if row is None:
        return None
    return RoleRow(
        row.id,
        row.tenant_id,
        row.name,
        row.description,
        row.is_system,
        row.version,
        template_code=row.template_code,
    )


async def role_name_taken(
    db: AsyncSession, tenant_id: uuid.UUID, name: str, *, excluding: uuid.UUID | None = None
) -> bool:
    condition = (ROLES.c.tenant_id == tenant_id) & (func.lower(ROLES.c.name) == name.lower())
    if excluding is not None:
        condition &= ROLES.c.id != excluding
    return bool(await db.scalar(select(exists().where(condition))))


async def role_permission_codes(
    db: AsyncSession, tenant_id: uuid.UUID, role_id: uuid.UUID
) -> frozenset[str]:
    rows = await db.scalars(
        select(ROLE_PERMISSIONS.c.permission_code).where(
            ROLE_PERMISSIONS.c.tenant_id == tenant_id, ROLE_PERMISSIONS.c.role_id == role_id
        )
    )
    return frozenset(rows)


async def insert_role(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    name: str,
    description: str | None,
    template_code: str | None = None,
) -> uuid.UUID:
    role_id = new_id()
    await db.execute(
        insert(ROLES).values(
            id=role_id,
            tenant_id=tenant_id,
            name=name,
            description=description,
            template_code=template_code,
            is_system=template_code is not None,
            version=1,
        )
    )
    return role_id


async def add_role_permissions(
    db: AsyncSession, tenant_id: uuid.UUID, role_id: uuid.UUID, codes: Iterable[str]
) -> None:
    values = [
        {"id": new_id(), "tenant_id": tenant_id, "role_id": role_id, "permission_code": code}
        for code in sorted(codes)
    ]
    if values:
        await db.execute(insert(ROLE_PERMISSIONS), values)


async def remove_role_permissions(
    db: AsyncSession, tenant_id: uuid.UUID, role_id: uuid.UUID, codes: Iterable[str]
) -> None:
    codes = list(codes)
    if codes:
        await db.execute(
            delete(ROLE_PERMISSIONS).where(
                ROLE_PERMISSIONS.c.tenant_id == tenant_id,
                ROLE_PERMISSIONS.c.role_id == role_id,
                ROLE_PERMISSIONS.c.permission_code.in_(codes),
            )
        )


async def update_role(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    role_id: uuid.UUID,
    *,
    expected_version: int,
    name: str,
    description: str | None,
) -> bool:
    """Optimistic update of a custom role; ``False`` when the version is stale."""
    result = await db.execute(
        update(ROLES)
        .where(
            ROLES.c.tenant_id == tenant_id,
            ROLES.c.id == role_id,
            ROLES.c.version == expected_version,
            ROLES.c.is_system.is_(False),
        )
        .values(
            name=name, description=description, version=ROLES.c.version + 1, updated_at=func.now()
        )
    )
    return bool(result.rowcount)  # type: ignore[attr-defined]


async def delete_role(
    db: AsyncSession, tenant_id: uuid.UUID, role_id: uuid.UUID, *, expected_version: int
) -> bool:
    """Delete a custom role and its permissions; ``False`` when the version is stale."""
    current = await db.scalar(
        select(ROLES.c.version)
        .where(ROLES.c.tenant_id == tenant_id, ROLES.c.id == role_id)
        .with_for_update()
    )
    if current != expected_version:
        return False
    await db.execute(
        delete(ROLE_PERMISSIONS).where(
            ROLE_PERMISSIONS.c.tenant_id == tenant_id, ROLE_PERMISSIONS.c.role_id == role_id
        )
    )
    result = await db.execute(
        delete(ROLES).where(
            ROLES.c.tenant_id == tenant_id,
            ROLES.c.id == role_id,
            ROLES.c.is_system.is_(False),
        )
    )
    return bool(result.rowcount)  # type: ignore[attr-defined]


async def role_assigned(db: AsyncSession, tenant_id: uuid.UUID, role_id: uuid.UUID) -> bool:
    return bool(
        await db.scalar(
            select(
                exists().where(
                    MEMBERSHIP_ROLES.c.tenant_id == tenant_id,
                    MEMBERSHIP_ROLES.c.role_id == role_id,
                )
            )
        )
    )


async def membership(
    db: AsyncSession, tenant_id: uuid.UUID, membership_id: uuid.UUID
) -> MembershipRow | None:
    row = (
        await db.execute(
            select(MEMBERSHIPS.c.id, MEMBERSHIPS.c.tenant_id, MEMBERSHIPS.c.user_id).where(
                MEMBERSHIPS.c.tenant_id == tenant_id, MEMBERSHIPS.c.id == membership_id
            )
        )
    ).one_or_none()
    return None if row is None else MembershipRow(row.id, row.tenant_id, user_id=row.user_id)


async def membership_has_role(
    db: AsyncSession, tenant_id: uuid.UUID, membership_id: uuid.UUID, role_id: uuid.UUID
) -> bool:
    return bool(
        await db.scalar(
            select(
                exists().where(
                    MEMBERSHIP_ROLES.c.tenant_id == tenant_id,
                    MEMBERSHIP_ROLES.c.membership_id == membership_id,
                    MEMBERSHIP_ROLES.c.role_id == role_id,
                )
            )
        )
    )


async def assign(
    db: AsyncSession, tenant_id: uuid.UUID, membership_id: uuid.UUID, role_id: uuid.UUID
) -> None:
    await db.execute(
        insert(MEMBERSHIP_ROLES).values(
            id=new_id(), tenant_id=tenant_id, membership_id=membership_id, role_id=role_id
        )
    )


async def unassign(
    db: AsyncSession, tenant_id: uuid.UUID, membership_id: uuid.UUID, role_id: uuid.UUID
) -> bool:
    result = await db.execute(
        delete(MEMBERSHIP_ROLES).where(
            MEMBERSHIP_ROLES.c.tenant_id == tenant_id,
            MEMBERSHIP_ROLES.c.membership_id == membership_id,
            MEMBERSHIP_ROLES.c.role_id == role_id,
        )
    )
    return bool(result.rowcount)  # type: ignore[attr-defined]


async def assigned_roles(
    db: AsyncSession, tenant_id: uuid.UUID, membership_id: uuid.UUID
) -> list[AssignedRole]:
    """Each role of a membership with each of its permissions (one row per pair)."""
    statement = (
        select(ROLES.c.id, ROLES.c.name, ROLES.c.is_system, ROLE_PERMISSIONS.c.permission_code)
        .select_from(
            MEMBERSHIP_ROLES.join(
                ROLES,
                (ROLES.c.tenant_id == MEMBERSHIP_ROLES.c.tenant_id)
                & (ROLES.c.id == MEMBERSHIP_ROLES.c.role_id),
            ).outerjoin(
                ROLE_PERMISSIONS,
                (ROLE_PERMISSIONS.c.tenant_id == ROLES.c.tenant_id)
                & (ROLE_PERMISSIONS.c.role_id == ROLES.c.id),
            )
        )
        .where(
            MEMBERSHIP_ROLES.c.tenant_id == tenant_id,
            MEMBERSHIP_ROLES.c.membership_id == membership_id,
        )
    )
    rows = (await db.execute(statement)).all()
    return [AssignedRole(row.name, row.is_system, row.permission_code) for row in rows]


# --- Owner protection (T01-08, D8-4) ----------------------------------------------------------

OWNER_LOCK_CLASS: Final = 70_080_001
"""First key of the per-tenant transaction advisory lock that serialises changes able to
remove the last active owner (D8-4). The second key is derived from the tenant ID (both
``int4``); a hash collision between two tenants only serialises them."""


def _active_owner_memberships(tenant_id: uuid.UUID, owner_template: str) -> Any:
    return (
        select(MEMBERSHIP_ROLES.c.membership_id)
        .select_from(
            MEMBERSHIP_ROLES.join(
                ROLES,
                (ROLES.c.tenant_id == MEMBERSHIP_ROLES.c.tenant_id)
                & (ROLES.c.id == MEMBERSHIP_ROLES.c.role_id),
            ).join(
                MEMBERSHIPS,
                (MEMBERSHIPS.c.tenant_id == MEMBERSHIP_ROLES.c.tenant_id)
                & (MEMBERSHIPS.c.id == MEMBERSHIP_ROLES.c.membership_id),
            )
        )
        .where(
            MEMBERSHIP_ROLES.c.tenant_id == tenant_id,
            ROLES.c.is_system,
            ROLES.c.template_code == owner_template,
            MEMBERSHIPS.c.status == "ACTIVE",
        )
    )


async def is_active_owner(
    db: AsyncSession, tenant_id: uuid.UUID, membership_id: uuid.UUID, owner_template: str
) -> bool:
    owners = _active_owner_memberships(tenant_id, owner_template).subquery()
    return bool(await db.scalar(select(exists().where(owners.c.membership_id == membership_id))))


async def active_owner_count(
    db: AsyncSession, tenant_id: uuid.UUID, owner_template: str, *, excluding: uuid.UUID
) -> int:
    owners = _active_owner_memberships(tenant_id, owner_template).subquery()
    query = (
        select(func.count(func.distinct(owners.c.membership_id)))
        .select_from(owners)
        .where(owners.c.membership_id != excluding)
    )
    return int((await db.execute(query)).scalar_one())


async def lock_owners(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    await db.execute(
        select(func.pg_advisory_xact_lock(OWNER_LOCK_CLASS, func.hashtext(literal(str(tenant_id)))))
    )


# --- Role directory (T01-08 API) -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RoleDetail:
    id: uuid.UUID
    name: str
    description: str | None
    is_system: bool
    template_code: str | None
    version: int
    permissions: tuple[str, ...]
    member_count: int


async def roles_of_tenant(
    db: AsyncSession, tenant_id: uuid.UUID, *, role_id: uuid.UUID | None = None
) -> list[RoleDetail]:
    """The tenant's roles (system first, then by name) with permissions and member counts."""
    members = (
        select(func.count())
        .select_from(MEMBERSHIP_ROLES)
        .where(
            MEMBERSHIP_ROLES.c.tenant_id == ROLES.c.tenant_id,
            MEMBERSHIP_ROLES.c.role_id == ROLES.c.id,
        )
        .scalar_subquery()
    )
    statement = select(
        ROLES.c.id,
        ROLES.c.name,
        ROLES.c.description,
        ROLES.c.is_system,
        ROLES.c.template_code,
        ROLES.c.version,
        members.label("member_count"),
    ).where(ROLES.c.tenant_id == tenant_id)
    if role_id is not None:
        statement = statement.where(ROLES.c.id == role_id)
    rows = (
        await db.execute(statement.order_by(ROLES.c.is_system.desc(), ROLES.c.name, ROLES.c.id))
    ).all()
    codes: dict[uuid.UUID, list[str]] = {row.id: [] for row in rows}
    if codes:
        for row in await db.execute(
            select(ROLE_PERMISSIONS.c.role_id, ROLE_PERMISSIONS.c.permission_code)
            .where(
                ROLE_PERMISSIONS.c.tenant_id == tenant_id,
                ROLE_PERMISSIONS.c.role_id.in_(list(codes)),
            )
            .order_by(ROLE_PERMISSIONS.c.permission_code)
        ):
            codes[row.role_id].append(row.permission_code)
    return [
        RoleDetail(
            row.id,
            row.name,
            row.description,
            row.is_system,
            row.template_code,
            row.version,
            tuple(codes[row.id]),
            int(row.member_count),
        )
        for row in rows
    ]
