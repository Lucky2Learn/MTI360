"""Member permissions (T01-05 baseline, D-B3). Tenant realm, tenant-wide."""

from app.core.authz import PermissionScope, permission
from app.core.context import Realm

_M = "identity"
_T = PermissionScope.TENANT

MEMBER_READ = permission("member.read", Realm.TENANT, _T, "View members", module=_M)
MEMBER_INVITE = permission("member.invite", Realm.TENANT, _T, "Invite members", module=_M)
MEMBER_UPDATE = permission("member.update", Realm.TENANT, _T, "Edit members", module=_M)
MEMBER_SUSPEND = permission("member.suspend", Realm.TENANT, _T, "Suspend members", module=_M)
MEMBER_REVOKE = permission("member.revoke", Realm.TENANT, _T, "Remove members", module=_M)
