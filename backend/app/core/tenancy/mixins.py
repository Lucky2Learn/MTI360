"""Tenant-scoped model foundation (T01-03; ADR-0004, ADR-0014, tenancy.md §4, §9).

Every tenant-owned table inherits :class:`TenantScopedMixin`:

* ``id`` — the UUIDv7 primary key (:class:`UUIDPrimaryKeyMixin`);
* ``tenant_id`` — ``NOT NULL``, foreign key to ``tenants(id)`` with
  ``ON DELETE RESTRICT``. The table is referenced by name, so ``core`` never
  imports the ``tenants`` module;
* the table must also declare ``UniqueConstraint("tenant_id", "id")``: the
  target of composite foreign keys from tenant-scoped children
  (:func:`tenant_foreign_key`). A unit test enforces it for every mapper.

The mixin is what the tenant ORM filter (``app.core.tenancy.filter``), the
tenant-scoped repository and the Row-Level Security policy of the table
(written in its migration) rely on. ``tenant_id`` is never accepted from
request input: repositories stamp it from the trusted context.
"""

import uuid

from sqlalchemy import ForeignKey, ForeignKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import UUIDPrimaryKeyMixin

TENANTS_TABLE = "tenants"


class TenantScopedMixin(UUIDPrimaryKeyMixin):
    """A row owned by exactly one tenant."""

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{TENANTS_TABLE}.id", ondelete="RESTRICT"), nullable=False, sort_order=-9
    )


def tenant_foreign_key(
    column: str, parent_table: str, *, name: str | None = None
) -> ForeignKeyConstraint:
    """Composite foreign key from a tenant-scoped child to a tenant-scoped parent.

    ``(tenant_id, <column>) → <parent_table>(tenant_id, id)``, ``ON DELETE
    RESTRICT``: the database rejects a child that points at another tenant's
    parent, whatever the application does. The parent must declare
    ``UNIQUE (tenant_id, id)``. ``name`` overrides the naming convention when
    the generated name would exceed PostgreSQL's 63-character limit.
    """
    return ForeignKeyConstraint(
        ["tenant_id", column],
        [f"{parent_table}.tenant_id", f"{parent_table}.id"],
        ondelete="RESTRICT",
        name=name,
    )
