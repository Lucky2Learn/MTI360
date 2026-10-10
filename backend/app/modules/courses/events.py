"""Course catalogue audit events (Phase 02-1; ADR-0013 category ``domain``).

Metadata: the course code, changed field names and statuses only.
"""

from app.core.audit import AuditCategory, AuditEventType

_D = AuditCategory.DOMAIN

COURSE_CREATED = AuditEventType("course.created", _D)
COURSE_UPDATED = AuditEventType("course.updated", _D)
COURSE_STATUS_CHANGED = AuditEventType("course.status_changed", _D)
