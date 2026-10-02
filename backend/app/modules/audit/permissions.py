"""Audit read permissions (T01-05 baseline, D-B3): one per realm, same code."""

from app.core.authz import PermissionScope, permission
from app.core.context import Realm

_M = "audit"

TENANT_AUDIT_READ = permission(
    "audit.read", Realm.TENANT, PermissionScope.TENANT, "View the institute audit log", module=_M
)
PLATFORM_AUDIT_READ = permission(
    "audit.read", Realm.PLATFORM, None, "View the platform audit log", module=_M
)
