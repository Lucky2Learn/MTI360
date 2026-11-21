# SQL is assembled only from the frozen constants below (no input): S608 is a false positive.
# ruff: noqa: S608
"""Public enquiry: institute domains, transactional outbox, lead consent (Phase 02-4).

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-31

ADR-0024:

* ``tenant_domains`` — global registry of verified hostnames
  (``<slug>.<public site domain>``, platform-issued and verified by
  construction). ``hostname`` is unique across the platform; one ``ACTIVE``
  platform address per institute. Realm-aware Row-Level Security: platform and
  system read every row and are the only realms that insert or update; the
  public realm reads only ``ACTIVE``, verified rows; a tenant context reads its
  own rows. The application role gets SELECT, INSERT, UPDATE; the read-only
  role nothing.
* ``outbox_messages`` — tenant-scoped transactional outbox. Tenant Row-Level
  Security plus a system-realm policy for the worker, which claims messages of
  every tenant. SELECT, INSERT, UPDATE for the application role (never DELETE);
  nothing for the read-only role (identifiers only, but operational data).
* ``leads`` — ``consent_version`` and ``consented_at`` (consent evidence of a
  public enquiry, set together); ``created_by_membership_id`` becomes nullable,
  but only a ``WEBSITE`` lead with consent evidence may have no creator.

The downgrade is a development operation that loses data (like ``0011``): it
deletes the leads without a creator (public enquiries) with their follow-ups
and activities, then drops both tables and the consent columns. It refuses
while such a lead has an application or is another lead's duplicate target,
because that would cut admissions history. No SECURITY DEFINER.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migrations.helpers import database_roles, quote_role

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# --- Frozen copies at this revision (never import app code into migrations) -----------
T = "nullif(current_setting('app.tenant_id', true), '')::uuid"
REALM = "nullif(current_setting('app.realm', true), '')"
PLATFORM_OR_SYSTEM = f"{REALM} IN ('platform', 'system')"
LABEL = "[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
HOSTNAME_PATTERN = f"^{LABEL}(?:\\.{LABEL})+$"
DOMAIN_KINDS = ("PLATFORM_SUBDOMAIN",)
DOMAIN_STATUSES = ("ACTIVE", "INACTIVE")
OUTBOX_STATUSES = ("PENDING", "PROCESSING", "SENT", "FAILED")

DOMAIN_POLICIES = (
    "tenant_domains_platform_read",
    "tenant_domains_public_read",
    "tenant_domains_own_read",
    "tenant_domains_platform_insert",
    "tenant_domains_platform_update",
)


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _check(table: str, name: str, condition: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(condition, name=op.f(f"ck_{table}_{name}"))


def _timestamps() -> list[sa.Column[Any]]:
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
    ]


def upgrade() -> None:
    roles = database_roles()
    app_role, readonly_role = quote_role(roles["app"]), quote_role(roles["readonly"])

    # --- tenant_domains --------------------------------------------------------------
    op.create_table(
        "tenant_domains",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("hostname", sa.String(length=253), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_domains")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_tenant_domains_tenant_id_tenants"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("hostname", name=op.f("uq_tenant_domains_hostname")),
        _check("tenant_domains", "kind", _in("kind", DOMAIN_KINDS)),
        _check("tenant_domains", "status", _in("status", DOMAIN_STATUSES)),
        _check("tenant_domains", "hostname_format", f"hostname ~ '{HOSTNAME_PATTERN}'"),
        _check(
            "tenant_domains",
            "platform_verified",
            "kind <> 'PLATFORM_SUBDOMAIN' OR verified_at IS NOT NULL",
        ),
    )
    op.create_index(op.f("ix_tenant_domains_tenant_id"), "tenant_domains", ["tenant_id"])
    op.create_index(
        "ix_tenant_domains_one_active_platform",
        "tenant_domains",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'PLATFORM_SUBDOMAIN' AND status = 'ACTIVE'"),
    )

    # --- outbox_messages -------------------------------------------------------------
    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'PENDING'"), nullable=False
        ),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=64), nullable=True),
        sa.Column("last_error", sa.String(length=64), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_messages")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_outbox_messages_tenant_id_tenants"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name=op.f("uq_outbox_messages_tenant_id_idempotency_key"),
        ),
        _check("outbox_messages", "status", _in("status", OUTBOX_STATUSES)),
        _check("outbox_messages", "attempts", "attempts >= 0 AND attempts <= max_attempts"),
        _check("outbox_messages", "max_attempts", "max_attempts BETWEEN 1 AND 20"),
        _check(
            "outbox_messages",
            "locked",
            "(status = 'PROCESSING') = (locked_at IS NOT NULL AND locked_by IS NOT NULL)",
        ),
        _check("outbox_messages", "sent_at", "(status = 'SENT') = (sent_at IS NOT NULL)"),
        _check("outbox_messages", "failed_at", "(status = 'FAILED') = (failed_at IS NOT NULL)"),
    )
    op.create_index(
        "ix_outbox_messages_ready",
        "outbox_messages",
        ["available_at"],
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    op.create_index(
        "ix_outbox_messages_processing",
        "outbox_messages",
        ["locked_at"],
        postgresql_where=sa.text("status = 'PROCESSING'"),
    )

    # --- leads: consent evidence; no creator only for a consented website lead -------
    op.add_column("leads", sa.Column("consent_version", sa.String(length=32), nullable=True))
    op.add_column("leads", sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("leads", "created_by_membership_id", existing_type=sa.Uuid(), nullable=True)
    op.create_check_constraint(
        op.f("ck_leads_consent"), "leads", "(consent_version IS NULL) = (consented_at IS NULL)"
    )
    op.create_check_constraint(
        op.f("ck_leads_creator"),
        "leads",
        "created_by_membership_id IS NOT NULL "
        "OR (source = 'WEBSITE' AND consent_version IS NOT NULL)",
    )

    # --- Privileges: replace the defaults ----------------------------------------------
    for table in ("tenant_domains", "outbox_messages"):
        op.execute(f"REVOKE ALL ON TABLE {table} FROM {app_role}, {readonly_role}")
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE {table} TO {app_role}")

    # --- Row-Level Security --------------------------------------------------------------
    op.execute("ALTER TABLE tenant_domains ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_domains_platform_read ON tenant_domains FOR SELECT "
        f"TO {app_role} USING ({PLATFORM_OR_SYSTEM})"
    )
    op.execute(
        f"CREATE POLICY tenant_domains_public_read ON tenant_domains FOR SELECT TO {app_role} "
        f"USING ({REALM} = 'public' AND status = 'ACTIVE' AND verified_at IS NOT NULL)"
    )
    op.execute(
        f"CREATE POLICY tenant_domains_own_read ON tenant_domains FOR SELECT TO {app_role} "
        f"USING (tenant_id = {T})"
    )
    op.execute(
        f"CREATE POLICY tenant_domains_platform_insert ON tenant_domains FOR INSERT "
        f"TO {app_role} WITH CHECK ({PLATFORM_OR_SYSTEM})"
    )
    op.execute(
        f"CREATE POLICY tenant_domains_platform_update ON tenant_domains FOR UPDATE "
        f"TO {app_role} USING ({PLATFORM_OR_SYSTEM}) WITH CHECK ({PLATFORM_OR_SYSTEM})"
    )
    op.execute("ALTER TABLE outbox_messages ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY outbox_messages_tenant_isolation ON outbox_messages FOR ALL "
        f"TO {app_role} USING (tenant_id = {T}) WITH CHECK (tenant_id = {T})"
    )
    op.execute(
        f"CREATE POLICY outbox_messages_system ON outbox_messages FOR ALL TO {app_role} "
        f"USING ({REALM} = 'system') WITH CHECK ({REALM} = 'system')"
    )


def downgrade() -> None:
    public_leads = "SELECT id FROM leads WHERE created_by_membership_id IS NULL"
    op.execute(
        "DO $$ BEGIN "
        f"IF EXISTS (SELECT 1 FROM applications WHERE lead_id IN ({public_leads})) "
        "OR EXISTS (SELECT 1 FROM leads WHERE duplicate_of_lead_id IS NOT NULL "
        f"AND duplicate_of_lead_id IN ({public_leads})) THEN "
        "RAISE EXCEPTION 'public enquiry leads are linked to applications or duplicates; "
        "attribute them before downgrading 0012'; "
        "END IF; END $$"
    )
    for table in ("lead_follow_ups", "lead_activities"):
        op.execute(f"DELETE FROM {table} WHERE lead_id IN ({public_leads})")
    op.execute("DELETE FROM leads WHERE created_by_membership_id IS NULL")
    op.drop_constraint(op.f("ck_leads_creator"), "leads", type_="check")
    op.drop_constraint(op.f("ck_leads_consent"), "leads", type_="check")
    op.alter_column("leads", "created_by_membership_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("leads", "consented_at")
    op.drop_column("leads", "consent_version")
    op.drop_table("outbox_messages")  # drops its indexes and policies
    for policy in DOMAIN_POLICIES:
        op.execute(f"DROP POLICY {policy} ON tenant_domains")
    op.drop_table("tenant_domains")
