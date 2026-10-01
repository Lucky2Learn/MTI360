"""Audit writer: events recorded in the request's own transaction (T01-02; ADR-0013 §4).

Admin, data-access and domain events are part of the change they describe
(T01-00 decision D22)::

    async def suspend_campus(session: DbSession, ...) -> None:
        campus.status = "suspended"
        await write_audit_event(session, CAMPUS_SUSPENDED, target=AuditTarget("campus", campus.id))

* The event is inserted through the caller's session, inside the request
  transaction: no other connection is opened, and the mutation and its audit
  record commit or roll back together. If the insert fails, the request fails.
* Realm, tenant, principal and request ID come from the trusted
  :class:`~app.core.context.RequestContext`, never from arguments; Row-Level
  Security additionally checks tenant and realm against the ``SET LOCAL``
  context of the transaction.
* Security events do not use this writer: they are recorded with
  :func:`app.core.audit.security.record_security_event` and committed after
  the request transaction, so that a rolled-back request still leaves its
  security trail.
"""

import uuid
from collections.abc import Mapping
from typing import Any, cast

from sqlalchemy import Table, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit.events import AuditCategory, AuditEventType, AuditTarget
from app.core.audit.metadata import safe_metadata
from app.core.audit.models import AuditEvent
from app.core.context import RequestContext, current_context
from app.core.ids import new_id

AUDIT_TABLE = cast(Table, AuditEvent.__table__)


def audit_row(
    context: RequestContext,
    event_type: AuditEventType,
    *,
    target: AuditTarget | None = None,
    metadata: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """The validated database row of one event (metadata already redacted)."""
    if not isinstance(event_type, AuditEventType):
        raise TypeError("event_type must be an AuditEventType")
    return {
        "id": new_id(),
        "request_id": context.request_id,
        "realm": context.realm.value,
        "tenant_id": context.tenant_id,
        "principal_id": context.principal_id,
        "category": event_type.category.value,
        "event_type": event_type.name,
        "target_type": target.type if target else None,
        "target_id": target.id if target else None,
        "metadata": safe_metadata(metadata),
    }


async def write_audit_event(
    session: AsyncSession,
    event_type: AuditEventType,
    *,
    target: AuditTarget | None = None,
    metadata: Mapping[str, object] | None = None,
) -> uuid.UUID:
    """Insert an audit event in the current request transaction; return its ID."""
    row = audit_row(current_context(), event_type, target=target, metadata=metadata)
    if event_type.category is AuditCategory.SECURITY:
        raise ValueError("security events are recorded with record_security_event()")
    if not session.in_transaction():
        raise RuntimeError("audit events are written inside the request transaction")
    # A plain INSERT: no RETURNING, so RLS checks only the insert policy.
    await session.execute(insert(AUDIT_TABLE).values(**row))
    return cast(uuid.UUID, row["id"])
