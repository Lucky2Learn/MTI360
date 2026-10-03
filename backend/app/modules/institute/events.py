"""Campus administration audit events (T01-08; ADR-0013 category ``admin``)."""

from app.core.audit import AuditCategory, AuditEventType

_A = AuditCategory.ADMIN

CAMPUS_CREATED = AuditEventType("campus.created", _A)
CAMPUS_UPDATED = AuditEventType("campus.updated", _A)
