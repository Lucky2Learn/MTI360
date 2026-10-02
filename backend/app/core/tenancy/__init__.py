"""Tenancy core (T01-03; ADR-0004, ADR-0014): tenant-scoped models and isolation layers.

Importing the package installs the automatic tenant ORM filter
(:mod:`app.core.tenancy.filter`) on every SQLAlchemy session.
"""

from app.core.tenancy import filter as _filter  # noqa: F401 - installs the ORM listener
from app.core.tenancy.context import (
    MissingTenantContextError,
    TenantMismatchError,
    trusted_tenant_id,
)
from app.core.tenancy.mixins import TenantScopedMixin, tenant_foreign_key
from app.core.tenancy.repository import TenantScopedRepository
from app.core.tenancy.system import SystemContextError, system_context

__all__ = [
    "MissingTenantContextError",
    "SystemContextError",
    "TenantMismatchError",
    "TenantScopedMixin",
    "TenantScopedRepository",
    "system_context",
    "tenant_foreign_key",
    "trusted_tenant_id",
]
