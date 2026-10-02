"""``tenants``: the platform registry of institutes (T01-03; ADR-0014).

A global table, not tenant-scoped: it is the foreign-key target of every
tenant-owned table. Its Row-Level Security policies (migration ``0003``) are
realm-aware: the platform and system realms read every row and are the only
ones that insert or update; any other context reads only its trusted tenant's
row. Tenants are never deleted (PLATFORM-ADMIN.md §38): the runtime roles have
no DELETE privilege.

Institute profile fields (legal name, address, timezone, …) are a separate
1:1 extension owned by the ``institute`` module (INC-34), not columns here.
"""

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin
from app.modules.tenants.domain import INITIAL_STATUS, TenantStatus

STATUS_MAX_LENGTH = 16


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(_in("status", [status.value for status in TenantStatus]), name="status"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(STATUS_MAX_LENGTH), nullable=False, default=INITIAL_STATUS.value
    )
