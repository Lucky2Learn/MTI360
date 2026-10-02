# Policy SQL is assembled only from the constants below (no input): S608/S105 are false positives.
# ruff: noqa: S608, S105
"""Platform identity and MFA: platform users, credentials, roles, sessions, MFA (T01-06).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-02

Platform realm (ADR-0005, ADR-0010; locked decisions D6-1 … D6-5):
platform_users, platform_user_credentials, platform_user_roles,
platform_sessions, platform_mfa_factors, platform_recovery_codes,
platform_password_reset_tokens. Tenant realm (optional MFA): user_mfa_factors,
user_recovery_codes, and two columns on user_sessions (mfa_pending,
mfa_failed_attempts).

Row-Level Security reads only trusted transaction-local settings:

* app.realm, and **app.platform_user_id** — published by context_transaction
  for platform-realm principals (never app.user_id, which names a `users` row);
* platform **pre-authentication lookup keys**, published only by
  app.modules.platform_identity.lookup and matched by equality:
    - app.platform_auth_email          canonical email (sign-in, reset request)
    - app.platform_auth_token_hash     HMAC of a platform reset token
    - app.platform_session_token_hash  HMAC of the presented platform session token
    - app.platform_mfa_reset_user_id   the target of an authorized MFA reset (D6-3)

Every platform policy also requires app.realm = 'platform' (or the system
realm), so tenant contexts see no platform row. Credentials, MFA factors,
recovery codes and reset tokens are visible only for the principal's own
row (or the single row a lookup key names). The read-only role gets nothing.
No SECURITY DEFINER functions.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from migrations.helpers import database_roles, quote_role

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies at this revision.
PLATFORM_USER_STATUSES = ("INVITED", "ACTIVE", "SUSPENDED")
PLATFORM_ROLES = (
    "SUPER_ADMIN",
    "PLATFORM_OPERATIONS_ADMIN",
    "CUSTOMER_SUCCESS_ADMIN",
    "BILLING_ADMIN",
    "SUPPORT_ADMIN",
    "SECURITY_AUDIT_ADMIN",
    "AI_PLATFORM_ADMIN",
)
PLATFORM_REVOKE_REASONS = (
    "logout",
    "rotated",
    "password_reset",
    "mfa_failed",
    "mfa_reset",
    "break_glass",
)
TENANT_REVOKE_REASONS_BEFORE = ("logout", "rotated", "password_reset")
TENANT_REVOKE_REASONS = (*TENANT_REVOKE_REASONS_BEFORE, "mfa_failed")
MFA_KINDS = ("totp",)
HASH = "~ '^[0-9a-f]{64}$'"

SYSTEM = "nullif(current_setting('app.realm', true), '') = 'system'"
PLATFORM = "nullif(current_setting('app.realm', true), '') = 'platform'"
U = "nullif(current_setting('app.user_id', true), '')::uuid"
PU = "nullif(current_setting('app.platform_user_id', true), '')::uuid"
P_EMAIL = "nullif(current_setting('app.platform_auth_email', true), '')"
P_TOKEN = "nullif(current_setting('app.platform_auth_token_hash', true), '')"
P_SESSION = "nullif(current_setting('app.platform_session_token_hash', true), '')"
P_TARGET = "nullif(current_setting('app.platform_mfa_reset_user_id', true), '')::uuid"


def _platform(condition: str) -> str:
    return f"{SYSTEM} OR ({PLATFORM} AND ({condition}))"


OWN = f"platform_user_id = {PU}"
RESET_TARGET = f"({PU} IS NOT NULL AND platform_user_id = {P_TARGET})"
EMAIL_SUBJECT = f"platform_user_id IN (SELECT u.id FROM platform_users u WHERE u.email = {P_EMAIL})"

PLATFORM_TABLES = (
    "platform_users",
    "platform_user_credentials",
    "platform_user_roles",
    "platform_sessions",
    "platform_mfa_factors",
    "platform_recovery_codes",
    "platform_password_reset_tokens",
)
TENANT_TABLES = ("user_mfa_factors", "user_recovery_codes")
TABLES = (*PLATFORM_TABLES, *TENANT_TABLES)
PRIVILEGES = dict.fromkeys(TABLES, "SELECT, INSERT, UPDATE") | {
    "platform_user_roles": "SELECT, INSERT, DELETE"
}

# (table, policy, command, USING, WITH CHECK) — for the application role.
POLICIES: tuple[tuple[str, str, str, str | None, str | None], ...] = (
    (
        "platform_users",
        "platform_users_select",
        "SELECT",
        _platform(f"{PU} IS NOT NULL OR email = {P_EMAIL}"),
        None,
    ),
    ("platform_users", "platform_users_insert", "INSERT", None, SYSTEM),
    (
        "platform_users",
        "platform_users_update",
        "UPDATE",
        _platform(f"id = {PU}"),
        _platform(f"id = {PU}"),
    ),
    (
        "platform_user_credentials",
        "platform_user_credentials_select",
        "SELECT",
        _platform(f"{OWN} OR {EMAIL_SUBJECT}"),
        None,
    ),
    ("platform_user_credentials", "platform_user_credentials_insert", "INSERT", None, SYSTEM),
    (
        "platform_user_credentials",
        "platform_user_credentials_update",
        "UPDATE",
        _platform(f"{OWN} OR {EMAIL_SUBJECT}"),
        _platform(f"{OWN} OR {EMAIL_SUBJECT}"),
    ),
    (
        "platform_user_roles",
        "platform_user_roles_select",
        "SELECT",
        _platform(f"{PU} IS NOT NULL"),
        None,
    ),
    ("platform_user_roles", "platform_user_roles_insert", "INSERT", None, SYSTEM),
    ("platform_user_roles", "platform_user_roles_delete", "DELETE", SYSTEM, None),
    (
        "platform_sessions",
        "platform_sessions_select",
        "SELECT",
        _platform(f"{OWN} OR token_hash = {P_SESSION} OR {RESET_TARGET}"),
        None,
    ),
    ("platform_sessions", "platform_sessions_insert", "INSERT", None, _platform(OWN)),
    (
        "platform_sessions",
        "platform_sessions_update",
        "UPDATE",
        _platform(f"{OWN} OR token_hash = {P_SESSION} OR {RESET_TARGET}"),
        _platform(f"{OWN} OR token_hash = {P_SESSION} OR {RESET_TARGET}"),
    ),
    *(
        (table, f"{table}_{command.lower()}", command, using, check)
        for table in ("platform_mfa_factors", "platform_recovery_codes")
        for command, using, check in (
            ("SELECT", _platform(f"{OWN} OR {RESET_TARGET}"), None),
            ("INSERT", None, _platform(OWN)),
            (
                "UPDATE",
                _platform(f"{OWN} OR {RESET_TARGET}"),
                _platform(f"{OWN} OR {RESET_TARGET}"),
            ),
        )
    ),
    (
        "platform_password_reset_tokens",
        "platform_password_reset_tokens_select",
        "SELECT",
        _platform(f"{OWN} OR token_hash = {P_TOKEN}"),
        None,
    ),
    (
        "platform_password_reset_tokens",
        "platform_password_reset_tokens_insert",
        "INSERT",
        None,
        _platform(OWN),
    ),
    (
        "platform_password_reset_tokens",
        "platform_password_reset_tokens_update",
        "UPDATE",
        _platform(OWN),
        _platform(OWN),
    ),
    *(
        (table, f"{table}_{command.lower()}", command, using, check)
        for table in TENANT_TABLES
        for command, using, check in (
            ("SELECT", f"user_id = {U} OR {SYSTEM}", None),
            ("INSERT", None, f"user_id = {U} OR {SYSTEM}"),
            ("UPDATE", f"user_id = {U} OR {SYSTEM}", f"user_id = {U} OR {SYSTEM}"),
        )
    ),
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


def _ts(name: str, *, nullable: bool = True) -> sa.Column[Any]:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _fk(table: str, column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"fk_{table}_{column}_{target}"), ondelete="RESTRICT"
    )


def _mfa_tables(prefix: str, owner: str, owner_table: str) -> None:
    factors, codes = f"{prefix}_mfa_factors", f"{prefix}_recovery_codes"
    op.create_table(
        factors,
        _uuid("id"),
        _uuid(owner),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("secret_ciphertext", sa.String(length=512), nullable=False),
        _ts("confirmed_at"),
        sa.Column("last_used_step", sa.BigInteger(), nullable=True),
        _ts("disabled_at"),
        sa.Column("disabled_reason", sa.String(length=32), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(_in("kind", MFA_KINDS), name=op.f(f"ck_{factors}_kind")),
        sa.CheckConstraint(
            "(disabled_at IS NULL) = (disabled_reason IS NULL)", name=op.f(f"ck_{factors}_disabled")
        ),
        _fk(factors, owner, owner_table),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{factors}")),
    )
    op.create_index(
        f"uq_{factors}_{owner}_live",
        factors,
        [owner],
        unique=True,
        postgresql_where=sa.text("disabled_at IS NULL"),
    )
    op.create_table(
        codes,
        _uuid("id"),
        _uuid(owner),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        _ts("used_at"),
        _ts("invalidated_at"),
        *_timestamps(),
        sa.CheckConstraint(f"code_hash {HASH}", name=op.f(f"ck_{codes}_code_hash")),
        _fk(codes, owner, owner_table),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{codes}")),
        sa.UniqueConstraint("code_hash", name=op.f(f"uq_{codes}_code_hash")),
    )
    op.create_index(
        f"ix_{codes}_{owner}_open",
        codes,
        [owner],
        postgresql_where=sa.text("used_at IS NULL AND invalidated_at IS NULL"),
    )


def upgrade() -> None:
    roles = database_roles()
    app_role, readonly_role = quote_role(roles["app"]), quote_role(roles["readonly"])

    op.create_table(
        "platform_users",
        _uuid("id"),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        *_timestamps(version=True),
        sa.CheckConstraint(
            "email = lower(btrim(email)) AND email LIKE '%_@_%'",
            name=op.f("ck_platform_users_email"),
        ),
        sa.CheckConstraint(
            "btrim(display_name) <> ''", name=op.f("ck_platform_users_display_name")
        ),
        sa.CheckConstraint(
            _in("status", PLATFORM_USER_STATUSES), name=op.f("ck_platform_users_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_users")),
        sa.UniqueConstraint("email", name=op.f("uq_platform_users_email")),
    )
    op.create_table(
        "platform_user_credentials",
        _uuid("id"),
        _uuid("platform_user_id"),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        _ts("password_changed_at", nullable=False),
        sa.Column("failed_login_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        _ts("locked_until"),
        *_timestamps(),
        sa.CheckConstraint(
            "failed_login_count >= 0", name=op.f("ck_platform_user_credentials_failed_login_count")
        ),
        _fk("platform_user_credentials", "platform_user_id", "platform_users"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_user_credentials")),
        sa.UniqueConstraint(
            "platform_user_id", name=op.f("uq_platform_user_credentials_platform_user_id")
        ),
    )
    op.create_table(
        "platform_user_roles",
        _uuid("id"),
        _uuid("platform_user_id"),
        sa.Column("role_code", sa.String(length=32), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            _in("role_code", PLATFORM_ROLES), name=op.f("ck_platform_user_roles_role_code")
        ),
        _fk("platform_user_roles", "platform_user_id", "platform_users"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_user_roles")),
        sa.UniqueConstraint(
            "platform_user_id",
            "role_code",
            name=op.f("uq_platform_user_roles_platform_user_id_role_code"),
        ),
    )
    op.create_table(
        "platform_sessions",
        _uuid("id"),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        _uuid("platform_user_id"),
        _ts("mfa_verified_at"),
        sa.Column("mfa_failed_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        _ts("last_seen_at", nullable=False),
        _ts("idle_expires_at", nullable=False),
        _ts("absolute_expires_at", nullable=False),
        _ts("revoked_at"),
        sa.Column("revoke_reason", sa.String(length=32), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(f"token_hash {HASH}", name=op.f("ck_platform_sessions_token_hash")),
        sa.CheckConstraint(
            _in("revoke_reason", PLATFORM_REVOKE_REASONS),
            name=op.f("ck_platform_sessions_revoke_reason"),
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL) = (revoke_reason IS NULL)",
            name=op.f("ck_platform_sessions_revocation"),
        ),
        sa.CheckConstraint(
            "mfa_failed_attempts >= 0", name=op.f("ck_platform_sessions_mfa_failed_attempts")
        ),
        _fk("platform_sessions", "platform_user_id", "platform_users"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_platform_sessions_token_hash")),
    )
    op.create_index(
        "ix_platform_sessions_platform_user_id_live",
        "platform_sessions",
        ["platform_user_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    _mfa_tables("platform", "platform_user_id", "platform_users")
    op.create_table(
        "platform_password_reset_tokens",
        _uuid("id"),
        _uuid("platform_user_id"),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        _ts("expires_at", nullable=False),
        _ts("used_at"),
        _ts("invalidated_at"),
        *_timestamps(),
        sa.CheckConstraint(
            f"token_hash {HASH}", name=op.f("ck_platform_password_reset_tokens_token_hash")
        ),
        _fk("platform_password_reset_tokens", "platform_user_id", "platform_users"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_password_reset_tokens")),
        sa.UniqueConstraint(
            "token_hash", name=op.f("uq_platform_password_reset_tokens_token_hash")
        ),
    )
    op.create_index(
        "ix_platform_password_reset_tokens_platform_user_id_open",
        "platform_password_reset_tokens",
        ["platform_user_id"],
        postgresql_where=sa.text("used_at IS NULL AND invalidated_at IS NULL"),
    )

    # --- Tenant realm: optional MFA ------------------------------------------------------
    _mfa_tables("user", "user_id", "users")
    op.add_column(
        "user_sessions",
        sa.Column("mfa_pending", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "user_sessions",
        sa.Column("mfa_failed_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_user_sessions_mfa_failed_attempts"), "user_sessions", "mfa_failed_attempts >= 0"
    )
    op.create_check_constraint(
        op.f("ck_user_sessions_pending_no_tenant"),
        "user_sessions",
        "NOT mfa_pending OR active_tenant_id IS NULL",
    )
    op.drop_constraint(op.f("ck_user_sessions_revoke_reason"), "user_sessions", type_="check")
    op.create_check_constraint(
        op.f("ck_user_sessions_revoke_reason"),
        "user_sessions",
        _in("revoke_reason", TENANT_REVOKE_REASONS),
    )

    # --- Privileges: replace the defaults; nothing for read-only -------------------------
    for table in TABLES:
        op.execute(f"REVOKE ALL ON TABLE {table} FROM {app_role}, {readonly_role}")
        op.execute(f"GRANT {PRIVILEGES[table]} ON TABLE {table} TO {app_role}")

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
    # Before 0006 a session cannot be MFA-pending: end every live pending
    # session (it would otherwise become a session that skipped MFA), and map
    # the reasons 0005 does not know.
    op.execute(
        "UPDATE user_sessions SET revoked_at = now(), revoke_reason = 'logout' "
        "WHERE mfa_pending AND revoked_at IS NULL"
    )
    op.execute(
        "UPDATE user_sessions SET revoke_reason = 'logout' "
        f"WHERE revoke_reason NOT IN ({', '.join(repr(r) for r in TENANT_REVOKE_REASONS_BEFORE)})"
    )
    op.drop_constraint(op.f("ck_user_sessions_revoke_reason"), "user_sessions", type_="check")
    op.create_check_constraint(
        op.f("ck_user_sessions_revoke_reason"),
        "user_sessions",
        _in("revoke_reason", TENANT_REVOKE_REASONS_BEFORE),
    )
    op.drop_constraint(op.f("ck_user_sessions_pending_no_tenant"), "user_sessions", type_="check")
    op.drop_constraint(op.f("ck_user_sessions_mfa_failed_attempts"), "user_sessions", type_="check")
    op.drop_column("user_sessions", "mfa_failed_attempts")
    op.drop_column("user_sessions", "mfa_pending")
    for table in reversed(TABLES):
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    for table in (
        "user_recovery_codes",
        "user_mfa_factors",
        "platform_password_reset_tokens",
        "platform_recovery_codes",
        "platform_mfa_factors",
        "platform_sessions",
        "platform_user_roles",
        "platform_user_credentials",
        "platform_users",
    ):
        op.drop_table(table)
