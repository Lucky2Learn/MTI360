# Policy SQL is assembled only from the constants below (no input): S608/S105 are false positives.
# ruff: noqa: S608, S105
"""Platform administration: provisioning, platform user administration, invitations (T01-07).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-03

Locked decisions D7-1 … D7-10 (docs/architecture/platform-administration.md):

* ``platform_user_invitations`` (D7-3): single-use onboarding tokens (HMAC).
* ``tenants.owner_membership_id`` (D7-1, D7-8): the primary administrator's
  membership, kept inside the tenant by a composite foreign key.
* ``user_sessions`` revoke reason ``tenant_suspended`` (D7-6) and
  ``platform_sessions`` revoke reason ``admin_suspended`` (D7-4).

Row-Level Security: existing policies are **altered in place** (same names,
the 0004-0006 expressions plus one narrow, equality-matched term each); the
downgrade restores the frozen expressions. New transaction-local keys:

* ``app.provisioning_tenant_id`` — published only by
  ``app.modules.tenants.scopes`` together with the same ``app.tenant_id`` in a
  platform-realm provisioning transaction: the new tenant's system roles and
  their permissions, and an ``INVITED`` owner identity (D7-1);
* ``app.platform_target_tenant_id`` — the tenant being suspended: its sessions
  only (D7-6);
* ``app.platform_owner_membership_id`` — one tenant's owner membership, its
  invitations and its user (D7-8);
* ``app.platform_admin_target_user_id`` — published only by
  ``app.modules.platform_identity.lookup`` after ``authorize()``: one platform
  user's row, roles, sessions and invitations (D7-2);
* ``app.platform_auth_token_hash`` (0006) now also names a platform invitation:
  that invitation, its user and the user's first credential (D7-3).

Every new term requires ``app.realm = 'platform'`` (tenant contexts gain
nothing) and the administrator terms an authenticated platform principal. The
read-only role gets nothing new. No SECURITY DEFINER functions.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from migrations.helpers import database_roles, quote_role

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies at this revision.
TENANT_REVOKE_REASONS_BEFORE = ("logout", "rotated", "password_reset", "mfa_failed")
TENANT_REVOKE_REASONS = (*TENANT_REVOKE_REASONS_BEFORE, "tenant_suspended")
PLATFORM_REVOKE_REASONS_BEFORE = (
    "logout",
    "rotated",
    "password_reset",
    "mfa_failed",
    "mfa_reset",
    "break_glass",
)
PLATFORM_REVOKE_REASONS = (*PLATFORM_REVOKE_REASONS_BEFORE, "admin_suspended")
HASH = "~ '^[0-9a-f]{64}$'"

T = "nullif(current_setting('app.tenant_id', true), '')::uuid"
U = "nullif(current_setting('app.user_id', true), '')::uuid"
SYSTEM = "nullif(current_setting('app.realm', true), '') = 'system'"
PLATFORM = "nullif(current_setting('app.realm', true), '') = 'platform'"
AUTH_EMAIL = "nullif(current_setting('app.auth_email', true), '')"
AUTH_TOKEN_HASH = "nullif(current_setting('app.auth_token_hash', true), '')"
SESSION_TOKEN_HASH = "nullif(current_setting('app.session_token_hash', true), '')"
PU = "nullif(current_setting('app.platform_user_id', true), '')::uuid"
P_EMAIL = "nullif(current_setting('app.platform_auth_email', true), '')"
P_TOKEN = "nullif(current_setting('app.platform_auth_token_hash', true), '')"
P_SESSION = "nullif(current_setting('app.platform_session_token_hash', true), '')"
P_TARGET = "nullif(current_setting('app.platform_mfa_reset_user_id', true), '')::uuid"
# New in 0007.
PROVISIONING = "nullif(current_setting('app.provisioning_tenant_id', true), '')::uuid"
TARGET_TENANT = "nullif(current_setting('app.platform_target_tenant_id', true), '')::uuid"
OWNER = "nullif(current_setting('app.platform_owner_membership_id', true), '')::uuid"
ADMIN_TARGET = "nullif(current_setting('app.platform_admin_target_user_id', true), '')::uuid"


def _platform(condition: str) -> str:
    return f"{SYSTEM} OR ({PLATFORM} AND ({condition}))"


# --- Terms --------------------------------------------------------------------------------
# D7-1: the provisioning transaction publishes the new tenant twice (app.tenant_id and
# app.provisioning_tenant_id); both must name the row's tenant.
PROVISIONED = f"({PLATFORM} AND tenant_id = {T} AND tenant_id = {PROVISIONING})"
PROVISIONED_OWNER = f"({PLATFORM} AND {PROVISIONING} = {T} AND status = 'INVITED')"
# D7-8: one owner membership.
OWNER_MEMBERSHIP = f"({PLATFORM} AND id = {OWNER})"
OWNER_INVITATIONS = f"({PLATFORM} AND membership_id = {OWNER})"
OWNER_USER = (
    f"({PLATFORM} AND id IN (SELECT m.user_id FROM tenant_memberships m WHERE m.id = {OWNER}))"
)
# D7-6: the sessions whose active institute is the tenant being suspended.
SUSPENDED_SESSIONS = f"({PLATFORM} AND active_tenant_id = {TARGET_TENANT})"
# D7-2: one administered platform user, for an authenticated platform principal.
ADMIN_ROW = f"({PU} IS NOT NULL AND id = {ADMIN_TARGET})"
ADMIN_OWNED = f"({PU} IS NOT NULL AND platform_user_id = {ADMIN_TARGET})"
# D7-3: the platform invitation named by the presented token.
INVITED_USER = (
    f"id IN (SELECT i.platform_user_id FROM platform_user_invitations i "
    f"WHERE i.token_hash = {P_TOKEN})"
)
INVITED_OWNER = (
    f"platform_user_id IN (SELECT i.platform_user_id FROM platform_user_invitations i "
    f"WHERE i.token_hash = {P_TOKEN})"
)

# --- 0004 / 0005 / 0006 expressions (frozen) ------------------------------------------------
OWN = f"platform_user_id = {PU}"
RESET_TARGET = f"({PU} IS NOT NULL AND platform_user_id = {P_TARGET})"
USERS_SELECT = (
    f"id = {U} OR id IN (SELECT m.user_id FROM tenant_memberships m WHERE m.tenant_id = {T}) "
    f"OR email = {AUTH_EMAIL} OR {SYSTEM}"
)
MEMBERSHIPS_SELECT = (
    f"tenant_id = {T} OR user_id = {U} OR {SYSTEM} OR id IN "
    f"(SELECT i.membership_id FROM user_invitations i WHERE i.token_hash = {AUTH_TOKEN_HASH})"
)
INVITATIONS_SELECT = f"tenant_id = {T} OR token_hash = {AUTH_TOKEN_HASH} OR {SYSTEM}"
INVITATIONS_WRITE = f"tenant_id = {T} OR {SYSTEM}"
SESSIONS_ACCESS = f"user_id = {U} OR token_hash = {SESSION_TOKEN_HASH} OR {SYSTEM}"
CUSTOM_ROLE_IN_TENANT = (
    f"role_id IN (SELECT r.id FROM roles r WHERE r.tenant_id = {T} AND NOT r.is_system)"
)
ROLES_INSERT = f"(tenant_id = {T} AND NOT is_system) OR {SYSTEM}"
ROLE_PERMISSIONS_INSERT = f"(tenant_id = {T} AND {CUSTOM_ROLE_IN_TENANT}) OR {SYSTEM}"
P_USERS_SELECT = _platform(f"{PU} IS NOT NULL OR email = {P_EMAIL}")
P_USERS_UPDATE = _platform(f"id = {PU}")
P_SESSIONS = _platform(f"{OWN} OR token_hash = {P_SESSION} OR {RESET_TARGET}")

# (table, policy, command, (USING, WITH CHECK) before, (USING, WITH CHECK) after)
Expressions = tuple[str | None, str | None]
ALTERED: tuple[tuple[str, str, str, Expressions, Expressions], ...] = (
    # D7-1 provisioning: an INVITED owner identity, the new tenant's system roles.
    ("users", "users_insert", "INSERT", (None, SYSTEM), (None, f"{SYSTEM} OR {PROVISIONED_OWNER}")),
    (
        "roles",
        "roles_insert",
        "INSERT",
        (None, ROLES_INSERT),
        (None, f"{ROLES_INSERT} OR {PROVISIONED}"),
    ),
    (
        "role_permissions",
        "role_permissions_insert",
        "INSERT",
        (None, ROLE_PERMISSIONS_INSERT),
        (None, f"{ROLE_PERMISSIONS_INSERT} OR {PROVISIONED}"),
    ),
    # D7-8 owner invitation: one membership, its invitations and its user.
    (
        "users",
        "users_select",
        "SELECT",
        (USERS_SELECT, None),
        (f"{USERS_SELECT} OR {OWNER_USER}", None),
    ),
    (
        "tenant_memberships",
        "tenant_memberships_select",
        "SELECT",
        (MEMBERSHIPS_SELECT, None),
        (f"{MEMBERSHIPS_SELECT} OR {OWNER_MEMBERSHIP}", None),
    ),
    (
        "user_invitations",
        "user_invitations_select",
        "SELECT",
        (INVITATIONS_SELECT, None),
        (f"{INVITATIONS_SELECT} OR {OWNER_INVITATIONS}", None),
    ),
    (
        "user_invitations",
        "user_invitations_insert",
        "INSERT",
        (None, INVITATIONS_WRITE),
        (None, f"{INVITATIONS_WRITE} OR {OWNER_INVITATIONS}"),
    ),
    (
        "user_invitations",
        "user_invitations_update",
        "UPDATE",
        (INVITATIONS_WRITE, INVITATIONS_WRITE),
        (
            f"{INVITATIONS_WRITE} OR {OWNER_INVITATIONS}",
            f"{INVITATIONS_WRITE} OR {OWNER_INVITATIONS}",
        ),
    ),
    # D7-6 tenant suspension: that tenant's sessions.
    (
        "user_sessions",
        "user_sessions_select",
        "SELECT",
        (SESSIONS_ACCESS, None),
        (f"{SESSIONS_ACCESS} OR {SUSPENDED_SESSIONS}", None),
    ),
    (
        "user_sessions",
        "user_sessions_update",
        "UPDATE",
        (SESSIONS_ACCESS, SESSIONS_ACCESS),
        (
            f"{SESSIONS_ACCESS} OR {SUSPENDED_SESSIONS}",
            f"{SESSIONS_ACCESS} OR {SUSPENDED_SESSIONS}",
        ),
    ),
    # D7-2 platform user administration and D7-3 invitation acceptance.
    (
        "platform_users",
        "platform_users_select",
        "SELECT",
        (P_USERS_SELECT, None),
        (_platform(f"{PU} IS NOT NULL OR email = {P_EMAIL} OR {INVITED_USER}"), None),
    ),
    (
        "platform_users",
        "platform_users_insert",
        "INSERT",
        (None, SYSTEM),
        (None, _platform(f"{ADMIN_ROW} AND status = 'INVITED'")),
    ),
    (
        "platform_users",
        "platform_users_update",
        "UPDATE",
        (P_USERS_UPDATE, P_USERS_UPDATE),
        (
            _platform(f"id = {PU} OR {ADMIN_ROW} OR {INVITED_USER}"),
            _platform(f"id = {PU} OR {ADMIN_ROW} OR {INVITED_USER}"),
        ),
    ),
    (
        "platform_user_credentials",
        "platform_user_credentials_insert",
        "INSERT",
        (None, SYSTEM),
        (None, _platform(INVITED_OWNER)),
    ),
    (
        "platform_user_roles",
        "platform_user_roles_insert",
        "INSERT",
        (None, SYSTEM),
        (None, _platform(ADMIN_OWNED)),
    ),
    (
        "platform_user_roles",
        "platform_user_roles_delete",
        "DELETE",
        (SYSTEM, None),
        (_platform(ADMIN_OWNED), None),
    ),
    (
        "platform_sessions",
        "platform_sessions_select",
        "SELECT",
        (P_SESSIONS, None),
        (_platform(f"{OWN} OR token_hash = {P_SESSION} OR {RESET_TARGET} OR {ADMIN_OWNED}"), None),
    ),
    (
        "platform_sessions",
        "platform_sessions_update",
        "UPDATE",
        (P_SESSIONS, P_SESSIONS),
        (
            _platform(f"{OWN} OR token_hash = {P_SESSION} OR {RESET_TARGET} OR {ADMIN_OWNED}"),
            _platform(f"{OWN} OR token_hash = {P_SESSION} OR {RESET_TARGET} OR {ADMIN_OWNED}"),
        ),
    ),
)

INVITATION_ACCESS = _platform(f"{ADMIN_OWNED} OR token_hash = {P_TOKEN}")
# (table, policy, command, USING, WITH CHECK) — new table, for the application role.
POLICIES: tuple[tuple[str, str, str, str | None, str | None], ...] = (
    (
        "platform_user_invitations",
        "platform_user_invitations_select",
        "SELECT",
        INVITATION_ACCESS,
        None,
    ),
    (
        "platform_user_invitations",
        "platform_user_invitations_insert",
        "INSERT",
        None,
        _platform(ADMIN_OWNED),
    ),
    (
        "platform_user_invitations",
        "platform_user_invitations_update",
        "UPDATE",
        INVITATION_ACCESS,
        INVITATION_ACCESS,
    ),
)


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _alter(name: str, table: str, expressions: Expressions) -> None:
    using, check = expressions
    clauses = ""
    if using is not None:
        clauses += f" USING ({using})"
    if check is not None:
        clauses += f" WITH CHECK ({check})"
    op.execute(f"ALTER POLICY {name} ON {table}{clauses}")


def _revoke_reasons(table: str, reasons: Sequence[str]) -> None:
    op.drop_constraint(op.f(f"ck_{table}_revoke_reason"), table, type_="check")
    op.create_check_constraint(
        op.f(f"ck_{table}_revoke_reason"), table, _in("revoke_reason", reasons)
    )


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

    op.create_table(
        "platform_user_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("platform_user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invited_by", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            f"token_hash {HASH}", name=op.f("ck_platform_user_invitations_token_hash")
        ),
        sa.CheckConstraint(
            "accepted_at IS NULL OR revoked_at IS NULL",
            name=op.f("ck_platform_user_invitations_outcome"),
        ),
        sa.ForeignKeyConstraint(
            ["platform_user_id"],
            ["platform_users.id"],
            name=op.f("fk_platform_user_invitations_platform_user_id_platform_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["platform_users.id"],
            name=op.f("fk_platform_user_invitations_invited_by_platform_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_user_invitations")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_platform_user_invitations_token_hash")),
    )
    op.create_index(
        "ix_platform_user_invitations_platform_user_id_open",
        "platform_user_invitations",
        ["platform_user_id"],
        postgresql_where=sa.text("accepted_at IS NULL AND revoked_at IS NULL"),
    )

    op.add_column("tenants", sa.Column("owner_membership_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_tenants_owner_membership",
        "tenants",
        "tenant_memberships",
        ["id", "owner_membership_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )

    _revoke_reasons("user_sessions", TENANT_REVOKE_REASONS)
    _revoke_reasons("platform_sessions", PLATFORM_REVOKE_REASONS)

    op.execute(f"REVOKE ALL ON TABLE platform_user_invitations FROM {app_role}, {readonly_role}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE platform_user_invitations TO {app_role}")
    op.execute("ALTER TABLE platform_user_invitations ENABLE ROW LEVEL SECURITY")
    for table, name, command, using, check in POLICIES:
        clauses = ""
        if using is not None:
            clauses += f" USING ({using})"
        if check is not None:
            clauses += f" WITH CHECK ({check})"
        op.execute(f"CREATE POLICY {name} ON {table} FOR {command} TO {app_role}{clauses}")
    for table, name, _command, _before, after in ALTERED:
        _alter(name, table, after)


def downgrade() -> None:
    for table, name, _command, before, _after in reversed(ALTERED):
        _alter(name, table, before)
    for table, name, *_ in reversed(POLICIES):
        op.execute(f"DROP POLICY {name} ON {table}")
    # Before 0007 the reasons do not exist: map them to a plain sign-out.
    op.execute(
        "UPDATE user_sessions SET revoke_reason = 'logout' WHERE revoke_reason = 'tenant_suspended'"
    )
    op.execute(
        "UPDATE platform_sessions SET revoke_reason = 'logout' "
        "WHERE revoke_reason = 'admin_suspended'"
    )
    _revoke_reasons("user_sessions", TENANT_REVOKE_REASONS_BEFORE)
    _revoke_reasons("platform_sessions", PLATFORM_REVOKE_REASONS_BEFORE)
    op.drop_constraint("fk_tenants_owner_membership", "tenants", type_="foreignkey")
    op.drop_column("tenants", "owner_membership_id")
    op.drop_index(
        "ix_platform_user_invitations_platform_user_id_open", table_name="platform_user_invitations"
    )
    op.drop_table("platform_user_invitations")
