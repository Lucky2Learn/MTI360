"""Audit foundation: append-only ``audit_events`` with Row-Level Security (T01-02).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-01

ADR-0013. One mixed-scope table for every audit category:

* ``tenant_id`` is nullable (NULL = platform, system or pre-authentication
  event) and has NO foreign key: ``tenants`` arrives in T01-03, and audit
  history must outlive tenant records.
* Privileges: the default privileges from ``database/init/01-roles.sh`` would
  give the application role full DML and the read-only role SELECT. They are
  replaced: the application role gets SELECT and INSERT only; the read-only
  role gets nothing (a governed Data Agent may receive scoped access later).
* Append-only, twice: no UPDATE/DELETE/TRUNCATE privilege for the runtime
  roles, and triggers that reject UPDATE, DELETE and TRUNCATE for every role,
  including the owner.
* The first Row-Level Security policies of the repository. They read the
  transaction-local context published by ``app.core.db.settings``
  (``SET LOCAL``); an unset setting reads as NULL through ``nullif``:
    - read: the platform realm reads every row; the tenant realm reads only
      its own tenant's rows; no other realm reads anything;
    - insert: ``tenant_id`` must equal the trusted tenant context (NULL-safe)
      and ``realm`` the trusted realm.
  The application role stays NOBYPASSRLS. RLS is not forced on the owner,
  which runs migrations only.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migrations.helpers import database_roles, quote_role

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of the vocabularies at this revision (never import app enums
# into migrations: a later change must come with its own migration).
REALMS = ("platform", "tenant", "student", "public", "webhook", "system")
CATEGORIES = ("security", "admin", "data_access", "domain")

TRUSTED_TENANT = "nullif(current_setting('app.tenant_id', true), '')::uuid"
TRUSTED_REALM = "nullif(current_setting('app.realm', true), '')"


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def upgrade() -> None:
    roles = database_roles()
    app_role, readonly_role = quote_role(roles["app"]), quote_role(roles["readonly"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("realm", sa.String(length=16), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("principal_id", sa.Uuid(), nullable=True),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(_in("realm", REALMS), name=op.f("ck_audit_events_realm")),
        sa.CheckConstraint(_in("category", CATEGORIES), name=op.f("ck_audit_events_category")),
        sa.CheckConstraint(
            "event_type ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$'",
            name=op.f("ck_audit_events_event_type_format"),
        ),
        sa.CheckConstraint(
            "target_type ~ '^[a-z][a-z0-9_]*$'", name=op.f("ck_audit_events_target_type_format")
        ),
        sa.CheckConstraint(
            "target_id IS NULL OR target_type IS NOT NULL",
            name=op.f("ck_audit_events_target_has_type"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(metadata) = 'object'", name=op.f("ck_audit_events_metadata_is_object")
        ),
        sa.CheckConstraint(
            "octet_length(metadata::text) <= 8192", name=op.f("ck_audit_events_metadata_size")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(
        op.f("ix_audit_events_tenant_id_created_at"), "audit_events", ["tenant_id", "created_at"]
    )
    op.create_index(
        op.f("ix_audit_events_category_created_at"), "audit_events", ["category", "created_at"]
    )
    op.create_index(op.f("ix_audit_events_request_id"), "audit_events", ["request_id"])

    # --- Privileges: replace the default privileges ---------------------------------
    op.execute(f"REVOKE ALL ON TABLE audit_events FROM {app_role}, {readonly_role}")
    op.execute(f"GRANT SELECT, INSERT ON TABLE audit_events TO {app_role}")

    # --- Append-only for every role, including the owner ----------------------------
    op.execute(
        """
        CREATE FUNCTION audit_events_reject_modification() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only (% rejected)', TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END
        $$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION audit_events_reject_modification() "
        f"FROM PUBLIC, {app_role}, {readonly_role}"
    )
    op.execute(
        "CREATE TRIGGER audit_events_reject_update_delete "
        "BEFORE UPDATE OR DELETE ON audit_events "
        "FOR EACH ROW EXECUTE FUNCTION audit_events_reject_modification()"
    )
    op.execute(
        "CREATE TRIGGER audit_events_reject_truncate "
        "BEFORE TRUNCATE ON audit_events "
        "FOR EACH STATEMENT EXECUTE FUNCTION audit_events_reject_modification()"
    )

    # --- Row-Level Security ----------------------------------------------------------
    op.execute("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY audit_events_platform_read ON audit_events FOR SELECT TO {app_role} "
        f"USING ({TRUSTED_REALM} = 'platform')"
    )
    op.execute(
        f"CREATE POLICY audit_events_tenant_read ON audit_events FOR SELECT TO {app_role} "
        f"USING ({TRUSTED_REALM} = 'tenant' AND tenant_id = {TRUSTED_TENANT})"
    )
    op.execute(
        f"CREATE POLICY audit_events_insert ON audit_events FOR INSERT TO {app_role} "
        f"WITH CHECK (tenant_id IS NOT DISTINCT FROM {TRUSTED_TENANT} "
        f"AND realm = {TRUSTED_REALM})"
    )


def downgrade() -> None:
    # Dependency-safe order: policies and triggers, the table (with its
    # indexes and constraints), then the trigger function.
    for policy in ("audit_events_insert", "audit_events_tenant_read", "audit_events_platform_read"):
        op.execute(f"DROP POLICY {policy} ON audit_events")
    op.execute("DROP TRIGGER audit_events_reject_truncate ON audit_events")
    op.execute("DROP TRIGGER audit_events_reject_update_delete ON audit_events")
    op.drop_table("audit_events")
    op.execute("DROP FUNCTION audit_events_reject_modification()")
