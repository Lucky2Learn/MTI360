"""Tenant permissions (T01-05 baseline, D-B3).

``tenant.profile.read`` is the tenant realm's view of its own institute; the
``tenant.*`` lifecycle permissions belong to the platform realm (T01-07).
"""

from app.core.authz import PermissionScope, permission
from app.core.context import Realm

_M = "tenants"

TENANT_PROFILE_READ = permission(
    "tenant.profile.read",
    Realm.TENANT,
    PermissionScope.TENANT,
    "View the institute profile",
    module=_M,
)

TENANT_READ = permission("tenant.read", Realm.PLATFORM, None, "View tenants", module=_M)
TENANT_CREATE = permission("tenant.create", Realm.PLATFORM, None, "Provision tenants", module=_M)
TENANT_SUSPEND = permission("tenant.suspend", Realm.PLATFORM, None, "Suspend tenants", module=_M)
TENANT_REACTIVATE = permission(
    "tenant.reactivate", Realm.PLATFORM, None, "Reactivate tenants", module=_M
)
