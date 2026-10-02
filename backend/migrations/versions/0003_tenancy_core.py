"""Tenancy core: ``tenants`` and ``campuses`` with Row-Level Security (T01-03).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-02

ADR-0014 (refining ADR-0004):

* ``tenants`` — the global registry. Status is one of the eight lifecycle
  states (CHECK). Realm-aware RLS: the platform and system realms read every
  row and are the only realms that insert or update; any context with a
  trusted tenant reads only that tenant's row.
* ``campuses`` — the first tenant-owned table. ``tenant_id`` → ``tenants``
  (ON DELETE RESTRICT), ``UNIQUE (tenant_id, id)`` for composite foreign keys,
  ``UNIQUE (tenant_id, code)`` with an upper-case code format. Realm-agnostic
  RLS, the pattern for every tenant-owned table: ``tenant_id`` must equal the
  trusted ``app.tenant_id`` for reads and writes; without a tenant context
  nothing matches.
* Privileges replace the defaults of ``database/init/01-roles.sh``: the
  application role gets SELECT, INSERT and UPDATE (never DELETE: tenants and
  campuses are not hard-deleted); the read-only role gets SELECT, restricted
  by RLS to the trusted tenant.
* RLS is enabled, not forced (the owner runs migrations only, as in 0002).
  The runtime roles stay NOBYPASSRLS.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from migrations.helpers import database_roles, quote_role

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies at this revision (never import app enums into migrations).
TENANT_STATUSES = (
    "PROSPECT",
    "TRIAL",
    "PROVISIONING",
    "ACTIVE",
    "PAST_DUE",
    "SUSPENDED",
    "CANCELLED",
    "DEACTIVATED",
)
CAMPUS_CODE_PATTERN = "^[A-Z0-9][A-Z0-9-]*$"

TRUSTED_TENANT = "nullif(current_setting('app.tenant_id', true), '')::uuid"
TRUSTED_REALM = "nullif(current_setting('app.realm', true), '')"
PLATFORM_OR_SYSTEM = f"{TRUSTED_REALM} IN ('platform', 'system')"

POLICIES = (
    ("tenants", "tenants_platform_read"),
    ("tenants", "tenants_own_read"),
    ("tenants", "tenants_platform_insert"),
    ("tenants", "tenants_platform_update"),
    ("campuses", "campuses_tenant_isolation"),
    ("campuses", "campuses_readonly_tenant_read"),
)


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _timestamps_and_version() -> list[sa.Column[Any]]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
    ]


def upgrade() -> None:
    roles = database_roles()
    app_role, readonly_role = quote_role(roles["app"]), quote_role(roles["readonly"])

    # --- Tables, constraints, indexes ------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        *_timestamps_and_version(),
        sa.CheckConstraint(_in("status", TENANT_STATUSES), name=op.f("ck_tenants_status")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
    )
    op.create_table(
        "campuses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        *_timestamps_and_version(),
        sa.CheckConstraint(f"code ~ '{CAMPUS_CODE_PATTERN}'", name=op.f("ck_campuses_code_format")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_campuses_tenant_id_tenants"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campuses")),
        # Composite foreign-key target; its leading column also indexes tenant_id.
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_campuses_tenant_id_id")),
        sa.UniqueConstraint("tenant_id", "code", name=op.f("uq_campuses_tenant_id_code")),
    )

    # --- Privileges: replace the default privileges ---------------------------------
    for table in ("tenants", "campuses"):
        op.execute(f"REVOKE ALL ON TABLE {table} FROM {app_role}, {readonly_role}")
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE {table} TO {app_role}")
        op.execute(f"GRANT SELECT ON TABLE {table} TO {readonly_role}")

    # --- Row-Level Security: tenants (global registry, realm-aware) -----------------
    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenants_platform_read ON tenants FOR SELECT TO {app_role} "
        f"USING ({PLATFORM_OR_SYSTEM})"
    )
    op.execute(
        f"CREATE POLICY tenants_own_read ON tenants FOR SELECT TO {app_role}, {readonly_role} "
        f"USING (id = {TRUSTED_TENANT})"
    )
    op.execute(
        f"CREATE POLICY tenants_platform_insert ON tenants FOR INSERT TO {app_role} "
        f"WITH CHECK ({PLATFORM_OR_SYSTEM})"
    )
    op.execute(
        f"CREATE POLICY tenants_platform_update ON tenants FOR UPDATE TO {app_role} "
        f"USING ({PLATFORM_OR_SYSTEM}) WITH CHECK ({PLATFORM_OR_SYSTEM})"
    )

    # --- Row-Level Security: campuses (tenant-owned, realm-agnostic) ----------------
    op.execute("ALTER TABLE campuses ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY campuses_tenant_isolation ON campuses FOR ALL TO {app_role} "
        f"USING (tenant_id = {TRUSTED_TENANT}) WITH CHECK (tenant_id = {TRUSTED_TENANT})"
    )
    op.execute(
        f"CREATE POLICY campuses_readonly_tenant_read ON campuses FOR SELECT TO {readonly_role} "
        f"USING (tenant_id = {TRUSTED_TENANT})"
    )


def downgrade() -> None:
    for table, policy in reversed(POLICIES):
        op.execute(f"DROP POLICY {policy} ON {table}")
    op.execute("ALTER TABLE campuses DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY")
    op.drop_table("campuses")
    op.drop_table("tenants")
