"""Platform user permissions (T01-05 baseline, D-B3). Platform realm."""

from app.core.authz import permission
from app.core.context import Realm

_M = "platform_identity"
_P = Realm.PLATFORM

PLATFORM_USER_READ = permission("platform_user.read", _P, None, "View platform users", module=_M)
PLATFORM_USER_CREATE = permission("platform_user.create", _P, None, "Add platform users", module=_M)
PLATFORM_USER_UPDATE = permission(
    "platform_user.update", _P, None, "Edit platform users", module=_M
)
PLATFORM_USER_SUSPEND = permission(
    "platform_user.suspend", _P, None, "Suspend platform users", module=_M
)
PLATFORM_USER_REACTIVATE = permission(
    "platform_user.reactivate", _P, None, "Reactivate platform users", module=_M
)
