"""Permission catalogue, tenant roles and role assignments (T01-05; ADR-0011, ADR-0016).

* ``permissions`` â€” the catalogue, keyed by ``(realm, code)`` (D-B3). Rows are
  written **only by Alembic migrations** (D-B4); the runtime roles can only
  read it. A test compares it with the code registry.
* ``roles`` â€” a tenant's roles. A *system* role (``is_system``) is a clone of
  a code template (``template_code``: ``INSTITUTE_OWNER`` or ``ADMIN``);
  custom roles have no template. The database keeps system roles immutable
  (D-B2): a trigger rejects renaming, deleting or changing their permissions,
  and Row-Level Security lets only the system realm create them.
* ``role_permissions`` â€” a role's permissions; tenant realm only (CHECK plus a
  foreign key to the catalogue), so a tenant role can never hold a platform
  permission.
* ``membership_roles`` â€” the roles of a membership (many; the effective
  permissions are their union). Composite foreign keys keep membership, role
  and tenant consistent.

Row-Level Security policies, triggers and privileges are defined in the
migration (``0005``).
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    Computed,
    ForeignKeyConstraint,
    Index,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    func,
    literal_column,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TimestampMixin, VersionedMixin
from app.core.tenancy import TenantScopedMixin, tenant_foreign_key

CODE_MAX_LENGTH = 100  # = app.core.authz.registry.CODE_MAX_LENGTH (unit-tested)
ROLE_NAME_MAX_LENGTH = 100
ROLE_DESCRIPTION_MAX_LENGTH = 500
TENANT_REALM = "tenant"
CODE_FORMAT = r"code ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$'"


class PermissionRecord(Base):
    """A row of the permission catalogue (read-only at runtime)."""

    __tablename__ = "permissions"
    __table_args__ = (
        PrimaryKeyConstraint("realm", "code"),
        CheckConstraint("realm IN ('platform', 'tenant')", name="realm"),
        CheckConstraint("scope IN ('tenant', 'campus')", name="scope"),
        CheckConstraint("(realm = 'tenant') = (scope IS NOT NULL)", name="scope_realm"),
        CheckConstraint(CODE_FORMAT, name="code_format"),
    )

    realm: Mapped[str] = mapped_column(String(16))
    code: Mapped[str] = mapped_column(String(CODE_MAX_LENGTH))
    scope: Mapped[str | None] = mapped_column(String(16))
    module: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class Role(TenantScopedMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "template_code"),
        # Role names are unique per tenant, ignoring case.
        Index(
            "uq_roles_tenant_id_lower_name",
            "tenant_id",
            func.lower(literal_column("name")),
            unique=True,
        ),
        CheckConstraint("btrim(name) <> ''", name="name"),
        CheckConstraint("is_system = (template_code IS NOT NULL)", name="system_template"),
    )

    name: Mapped[str] = mapped_column(String(ROLE_NAME_MAX_LENGTH), nullable=False)
    description: Mapped[str | None] = mapped_column(String(ROLE_DESCRIPTION_MAX_LENGTH))
    template_code: Mapped[str | None] = mapped_column(String(32))
    is_system: Mapped[bool] = mapped_column(nullable=False)


class RolePermission(TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("role_id", "permission_code"),
        tenant_foreign_key("role_id", "roles"),
        ForeignKeyConstraint(
            ["permission_realm", "permission_code"],
            ["permissions.realm", "permissions.code"],
            ondelete="RESTRICT",
            name="fk_role_permissions_permission",
        ),
    )

    role_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    # Generated, always 'tenant' (ADR-0011 §2): with the foreign key above,
    # the database rejects a platform permission on a tenant role.
    permission_realm: Mapped[str] = mapped_column(
        String(16), Computed(f"'{TENANT_REALM}'::character varying", persisted=True)
    )
    permission_code: Mapped[str] = mapped_column(String(CODE_MAX_LENGTH), nullable=False)


class MembershipRole(TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "membership_roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("membership_id", "role_id"),
        tenant_foreign_key(
            "membership_id", "tenant_memberships", name="fk_membership_roles_membership"
        ),
        tenant_foreign_key("role_id", "roles"),
        Index(None, "role_id"),
    )

    membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
