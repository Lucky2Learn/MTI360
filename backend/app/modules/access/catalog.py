"""The complete permission catalogue (T01-05; D-B3, D-B4).

Imports every module's ``permissions.py`` so that :data:`REGISTRY` is
complete wherever the catalogue is used (role templates, the application,
the drift test). A test fails when a module declares a ``permissions.py``
that is not listed here.
"""

from app.core.authz import REGISTRY, Permission
from app.core.context import Realm
from app.modules.access import permissions as _access
from app.modules.audit import permissions as _audit
from app.modules.courses import permissions as _courses
from app.modules.identity import permissions as _identity
from app.modules.institute import permissions as _institute
from app.modules.leads import permissions as _leads
from app.modules.platform_identity import permissions as _platform_identity
from app.modules.tenants import permissions as _tenants

PERMISSION_MODULES = tuple(
    module.__name__
    for module in (
        _access,
        _audit,
        _courses,
        _identity,
        _institute,
        _leads,
        _platform_identity,
        _tenants,
    )
)


def all_permissions() -> tuple[Permission, ...]:
    """Every declared permission, sorted by ``(realm, code)``."""
    return REGISTRY.all()


def tenant_permissions() -> tuple[Permission, ...]:
    return tuple(p for p in REGISTRY.all() if p.realm is Realm.TENANT)
