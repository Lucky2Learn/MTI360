"""Tenant administration data access (T01-07).

Core statements. ``tenants`` is readable and writable by the platform realm
(migration ``0003``); every tenant-owned row is reached only inside a scope
of :mod:`app.modules.tenants.scopes` (Row-Level Security, migration ``0007``).
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, cast

from sqlalchemy import ColumnElement, Table, and_, func, insert, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_id
from app.core.pagination import SortField
from app.modules.identity.domain import (
    CampusScope,
    MembershipStatus,
    SessionRevokeReason,
    UserStatus,
)
from app.modules.identity.models import TenantMembership, User, UserInvitation, UserSession
from app.modules.institute.models import Campus
from app.modules.platform_identity.admin_repository import escape_like
from app.modules.tenants.domain import INITIAL_STATUS, TenantStatus
from app.modules.tenants.models import Tenant

TENANTS = cast(Table, Tenant.__table__)
CAMPUSES = cast(Table, Campus.__table__)
USERS = cast(Table, User.__table__)
MEMBERSHIPS = cast(Table, TenantMembership.__table__)
INVITATIONS = cast(Table, UserInvitation.__table__)
SESSIONS = cast(Table, UserSession.__table__)

SORT_COLUMNS: Final = {
    "name": TENANTS.c.name,
    "status": TENANTS.c.status,
    "created_at": TENANTS.c.created_at,
}


def _rowcount(result: object) -> int:
    return cast(CursorResult[object], result).rowcount


@dataclass(frozen=True, slots=True)
class TenantRow:
    id: uuid.UUID
    name: str
    status: TenantStatus
    owner_membership_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class OwnerRow:
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    display_name: str
    user_status: UserStatus
    membership_status: MembershipStatus


_TENANT_COLUMNS = (
    TENANTS.c.id,
    TENANTS.c.name,
    TENANTS.c.status,
    TENANTS.c.owner_membership_id,
    TENANTS.c.created_at,
    TENANTS.c.updated_at,
    TENANTS.c.version,
)


def _tenant(row: Any) -> TenantRow:
    return TenantRow(
        row.id,
        row.name,
        TenantStatus(row.status),
        row.owner_membership_id,
        row.created_at,
        row.updated_at,
        row.version,
    )


# --- Registry ------------------------------------------------------------------------------


async def list_tenants(
    db: AsyncSession,
    *,
    search: str | None,
    status: TenantStatus | None,
    sort: Sequence[SortField],
    limit: int,
    offset: int,
) -> tuple[list[TenantRow], int]:
    conditions: list[ColumnElement[bool]] = []
    if search:
        conditions.append(TENANTS.c.name.ilike(f"%{escape_like(search)}%", escape="\\"))
    if status is not None:
        conditions.append(TENANTS.c.status == status.value)
    total_query = select(func.count()).select_from(TENANTS)
    query = select(*_TENANT_COLUMNS)
    if conditions:
        total_query = total_query.where(and_(*conditions))
        query = query.where(and_(*conditions))
    order = [
        SORT_COLUMNS[field.name].desc() if field.descending else SORT_COLUMNS[field.name].asc()
        for field in sort
    ]
    query = query.order_by(*order, TENANTS.c.id).limit(limit).offset(offset)
    total = int((await db.execute(total_query)).scalar_one())
    return [_tenant(row) for row in (await db.execute(query)).all()], total


async def tenant(db: AsyncSession, tenant_id: uuid.UUID) -> TenantRow | None:
    row = (
        await db.execute(select(*_TENANT_COLUMNS).where(TENANTS.c.id == tenant_id))
    ).one_or_none()
    return _tenant(row) if row else None


async def insert_tenant(db: AsyncSession, tenant_id: uuid.UUID, name: str) -> None:
    await db.execute(
        insert(TENANTS).values(id=tenant_id, name=name, status=INITIAL_STATUS.value, version=1)
    )


async def set_owner(db: AsyncSession, tenant_id: uuid.UUID, membership_id: uuid.UUID) -> None:
    """Part of creation: the version stays 1."""
    await db.execute(
        update(TENANTS).where(TENANTS.c.id == tenant_id).values(owner_membership_id=membership_id)
    )


async def set_status(
    db: AsyncSession, tenant_id: uuid.UUID, *, version: int, status: TenantStatus
) -> int:
    """Optimistic transition: 0 when the version is stale."""
    result = await db.execute(
        update(TENANTS)
        .where(TENANTS.c.id == tenant_id, TENANTS.c.version == version)
        .values(status=status.value, version=TENANTS.c.version + 1, updated_at=func.now())
    )
    return _rowcount(result)


async def revoke_tenant_sessions(db: AsyncSession, tenant_id: uuid.UUID, now: datetime) -> int:
    """D7-6: end every live session whose active institute is ``tenant_id``."""
    result = await db.execute(
        update(SESSIONS)
        .where(SESSIONS.c.active_tenant_id == tenant_id, SESSIONS.c.revoked_at.is_(None))
        .values(
            revoked_at=now,
            revoke_reason=SessionRevokeReason.TENANT_SUSPENDED.value,
            updated_at=func.now(),
        )
    )
    return _rowcount(result)


# --- Provisioning (inside ``scopes.provisioning_transaction``) ------------------------------


async def user_by_email(db: AsyncSession, email: str) -> tuple[uuid.UUID, UserStatus] | None:
    """An existing tenant identity (identity lookup transaction with the email key)."""
    row = (
        await db.execute(select(USERS.c.id, USERS.c.status).where(USERS.c.email == email))
    ).one_or_none()
    return (row.id, UserStatus(row.status)) if row else None


async def insert_campus(
    db: AsyncSession, tenant_id: uuid.UUID, *, name: str, code: str
) -> uuid.UUID:
    campus_id = new_id()
    await db.execute(
        insert(CAMPUSES).values(id=campus_id, tenant_id=tenant_id, name=name, code=code, version=1)
    )
    return campus_id


async def insert_invited_user(
    db: AsyncSession, user_id: uuid.UUID, *, email: str, display_name: str
) -> None:
    await db.execute(
        insert(USERS).values(
            id=user_id,
            email=email,
            display_name=display_name,
            status=UserStatus.INVITED.value,
            version=1,
        )
    )


async def insert_owner_membership(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> uuid.UUID:
    membership_id = new_id()
    await db.execute(
        insert(MEMBERSHIPS).values(
            id=membership_id,
            tenant_id=tenant_id,
            user_id=user_id,
            status=MembershipStatus.INVITED.value,
            campus_scope=CampusScope.ALL.value,
            version=1,
        )
    )
    return membership_id


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


# --- Owner (inside ``scopes.publish_owner``) ------------------------------------------------


async def owner(db: AsyncSession, membership_id: uuid.UUID) -> OwnerRow | None:
    row = (
        await db.execute(
            select(
                MEMBERSHIPS.c.id,
                MEMBERSHIPS.c.user_id,
                USERS.c.email,
                USERS.c.display_name,
                USERS.c.status,
                MEMBERSHIPS.c.status.label("membership_status"),
            )
            .select_from(MEMBERSHIPS.join(USERS, USERS.c.id == MEMBERSHIPS.c.user_id))
            .where(MEMBERSHIPS.c.id == membership_id)
        )
    ).one_or_none()
    if row is None:
        return None
    return OwnerRow(
        row.id,
        row.user_id,
        row.email,
        row.display_name,
        UserStatus(row.status),
        MembershipStatus(row.membership_status),
    )


async def revoke_open_invitations(db: AsyncSession, membership_id: uuid.UUID, now: datetime) -> int:
    result = await db.execute(
        update(INVITATIONS)
        .where(
            INVITATIONS.c.membership_id == membership_id,
            INVITATIONS.c.accepted_at.is_(None),
            INVITATIONS.c.revoked_at.is_(None),
        )
        .values(revoked_at=now, updated_at=func.now())
    )
    return _rowcount(result)
