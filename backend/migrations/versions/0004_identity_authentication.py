# Policy SQL is assembled only from the constants below (no input): S608/S105 are false positives.
# ruff: noqa: S608, S105
"""Identity and authentication: users, credentials, memberships, sessions, tokens (T01-04).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-02

Tables (in dependency order): users, user_credentials, tenant_memberships,
membership_campuses, user_sessions, password_reset_tokens, user_invitations.

Privileges replace the defaults of database/init/01-roles.sh: the application
role gets SELECT, INSERT and UPDATE (membership_campuses: SELECT, INSERT);
nothing is hard-deleted. The read-only role gets **nothing** on these tables
(identity data and credentials; decision D16).

Row-Level Security (enabled, not forced; the runtime roles stay NOBYPASSRLS).
Policies read only the trusted, transaction-local settings published with
SET LOCAL:

* app.realm, app.tenant_id, app.user_id (T01-01 context);
* the T01-04 **pre-authentication lookup keys** (decision D01), published only
  by the identity module's lookup transactions:
    - app.auth_email          canonical email (sign-in, password-reset request)
    - app.auth_token_hash     HMAC of a reset or invitation token
    - app.session_token_hash  HMAC of the presented session token
  Each key matches by equality only, so it can reach exactly the one identity,
  token or session it names — never a tenant's data. No SECURITY DEFINER
  functions are used.

The system realm (system_context: seed, jobs, tests) can read and write all
identity rows. No policy gives a tenant context access to credentials, reset
tokens or other users' sessions.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from migrations.helpers import database_roles, quote_role

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies at this revision (never import app enums into migrations).
USER_STATUSES = ("INVITED", "ACTIVE", "DISABLED")
MEMBERSHIP_STATUSES = ("INVITED", "ACTIVE", "SUSPENDED", "REVOKED")
CAMPUS_SCOPES = ("ALL", "SELECTED")
REVOKE_REASONS = ("logout", "rotated", "password_reset")
TOKEN_HASH = "token_hash ~ '^[0-9a-f]{64}$'"

T = "nullif(current_setting('app.tenant_id', true), '')::uuid"
U = "nullif(current_setting('app.user_id', true), '')::uuid"
SYSTEM = "nullif(current_setting('app.realm', true), '') = 'system'"
AUTH_EMAIL = "nullif(current_setting('app.auth_email', true), '')"
AUTH_TOKEN_HASH = "nullif(current_setting('app.auth_token_hash', true), '')"
SESSION_TOKEN_HASH = "nullif(current_setting('app.session_token_hash', true), '')"

TABLES = (
    "users",
    "user_credentials",
    "tenant_memberships",
    "membership_campuses",
    "user_sessions",
    "password_reset_tokens",
    "user_invitations",
)


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _timestamps(*, version: bool = False) -> list[sa.Column[Any]]:
    columns: list[sa.Column[Any]] = [
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
    if version:
        columns.append(sa.Column("version", sa.Integer(), nullable=False))
    return columns


def _uuid(name: str, *, nullable: bool = False) -> sa.Column[Any]:
    return sa.Column(name, sa.Uuid(), nullable=nullable)


def _restrict_fk(table: str, columns: list[str], target: str, target_columns: list[str]) -> Any:
    name = f"fk_{table}_{'_'.join(columns)}_{target}"
    return sa.ForeignKeyConstraint(
        columns, [f"{target}.{c}" for c in target_columns], name=op.f(name), ondelete="RESTRICT"
    )


# (table, policy, command, roles key, USING, WITH CHECK)
POLICIES: tuple[tuple[str, str, str, str | None, str | None], ...] = (
    # users: own identity, members of the active tenant, the pre-auth email, system.
    (
        "users",
        "users_select",
        "SELECT",
        f"id = {U} OR id IN (SELECT m.user_id FROM tenant_memberships m WHERE m.tenant_id = {T}) "
        f"OR email = {AUTH_EMAIL} OR {SYSTEM}",
        None,
    ),
    ("users", "users_insert", "INSERT", None, SYSTEM),
    ("users", "users_update", "UPDATE", f"id = {U} OR {SYSTEM}", f"id = {U} OR {SYSTEM}"),
    # user_credentials: only the user's own row, the pre-auth email, system.
    (
        "user_credentials",
        "user_credentials_select",
        "SELECT",
        f"user_id = {U} OR {SYSTEM} "
        f"OR user_id IN (SELECT u.id FROM users u WHERE u.email = {AUTH_EMAIL})",
        None,
    ),
    ("user_credentials", "user_credentials_insert", "INSERT", None, f"user_id = {U} OR {SYSTEM}"),
    (
        "user_credentials",
        "user_credentials_update",
        "UPDATE",
        f"user_id = {U} OR {SYSTEM} "
        f"OR user_id IN (SELECT u.id FROM users u WHERE u.email = {AUTH_EMAIL})",
        f"user_id = {U} OR {SYSTEM} "
        f"OR user_id IN (SELECT u.id FROM users u WHERE u.email = {AUTH_EMAIL})",
    ),
    # tenant_memberships: the active tenant, the user's own memberships (tenant
    # discovery before a tenant is active), the invitation being looked up, system.
    (
        "tenant_memberships",
        "tenant_memberships_select",
        "SELECT",
        f"tenant_id = {T} OR user_id = {U} OR {SYSTEM} OR id IN "
        f"(SELECT i.membership_id FROM user_invitations i WHERE i.token_hash = {AUTH_TOKEN_HASH})",
        None,
    ),
    (
        "tenant_memberships",
        "tenant_memberships_insert",
        "INSERT",
        None,
        f"tenant_id = {T} OR {SYSTEM}",
    ),
    (
        "tenant_memberships",
        "tenant_memberships_update",
        "UPDATE",
        f"tenant_id = {T} OR {SYSTEM}",
        f"tenant_id = {T} OR {SYSTEM}",
    ),
    # membership_campuses: the active tenant, the user's own memberships, system.
    (
        "membership_campuses",
        "membership_campuses_select",
        "SELECT",
        f"tenant_id = {T} OR {SYSTEM} OR membership_id IN "
        f"(SELECT m.id FROM tenant_memberships m WHERE m.user_id = {U})",
        None,
    ),
    (
        "membership_campuses",
        "membership_campuses_insert",
        "INSERT",
        None,
        f"tenant_id = {T} OR {SYSTEM}",
    ),
    # user_sessions: the user's own sessions, the presented token, system.
    (
        "user_sessions",
        "user_sessions_select",
        "SELECT",
        f"user_id = {U} OR token_hash = {SESSION_TOKEN_HASH} OR {SYSTEM}",
        None,
    ),
    ("user_sessions", "user_sessions_insert", "INSERT", None, f"user_id = {U} OR {SYSTEM}"),
    (
        "user_sessions",
        "user_sessions_update",
        "UPDATE",
        f"user_id = {U} OR token_hash = {SESSION_TOKEN_HASH} OR {SYSTEM}",
        f"user_id = {U} OR token_hash = {SESSION_TOKEN_HASH} OR {SYSTEM}",
    ),
    # password_reset_tokens: the user's own tokens, the presented token, system.
    (
        "password_reset_tokens",
        "password_reset_tokens_select",
        "SELECT",
        f"user_id = {U} OR token_hash = {AUTH_TOKEN_HASH} OR {SYSTEM}",
        None,
    ),
    (
        "password_reset_tokens",
        "password_reset_tokens_insert",
        "INSERT",
        None,
        f"user_id = {U} OR {SYSTEM}",
    ),
    (
        "password_reset_tokens",
        "password_reset_tokens_update",
        "UPDATE",
        f"user_id = {U} OR {SYSTEM}",
        f"user_id = {U} OR {SYSTEM}",
    ),
    # user_invitations: the active tenant, the presented token, system.
    (
        "user_invitations",
        "user_invitations_select",
        "SELECT",
        f"tenant_id = {T} OR token_hash = {AUTH_TOKEN_HASH} OR {SYSTEM}",
        None,
    ),
    ("user_invitations", "user_invitations_insert", "INSERT", None, f"tenant_id = {T} OR {SYSTEM}"),
    (
        "user_invitations",
        "user_invitations_update",
        "UPDATE",
        f"tenant_id = {T} OR {SYSTEM}",
        f"tenant_id = {T} OR {SYSTEM}",
    ),
    # tenants (T01-03 registry): a signed-in user may read the tenants of their
    # own memberships (institute choices before a tenant is active), and the
    # tenant of the invitation being looked up (institute name in the preview).
    (
        "tenants",
        "tenants_member_read",
        "SELECT",
        f"id IN (SELECT m.tenant_id FROM tenant_memberships m WHERE m.user_id = {U}) OR id IN "
        f"(SELECT i.tenant_id FROM user_invitations i WHERE i.token_hash = {AUTH_TOKEN_HASH})",
        None,
    ),
)


def upgrade() -> None:
    roles = database_roles()
    app_role, readonly_role = quote_role(roles["app"]), quote_role(roles["readonly"])

    op.create_table(
        "users",
        _uuid("id"),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(version=True),
        sa.CheckConstraint(
            "email = lower(btrim(email)) AND email LIKE '%_@_%'", name=op.f("ck_users_email")
        ),
        sa.CheckConstraint("btrim(display_name) <> ''", name=op.f("ck_users_display_name")),
        sa.CheckConstraint(_in("status", USER_STATUSES), name=op.f("ck_users_status")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "user_credentials",
        _uuid("id"),
        _uuid("user_id"),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failed_login_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "failed_login_count >= 0", name=op.f("ck_user_credentials_failed_login_count")
        ),
        _restrict_fk("user_credentials", ["user_id"], "users", ["id"]),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_credentials")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_credentials_user_id")),
    )
    op.create_table(
        "tenant_memberships",
        _uuid("id"),
        _uuid("tenant_id"),
        _uuid("user_id"),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("campus_scope", sa.String(length=16), nullable=False),
        _uuid("invited_by", nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(version=True),
        sa.CheckConstraint(
            _in("status", MEMBERSHIP_STATUSES), name=op.f("ck_tenant_memberships_status")
        ),
        sa.CheckConstraint(
            _in("campus_scope", CAMPUS_SCOPES), name=op.f("ck_tenant_memberships_campus_scope")
        ),
        _restrict_fk("tenant_memberships", ["tenant_id"], "tenants", ["id"]),
        _restrict_fk("tenant_memberships", ["user_id"], "users", ["id"]),
        _restrict_fk("tenant_memberships", ["invited_by"], "users", ["id"]),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_memberships")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_tenant_memberships_tenant_id_id")),
        sa.UniqueConstraint(
            "tenant_id", "user_id", name=op.f("uq_tenant_memberships_tenant_id_user_id")
        ),
    )
    op.create_index(op.f("ix_tenant_memberships_user_id"), "tenant_memberships", ["user_id"])
    op.create_table(
        "membership_campuses",
        _uuid("id"),
        _uuid("tenant_id"),
        _uuid("membership_id"),
        _uuid("campus_id"),
        *_timestamps(),
        _restrict_fk("membership_campuses", ["tenant_id"], "tenants", ["id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_membership_campuses_membership",
            ondelete="RESTRICT",
        ),
        _restrict_fk(
            "membership_campuses", ["tenant_id", "campus_id"], "campuses", ["tenant_id", "id"]
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_membership_campuses")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_membership_campuses_tenant_id_id")),
        sa.UniqueConstraint(
            "membership_id",
            "campus_id",
            name=op.f("uq_membership_campuses_membership_id_campus_id"),
        ),
    )
    op.create_table(
        "user_sessions",
        _uuid("id"),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        _uuid("user_id"),
        sa.Column("realm", sa.String(length=16), nullable=False),
        _uuid("active_tenant_id", nullable=True),
        _uuid("active_campus_id", nullable=True),
        sa.Column("mfa_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=32), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(TOKEN_HASH, name=op.f("ck_user_sessions_token_hash")),
        sa.CheckConstraint("realm IN ('tenant')", name=op.f("ck_user_sessions_realm")),
        sa.CheckConstraint(
            _in("revoke_reason", REVOKE_REASONS), name=op.f("ck_user_sessions_revoke_reason")
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL) = (revoke_reason IS NULL)",
            name=op.f("ck_user_sessions_revocation"),
        ),
        sa.CheckConstraint(
            "active_campus_id IS NULL OR active_tenant_id IS NOT NULL",
            name=op.f("ck_user_sessions_campus_needs_tenant"),
        ),
        _restrict_fk("user_sessions", ["user_id"], "users", ["id"]),
        _restrict_fk(
            "user_sessions",
            ["active_tenant_id", "user_id"],
            "tenant_memberships",
            ["tenant_id", "user_id"],
        ),
        _restrict_fk(
            "user_sessions",
            ["active_tenant_id", "active_campus_id"],
            "campuses",
            ["tenant_id", "id"],
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_user_sessions_token_hash")),
    )
    op.create_index(
        "ix_user_sessions_user_id_live",
        "user_sessions",
        ["user_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_table(
        "password_reset_tokens",
        _uuid("id"),
        _uuid("user_id"),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(TOKEN_HASH, name=op.f("ck_password_reset_tokens_token_hash")),
        _restrict_fk("password_reset_tokens", ["user_id"], "users", ["id"]),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_password_reset_tokens_token_hash")),
    )
    op.create_index(
        "ix_password_reset_tokens_user_id_open",
        "password_reset_tokens",
        ["user_id"],
        postgresql_where=sa.text("used_at IS NULL AND invalidated_at IS NULL"),
    )
    op.create_table(
        "user_invitations",
        _uuid("id"),
        _uuid("tenant_id"),
        _uuid("membership_id"),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        _uuid("invited_by", nullable=True),
        *_timestamps(),
        sa.CheckConstraint(TOKEN_HASH, name=op.f("ck_user_invitations_token_hash")),
        _restrict_fk("user_invitations", ["tenant_id"], "tenants", ["id"]),
        _restrict_fk(
            "user_invitations",
            ["tenant_id", "membership_id"],
            "tenant_memberships",
            ["tenant_id", "id"],
        ),
        _restrict_fk("user_invitations", ["invited_by"], "users", ["id"]),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_invitations")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_user_invitations_tenant_id_id")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_user_invitations_token_hash")),
    )

    # --- Privileges: replace the defaults; no DELETE, nothing for read-only ----------
    for table in TABLES:
        op.execute(f"REVOKE ALL ON TABLE {table} FROM {app_role}, {readonly_role}")
        privileges = (
            "SELECT, INSERT" if table == "membership_campuses" else "SELECT, INSERT, UPDATE"
        )
        op.execute(f"GRANT {privileges} ON TABLE {table} TO {app_role}")

    # --- Row-Level Security ------------------------------------------------------------
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    for table, name, command, using, check in POLICIES:
        clauses = ""
        if using is not None:
            clauses += f" USING ({using})"
        if check is not None:
            clauses += f" WITH CHECK ({check})"
        op.execute(f"CREATE POLICY {name} ON {table} FOR {command} TO {app_role}{clauses}")


def downgrade() -> None:
    for table, name, *_ in reversed(POLICIES):
        op.execute(f"DROP POLICY {name} ON {table}")
    for table in reversed(TABLES):
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.drop_table(table)
