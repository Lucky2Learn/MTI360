"""Application audit events (Phase 02-2; ADR-0013 category ``domain``, ADR-0021 §12).

Metadata: statuses, field names and booleans only. Never a name, contact
detail, identifier number, reason or note text.
"""

from app.core.audit import AuditCategory, AuditEventType

_D = AuditCategory.DOMAIN

APPLICATION_CREATED = AuditEventType("application.created", _D)
APPLICATION_UPDATED = AuditEventType("application.updated", _D)
APPLICATION_SUBMITTED = AuditEventType("application.submitted", _D)
APPLICATION_STATUS_CHANGED = AuditEventType("application.status_changed", _D)
