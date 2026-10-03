"""Platform (T01-07, D7-9) and tenant (T01-08, D8-2) audit reads (ADR-0013).

``GET /api/v1/platform/audit-events`` under ``audit.read`` (platform realm).
Row-Level Security already lets the platform realm read every event
(``audit_events_platform_read``); this service adds the filters, offset
pagination (D13) and newest-first ordering. Metadata was redacted when it was
written. Reading is not itself audited in T01.

``GET /api/v1/audit-events`` under the tenant ``audit.read`` (D8-2): only
events written **in the tenant realm** for the trusted tenant. The
``audit_events_tenant_read`` policy enforces it in the database (migration
0008); the query states the same predicate explicitly.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from sqlalchemy import ColumnElement, Table, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import AuditCategory, AuditEvent
from app.core.authz import authorize
from app.core.context import Realm, current_context
from app.core.db.session import context_transaction
from app.modules.audit.permissions import PLATFORM_AUDIT_READ, TENANT_AUDIT_READ

EVENTS = cast(Table, AuditEvent.__table__)


@dataclass(frozen=True, slots=True)
class AuditFilters:
    category: AuditCategory | None = None
    event_type: str | None = None
    tenant_id: uuid.UUID | None = None
    principal_id: uuid.UUID | None = None
    target_type: str | None = None
    target_id: uuid.UUID | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None


@dataclass(frozen=True, slots=True)
class AuditEventRow:
    id: uuid.UUID
    created_at: datetime
    realm: str
    category: str
    event_type: str
    principal_id: uuid.UUID | None
    tenant_id: uuid.UUID | None
    target_type: str | None
    target_id: uuid.UUID | None
    request_id: uuid.UUID
    metadata: dict[str, Any]


def _conditions(filters: AuditFilters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if filters.category is not None:
        conditions.append(EVENTS.c.category == filters.category.value)
    if filters.event_type is not None:
        conditions.append(EVENTS.c.event_type == filters.event_type)
    if filters.tenant_id is not None:
        # Events in the tenant, or platform events about it (D7-9).
        conditions.append(
            or_(
                EVENTS.c.tenant_id == filters.tenant_id,
                and_(EVENTS.c.target_type == "tenant", EVENTS.c.target_id == filters.tenant_id),
            )
        )
    if filters.principal_id is not None:
        conditions.append(EVENTS.c.principal_id == filters.principal_id)
    if filters.target_type is not None:
        conditions.append(EVENTS.c.target_type == filters.target_type)
    if filters.target_id is not None:
        conditions.append(EVENTS.c.target_id == filters.target_id)
    if filters.created_from is not None:
        conditions.append(EVENTS.c.created_at >= filters.created_from)
    if filters.created_to is not None:
        conditions.append(EVENTS.c.created_at < filters.created_to)
    return conditions


async def _page(
    db: AsyncSession,
    filters: AuditFilters,
    *,
    limit: int,
    offset: int,
    extra: list[ColumnElement[bool]] | None = None,
) -> tuple[list[AuditEventRow], int]:
    conditions = [*_conditions(filters), *(extra or [])]
    total_query = select(func.count()).select_from(EVENTS)
    query = select(
        EVENTS.c.id,
        EVENTS.c.created_at,
        EVENTS.c.realm,
        EVENTS.c.category,
        EVENTS.c.event_type,
        EVENTS.c.principal_id,
        EVENTS.c.tenant_id,
        EVENTS.c.target_type,
        EVENTS.c.target_id,
        EVENTS.c.request_id,
        EVENTS.c.metadata,
    )
    if conditions:
        total_query = total_query.where(and_(*conditions))
        query = query.where(and_(*conditions))
    query = (
        query.order_by(EVENTS.c.created_at.desc(), EVENTS.c.id.desc()).limit(limit).offset(offset)
    )
    total = int((await db.execute(total_query)).scalar_one())
    rows = [AuditEventRow(*row) for row in (await db.execute(query)).all()]
    return rows, total


async def list_platform_events(
    factory: async_sessionmaker[AsyncSession], filters: AuditFilters, *, limit: int, offset: int
) -> tuple[list[AuditEventRow], int]:
    context = current_context()
    authorize(context, PLATFORM_AUDIT_READ)
    async with context_transaction(factory, context) as db:
        return await _page(db, filters, limit=limit, offset=offset)


async def list_tenant_events(
    factory: async_sessionmaker[AsyncSession], filters: AuditFilters, *, limit: int, offset: int
) -> tuple[list[AuditEventRow], int]:
    """The active institute's tenant-realm events (D8-2); ``filters.tenant_id`` is ignored."""
    context = current_context()
    authorize(context, TENANT_AUDIT_READ)
    scoped = AuditFilters(
        category=filters.category,
        event_type=filters.event_type,
        principal_id=filters.principal_id,
        target_type=filters.target_type,
        target_id=filters.target_id,
        created_from=filters.created_from,
        created_to=filters.created_to,
    )
    async with context_transaction(factory, context) as db:
        return await _page(
            db,
            scoped,
            limit=limit,
            offset=offset,
            extra=[EVENTS.c.realm == Realm.TENANT.value, EVENTS.c.tenant_id == context.tenant_id],
        )
