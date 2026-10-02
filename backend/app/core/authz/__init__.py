"""Authorization (T01-05; ADR-0011, ADR-0016).

The permission registry, ``authorize`` and ``require_permission``.
"""

from app.core.authz.dependencies import AUTHZ_DENIED, require_permission, route_permissions
from app.core.authz.engine import AuthzResource, authorize
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
    "REGISTRY",
    "AuthzResource",
    "DuplicatePermissionError",
    "Permission",
    "PermissionRegistry",
    "PermissionScope",
    "authorize",
    "permission",
    "require_permission",
    "route_permissions",
]
