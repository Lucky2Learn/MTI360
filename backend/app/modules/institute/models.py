"""``campuses``: the campuses of a tenant (T01-03; PRD.md §12, PLATFORM-ADMIN.md §30).

Tenant-scoped (:class:`TenantScopedMixin`), protected by a realm-agnostic
Row-Level Security policy ``tenant_id = app.tenant_id`` (migration ``0003``).

* ``code`` is required, upper case (``^[A-Z0-9][A-Z0-9-]*$``) and unique per
  tenant; the same code may exist in different tenants.
* ``UNIQUE (tenant_id, id)`` is the target of composite foreign keys from
  campus-aware tables (memberships, batches, …).
* No hard delete: the runtime roles have no DELETE privilege. Address,
  contact, timezone and status arrive with the campus API (T01-08).
"""

from sqlalchemy import CheckConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TimestampMixin, VersionedMixin
from app.core.tenancy import TenantScopedMixin

CAMPUS_CODE_PATTERN = "^[A-Z0-9][A-Z0-9-]*$"
CAMPUS_CODE_MAX_LENGTH = 32


class Campus(TenantScopedMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "campuses"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "code"),
        CheckConstraint(f"code ~ '{CAMPUS_CODE_PATTERN}'", name="code_format"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(CAMPUS_CODE_MAX_LENGTH), nullable=False)
