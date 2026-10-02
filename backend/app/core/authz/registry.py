"""Permission registry (T01-05; ADR-0011, ADR-0016 D-B3).

A permission is identified by ``(realm, code)`` and declared **in code**, in
the ``permissions.py`` of the module that owns it::

    CAMPUS_READ = permission(
        "campus.read", Realm.TENANT, PermissionScope.CAMPUS, "View campuses", module="institute"
    )

* Codes are ``resource.action`` in lower case. Wildcards are not permissions:
  "all actions of a resource" is always an explicit list.
* Only the ``platform`` and ``tenant`` realms have permissions in T01.
* Tenant permissions carry a scope (decision D-B1): ``TENANT`` (tenant-wide;
  requires all-campus access) or ``CAMPUS`` (checked against the resource's
  campus). Platform permissions have no scope.
* ``requires_step_up`` is the MFA hook (T01-06); such permissions are refused
  until step-up authentication exists (fail closed).

The registry is read-only data: it never writes to the database. Permissions
reach the ``permissions`` table only through Alembic migrations (decision
D-B4), and a test compares the two.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from app.core.context import Realm

CODE_PATTERN: Final = r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$"
CODE_MAX_LENGTH: Final = 100
PERMISSION_REALMS: Final = frozenset({Realm.PLATFORM, Realm.TENANT})
_CODE = re.compile(CODE_PATTERN)


class PermissionScope(StrEnum):
    TENANT = "tenant"
    """Tenant-wide: requires all-campus access (D-B1)."""
    CAMPUS = "campus"
    """Checked against the resource's campus (D-B1)."""


@dataclass(frozen=True, slots=True)
class Permission:
    code: str
    realm: Realm
    scope: PermissionScope | None
    description: str
    module: str
    requires_step_up: bool = False

    def __post_init__(self) -> None:
        if len(self.code) > CODE_MAX_LENGTH or not _CODE.fullmatch(self.code):
            raise ValueError(f"invalid permission code: {self.code!r}")
        if self.realm not in PERMISSION_REALMS:
            raise ValueError(
                f"permissions exist only in the platform and tenant realms: {self.code}"
            )
        if (self.realm is Realm.TENANT) != (self.scope is not None):
            raise ValueError(f"tenant permissions need a scope, platform ones none: {self.code}")

    @property
    def key(self) -> tuple[str, str]:
        return (self.realm.value, self.code)


class DuplicatePermissionError(ValueError):
    pass


class PermissionRegistry:
    def __init__(self) -> None:
        self._permissions: dict[tuple[str, str], Permission] = {}

    def register(self, permission: Permission) -> Permission:
        existing = self._permissions.get(permission.key)
        if existing is not None and existing != permission:
            raise DuplicatePermissionError(f"permission declared twice: {permission.key}")
        self._permissions[permission.key] = permission
        return permission

    def get(self, realm: Realm, code: str) -> Permission | None:
        return self._permissions.get((realm.value, code))

    def all(self) -> tuple[Permission, ...]:
        return tuple(sorted(self._permissions.values(), key=lambda p: p.key))

    def codes(self, realm: Realm) -> frozenset[str]:
        return frozenset(p.code for p in self._permissions.values() if p.realm is realm)


REGISTRY: Final = PermissionRegistry()


def permission(
    code: str,
    realm: Realm,
    scope: PermissionScope | None,
    description: str,
    *,
    module: str,
    requires_step_up: bool = False,
) -> Permission:
    """Declare and register a permission (used by module ``permissions.py`` files)."""
    return REGISTRY.register(Permission(code, realm, scope, description, module, requires_step_up))
