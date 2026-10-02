"""Role permissions (T01-05 baseline, D-B3). Tenant realm, tenant-wide."""

from app.core.authz import PermissionScope, permission
from app.core.context import Realm

_M = "access"
_T = PermissionScope.TENANT

ROLE_READ = permission("role.read", Realm.TENANT, _T, "View roles", module=_M)
ROLE_CREATE = permission("role.create", Realm.TENANT, _T, "Create custom roles", module=_M)
ROLE_UPDATE = permission("role.update", Realm.TENANT, _T, "Edit custom roles", module=_M)
ROLE_DELETE = permission("role.delete", Realm.TENANT, _T, "Delete custom roles", module=_M)
ROLE_ASSIGN = permission("role.assign", Realm.TENANT, _T, "Assign roles to members", module=_M)
