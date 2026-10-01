"""Audit foundation (T01-02; ADR-0013): the append-only ``audit_events`` table.

* :func:`write_audit_event` — admin, data-access and domain events, in the
  request transaction.
"""

from app.core.audit.events import AuditCategory, AuditEventType, AuditTarget
from app.core.audit.metadata import AuditMetadataError, safe_metadata
from app.core.audit.models import AuditEvent
from app.core.audit.writer import write_audit_event

__all__ = [
    "AuditCategory",
    "AuditEvent",
    "AuditEventType",
    "AuditMetadataError",
    "AuditTarget",
    "safe_metadata",
    "write_audit_event",
]
