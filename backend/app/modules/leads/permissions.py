"""Lead permissions (Phase 02-1; ADR-0020 §10). Tenant realm, campus-scoped.

A lead without a campus (the institute pool, L6) is visible to every holder;
a lead of a campus only to members with that campus (D-B1, 404 otherwise).
Follow-ups, notes and status changes are covered by ``lead.update``.
"""

from app.core.authz import PermissionScope, permission
from app.core.context import Realm

_M = "leads"
_C = PermissionScope.CAMPUS

LEAD_READ = permission("lead.read", Realm.TENANT, _C, "View leads and their history", module=_M)
LEAD_CREATE = permission("lead.create", Realm.TENANT, _C, "Add leads", module=_M)
LEAD_UPDATE = permission(
    "lead.update",
    Realm.TENANT,
    _C,
    "Edit leads, change their status, add notes and follow-ups",
    module=_M,
)
LEAD_ASSIGN = permission(
    "lead.assign", Realm.TENANT, _C, "Assign leads to staff and campuses", module=_M
)
