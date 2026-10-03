"""The fixed platform roles and their permissions (T01-05; PRD.md §85, ADR-0011 §3).

The seven role codes come from PRD.md §85 / PLATFORM-ADMIN.md §7. Their
permission map lives in code (no database rows); assignments to platform
users (``platform_user_roles``) arrive with ``platform_users`` in T01-06.

T01 grants permissions only to ``SUPER_ADMIN`` (every T01 platform
permission: ``tenant.*``, ``platform_user.*`` and ``audit.read``, expanded to
explicit codes) and ``SECURITY_AUDIT_ADMIN`` (``audit.read``). The other
roles exist but grant nothing until their phases (decision D7).
"""

from enum import StrEnum
from types import MappingProxyType
from typing import Final

from app.core.authz import Permission
from app.modules.audit.permissions import PLATFORM_AUDIT_READ
from app.modules.platform_identity.permissions import (
    PLATFORM_USER_CREATE,
    PLATFORM_USER_REACTIVATE,
    PLATFORM_USER_READ,
    PLATFORM_USER_SUSPEND,
    PLATFORM_USER_UPDATE,
)
from app.modules.tenants.permissions import (
    TENANT_CREATE,
    TENANT_REACTIVATE,
    TENANT_READ,
    TENANT_SUSPEND,
)


class PlatformRole(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    PLATFORM_OPERATIONS_ADMIN = "PLATFORM_OPERATIONS_ADMIN"
    CUSTOMER_SUCCESS_ADMIN = "CUSTOMER_SUCCESS_ADMIN"
    BILLING_ADMIN = "BILLING_ADMIN"
    SUPPORT_ADMIN = "SUPPORT_ADMIN"
    SECURITY_AUDIT_ADMIN = "SECURITY_AUDIT_ADMIN"
    AI_PLATFORM_ADMIN = "AI_PLATFORM_ADMIN"


PLATFORM_ROLE_PERMISSIONS: Final[MappingProxyType[PlatformRole, frozenset[Permission]]] = (
    MappingProxyType(
        {
            PlatformRole.SUPER_ADMIN: frozenset(
                {
                    TENANT_READ,
                    TENANT_CREATE,
                    TENANT_SUSPEND,
                    TENANT_REACTIVATE,
                    PLATFORM_USER_READ,
                    PLATFORM_USER_CREATE,
                    PLATFORM_USER_UPDATE,
                    PLATFORM_USER_SUSPEND,
                    PLATFORM_USER_REACTIVATE,
                    PLATFORM_AUDIT_READ,
                }
            ),
            PlatformRole.PLATFORM_OPERATIONS_ADMIN: frozenset(),
            PlatformRole.CUSTOMER_SUCCESS_ADMIN: frozenset(),
            PlatformRole.BILLING_ADMIN: frozenset(),
            PlatformRole.SUPPORT_ADMIN: frozenset(),
            PlatformRole.SECURITY_AUDIT_ADMIN: frozenset({PLATFORM_AUDIT_READ}),
            PlatformRole.AI_PLATFORM_ADMIN: frozenset(),
        }
    )
)


GUARDIAN_ROLE: Final = PlatformRole.SUPER_ADMIN
"""The role the platform must always keep at least one active holder of (D7-5).

A role invariant, not an authorization rule: permissions still come only from
:data:`PLATFORM_ROLE_PERMISSIONS`."""


def platform_permissions(roles: frozenset[PlatformRole]) -> frozenset[str]:
    """Effective platform permission codes of a set of roles (union)."""
    return frozenset(p.code for role in roles for p in PLATFORM_ROLE_PERMISSIONS[role])
