"""Campus permissions (T01-05 baseline, D-B3). Tenant realm."""

from app.core.authz import PermissionScope, permission
from app.core.context import Realm

_M = "institute"

CAMPUS_READ = permission(
    "campus.read", Realm.TENANT, PermissionScope.CAMPUS, "View campuses", module=_M
)
CAMPUS_CREATE = permission(
    "campus.create", Realm.TENANT, PermissionScope.TENANT, "Add campuses", module=_M
)
CAMPUS_UPDATE = permission(
    "campus.update", Realm.TENANT, PermissionScope.CAMPUS, "Edit campuses", module=_M
)
