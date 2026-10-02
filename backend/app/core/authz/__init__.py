"""Authorization (T01-05; ADR-0011, ADR-0016).

The permission registry, ``authorize`` and ``require_permission``.
"""

from app.core.authz.dependencies import (
    AUTHZ_DENIED,
    AUTHZ_STEP_UP_REQUIRED,
    require_permission,
    route_permissions,
)
from app.core.authz.engine import STEP_UP_WINDOW, AuthzResource, authorize, require_fresh_mfa
from app.core.authz.registry import (
    REGISTRY,
    DuplicatePermissionError,
    Permission,
    PermissionRegistry,
    PermissionScope,
    permission,
)

__all__ = [
    "AUTHZ_DENIED",
    "AUTHZ_STEP_UP_REQUIRED",
    "REGISTRY",
    "STEP_UP_WINDOW",
    "AuthzResource",
    "DuplicatePermissionError",
    "Permission",
    "PermissionRegistry",
    "PermissionScope",
    "authorize",
    "permission",
    "require_fresh_mfa",
    "require_permission",
    "route_permissions",
]
