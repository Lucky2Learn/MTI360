"""Application permissions (Phase 02-2; ADR-0021 §11). Tenant realm, campus-scoped.

An application always has a campus (L6): members see and work the
applications of their campuses; anything else is not found (404, D-B1).
"""

from app.core.authz import PermissionScope, permission
from app.core.context import Realm

_M = "applications"
_C = PermissionScope.CAMPUS

APPLICATION_READ = permission(
    "application.read", Realm.TENANT, _C, "View applications and their history", module=_M
)
APPLICATION_CREATE = permission(
    "application.create", Realm.TENANT, _C, "Start applications", module=_M
)
APPLICATION_UPDATE = permission(
    "application.update", Realm.TENANT, _C, "Edit and submit applications", module=_M
)
APPLICATION_REVIEW = permission(
    "application.review",
    Realm.TENANT,
    _C,
    "Review applications: approve, reject or request corrections",
    module=_M,
)
