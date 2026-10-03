"""Platform audit read route (T01-07, D7-9). Mounted by ``app.api.platform``.

``GET /api/v1/platform/audit-events`` — ``audit.read`` in the platform realm.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request

from app.core.audit import AuditCategory
from app.core.audit.events import EVENT_TYPE_MAX_LENGTH, TARGET_TYPE_MAX_LENGTH
from app.core.authz import require_permission
from app.core.pagination import Pagination
from app.core.schemas import ListEnvelope, ResponseModel
from app.modules.audit.permissions import PLATFORM_AUDIT_READ
from app.modules.audit.service import AuditFilters, list_platform_events


class AuditEventOut(ResponseModel):
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
    """Redacted when the event was written (ADR-0013 §3)."""


audit_routes = APIRouter(prefix="/audit-events", tags=["platform-audit"])


@audit_routes.get("", dependencies=[require_permission(PLATFORM_AUDIT_READ)])
async def list_audit_events(
    request: Request,
    page: Pagination,
    category: AuditCategory | None = None,
    event_type: Annotated[str | None, Query(max_length=EVENT_TYPE_MAX_LENGTH)] = None,
    tenant_id: uuid.UUID | None = None,
    principal_id: uuid.UUID | None = None,
    target_type: Annotated[str | None, Query(max_length=TARGET_TYPE_MAX_LENGTH)] = None,
    target_id: uuid.UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> ListEnvelope[AuditEventOut]:
    """Audit events, newest first. ``tenant_id`` matches events in the tenant and about it."""
    rows, total = await list_platform_events(
        request.app.state.sessionmaker,
        AuditFilters(
            category=category,
            event_type=event_type,
            tenant_id=tenant_id,
            principal_id=principal_id,
            target_type=target_type,
            target_id=target_id,
            created_from=created_from,
            created_to=created_to,
        ),
        limit=page.limit,
        offset=page.offset,
    )
    return ListEnvelope.build(
        [AuditEventOut.model_validate(row) for row in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )
