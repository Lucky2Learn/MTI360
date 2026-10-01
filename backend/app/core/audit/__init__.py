"""Audit foundation (T01-02; ADR-0013): the append-only ``audit_events`` table.

* :func:`write_audit_event` — admin, data-access and domain events, in the
  request transaction.
* :func:`record_security_event` — security events, buffered during the
  request and committed after it (:mod:`app.core.audit.security`).
"""

from app.core.audit.events import AuditCategory, AuditEventType, AuditTarget
from app.core.audit.metadata import AuditMetadataError, safe_metadata
from app.core.audit.models import AuditEvent
from app.core.audit.security import record_security_event
from app.core.audit.writer import write_audit_event

__all__ = [
    "AuditCategory",
    "AuditEvent",
    "AuditEventType",
    "AuditMetadataError",
    "AuditTarget",
    "record_security_event",
    "safe_metadata",
    "write_audit_event",
]
