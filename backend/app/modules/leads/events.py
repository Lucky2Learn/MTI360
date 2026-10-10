"""Lead audit events (Phase 02-1; ADR-0013 category ``domain``, blueprint §25).

Metadata: sources, statuses, field names and booleans only. Never a name,
mobile, email, reason or note text. Follow-ups and notes are activity only.
"""

from app.core.audit import AuditCategory, AuditEventType

_D = AuditCategory.DOMAIN

LEAD_CREATED = AuditEventType("lead.created", _D)
LEAD_UPDATED = AuditEventType("lead.updated", _D)
LEAD_STATUS_CHANGED = AuditEventType("lead.status_changed", _D)
LEAD_ASSIGNED = AuditEventType("lead.assigned", _D)
