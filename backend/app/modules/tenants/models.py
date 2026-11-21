"""``tenants``: the platform registry of institutes (T01-03; ADR-0014).

A global table, not tenant-scoped: it is the foreign-key target of every
tenant-owned table. Its Row-Level Security policies (migration ``0003``) are
realm-aware: the platform and system realms read every row and are the only
ones that insert or update; any other context reads only its trusted tenant's
row. Tenants are never deleted (PLATFORM-ADMIN.md §38): the runtime roles have
no DELETE privilege.

``tenant_domains`` (Phase 02-4, ADR-0024) maps a verified hostname to its
institute for the public realm. A global table: the hostname is unique across
the platform, so no institute can take another's address. Its Row-Level
Security (migration ``0012``): the platform and system realms read every row
and are the only ones that insert or update; the public realm reads only
``ACTIVE``, verified rows (to resolve a request host); a tenant context reads
its own rows. Never deleted: an address is deactivated instead.

Institute profile fields (legal name, address, timezone, …) are a separate
1:1 extension owned by the ``institute`` module (INC-34), not columns here.

``owner_membership_id`` (T01-07, D7-1/D7-8) points at the membership of the
primary administrator invited at provisioning: the composite foreign key
``(id, owner_membership_id) → tenant_memberships(tenant_id, id)`` keeps it
inside the tenant. It lets the platform show and re-invite the owner through
one narrow key, without reading the tenant's other members.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin
from app.modules.tenants.domain import INITIAL_STATUS, TenantStatus
from app.modules.tenants.sites import (
    HOSTNAME_MAX_LENGTH,
    HOSTNAME_PATTERN,
    DomainKind,
    DomainStatus,
)

STATUS_MAX_LENGTH = 16


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(_in("status", [status.value for status in TenantStatus]), name="status"),
        # Tenants and memberships reference each other: created after both tables.
        ForeignKeyConstraint(
            ["id", "owner_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            ondelete="RESTRICT",
            name="fk_tenants_owner_membership",
            use_alter=True,
        ),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(STATUS_MAX_LENGTH), nullable=False, default=INITIAL_STATUS.value
    )
    owner_membership_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)


class TenantDomain(UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, Base):
    """A verified hostname of an institute's public pages (Phase 02-4, ADR-0024)."""

    __tablename__ = "tenant_domains"
    __table_args__ = (
        UniqueConstraint("hostname"),
        CheckConstraint(_in("kind", [kind.value for kind in DomainKind]), name="kind"),
        CheckConstraint(_in("status", [status.value for status in DomainStatus]), name="status"),
        CheckConstraint(f"hostname ~ '{HOSTNAME_PATTERN}'", name="hostname_format"),
        CheckConstraint(
            "kind <> 'PLATFORM_SUBDOMAIN' OR verified_at IS NOT NULL", name="platform_verified"
        ),
        # One active platform address per institute.
        Index(
            "ix_tenant_domains_one_active_platform",
            "tenant_id",
            unique=True,
            postgresql_where=text("kind = 'PLATFORM_SUBDOMAIN' AND status = 'ACTIVE'"),
        ),
        Index(None, "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    hostname: Mapped[str] = mapped_column(String(HOSTNAME_MAX_LENGTH), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
