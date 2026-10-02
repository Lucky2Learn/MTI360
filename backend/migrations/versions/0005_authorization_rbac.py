# SQL is assembled only from the frozen constants below (no input): S608 is a false positive.
# ruff: noqa: S608
"""Authorization and RBAC: permission catalogue, roles, role permissions, assignments (T01-05).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-02

Tables: permissions, roles, role_permissions, membership_roles.

* ``permissions`` is the catalogue, keyed by (realm, code) (D-B3). Its rows
  are written only by migrations (D-B4): this one seeds the T01-05 baseline
  from the frozen copy below. The runtime roles may only read it.
* System roles are protected by the database (D-B2):
    - Row-Level Security lets only the system realm create a system role or
      give one permissions (and migrations, which run as the table owner);
    - the triggers ``roles_protect_system`` and
      ``role_permissions_protect_system`` reject renaming, deleting or
      changing the permissions of a system role — for every database role,
      the owner included — and turning a custom role into a system role.
  The trigger functions are plain (SECURITY INVOKER) functions.
* The system roles INSTITUTE_OWNER and ADMIN are cloned for every existing
  tenant. Nobody is assigned a role: membership_roles starts empty, and roles
  are granted by tenant creation (T01-07) or an administrator (T01-08).

Privileges replace the defaults of database/init/01-roles.sh. The application
role: permissions SELECT; roles SELECT, INSERT, UPDATE, DELETE (custom roles
only, by policy and trigger); role_permissions and membership_roles SELECT,
INSERT, DELETE. The read-only role may read the permission catalogue only.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from migrations.helpers import database_roles, quote_role

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# --- Frozen copies at this revision (never import app code into migrations) -----------
# (realm, code, scope, module, description)
PERMISSIONS: tuple[tuple[str, str, str | None, str, str], ...] = (
    ("platform", "audit.read", None, "audit", "View the platform audit log"),
    ("platform", "platform_user.create", None, "platform_identity", "Add platform users"),
    (
        "platform",
        "platform_user.reactivate",
        None,
        "platform_identity",
        "Reactivate platform users",
    ),
    ("platform", "platform_user.read", None, "platform_identity", "View platform users"),
    ("platform", "platform_user.suspend", None, "platform_identity", "Suspend platform users"),
    ("platform", "platform_user.update", None, "platform_identity", "Edit platform users"),
    ("platform", "tenant.create", None, "tenants", "Provision tenants"),
    ("platform", "tenant.reactivate", None, "tenants", "Reactivate tenants"),
    ("platform", "tenant.read", None, "tenants", "View tenants"),
    ("platform", "tenant.suspend", None, "tenants", "Suspend tenants"),
    ("tenant", "audit.read", "tenant", "audit", "View the institute audit log"),
    ("tenant", "campus.create", "tenant", "institute", "Add campuses"),
    ("tenant", "campus.read", "campus", "institute", "View campuses"),
    ("tenant", "campus.update", "campus", "institute", "Edit campuses"),
    ("tenant", "member.invite", "tenant", "identity", "Invite members"),
    ("tenant", "member.read", "tenant", "identity", "View members"),
    ("tenant", "member.revoke", "tenant", "identity", "Remove members"),
    ("tenant", "member.suspend", "tenant", "identity", "Suspend members"),
    ("tenant", "member.update", "tenant", "identity", "Edit members"),
    ("tenant", "role.assign", "tenant", "access", "Assign roles to members"),
    ("tenant", "role.create", "tenant", "access", "Create custom roles"),
    ("tenant", "role.delete", "tenant", "access", "Delete custom roles"),
    ("tenant", "role.read", "tenant", "access", "View roles"),
    ("tenant", "role.update", "tenant", "access", "Edit custom roles"),
    ("tenant", "tenant.profile.read", "tenant", "tenants", "View the institute profile"),
)
TENANT_CODES = tuple(code for realm, code, *_ in PERMISSIONS if realm == "tenant")
# (template_code, name, description, permission codes)
SYSTEM_ROLES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "INSTITUTE_OWNER",
        "Institute owner",
        "Full access to the institute, including deleting roles.",
        TENANT_CODES,
    ),
    (
        "ADMIN",
        "Administrator",
        "Full access to the institute except deleting roles.",
        tuple(code for code in TENANT_CODES if code != "role.delete"),
    ),
)
SYSTEM_ROLE_ERRCODE = "MT001"
CODE_FORMAT = r"code ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$'"

T = "nullif(current_setting('app.tenant_id', true), '')::uuid"
SYSTEM = "nullif(current_setting('app.realm', true), '') = 'system'"

TABLES = ("permissions", "roles", "role_permissions", "membership_roles")
PRIVILEGES = {
    "permissions": "SELECT",
    "roles": "SELECT, INSERT, UPDATE, DELETE",
    "role_permissions": "SELECT, INSERT, DELETE",
    "membership_roles": "SELECT, INSERT, DELETE",
}
CUSTOM_ROLE_IN_TENANT = (
    f"role_id IN (SELECT r.id FROM roles r WHERE r.tenant_id = {T} AND NOT r.is_system)"
)

# (table, policy, command, USING, WITH CHECK) — for the application role.
POLICIES: tuple[tuple[str, str, str, str | None, str | None], ...] = (
    ("roles", "roles_select", "SELECT", f"tenant_id = {T} OR {SYSTEM}", None),
    (
        "roles",
        "roles_insert",
        "INSERT",
        None,
        f"(tenant_id = {T} AND NOT is_system) OR {SYSTEM}",
    ),
    (
        "roles",
        "roles_update",
        "UPDATE",
        f"(tenant_id = {T} AND NOT is_system) OR {SYSTEM}",
        f"(tenant_id = {T} AND NOT is_system) OR {SYSTEM}",
    ),
    ("roles", "roles_delete", "DELETE", f"(tenant_id = {T} AND NOT is_system) OR {SYSTEM}", None),
    ("role_permissions", "role_permissions_select", "SELECT", f"tenant_id = {T} OR {SYSTEM}", None),
    (
        "role_permissions",
        "role_permissions_insert",
        "INSERT",
        None,
        f"(tenant_id = {T} AND {CUSTOM_ROLE_IN_TENANT}) OR {SYSTEM}",
    ),
    (
        "role_permissions",
        "role_permissions_delete",
        "DELETE",
        f"(tenant_id = {T} AND {CUSTOM_ROLE_IN_TENANT}) OR {SYSTEM}",
        None,
    ),
    ("membership_roles", "membership_roles_select", "SELECT", f"tenant_id = {T} OR {SYSTEM}", None),
    ("membership_roles", "membership_roles_insert", "INSERT", None, f"tenant_id = {T} OR {SYSTEM}"),
    ("membership_roles", "membership_roles_delete", "DELETE", f"tenant_id = {T} OR {SYSTEM}", None),
)

TRIGGER_FUNCTIONS = (
    (
        "roles_protect_system",
        f"""
        BEGIN
            IF OLD.is_system THEN
                RAISE EXCEPTION 'system roles cannot be changed or deleted'
                    USING ERRCODE = '{SYSTEM_ROLE_ERRCODE}';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            IF NEW.is_system OR NEW.template_code IS NOT NULL THEN
                RAISE EXCEPTION 'a custom role cannot become a system role'
                    USING ERRCODE = '{SYSTEM_ROLE_ERRCODE}';
            END IF;
            RETURN NEW;
        END
        """,
    ),
    (
        "role_permissions_protect_system",
        f"""
        BEGIN
            IF EXISTS (SELECT 1 FROM roles r WHERE r.id = OLD.role_id AND r.is_system) THEN
                RAISE EXCEPTION 'the permissions of a system role cannot be changed'
                    USING ERRCODE = '{SYSTEM_ROLE_ERRCODE}';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END
        """,
    ),
)
TRIGGERS = (
    ("roles", "roles_protect_system", "UPDATE OR DELETE"),
    ("role_permissions", "role_permissions_protect_system", "UPDATE OR DELETE"),
)


def _sql_list(values: Sequence[str]) -> str:
    return ", ".join("'" + value.replace("'", "''") + "'" for value in values)


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


def _uuid(name: str) -> sa.Column[Any]:
    return sa.Column(name, sa.Uuid(), nullable=False)


def _tenant_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id"],
        ["tenants.id"],
        name=op.f(f"fk_{table}_tenant_id_tenants"),
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    roles = database_roles()
    app_role, readonly_role = quote_role(roles["app"]), quote_role(roles["readonly"])

    op.create_table(
        "permissions",
        sa.Column("realm", sa.String(length=16), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=True),
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.CheckConstraint("realm IN ('platform', 'tenant')", name=op.f("ck_permissions_realm")),
        sa.CheckConstraint("scope IN ('tenant', 'campus')", name=op.f("ck_permissions_scope")),
        sa.CheckConstraint(
            "(realm = 'tenant') = (scope IS NOT NULL)", name=op.f("ck_permissions_scope_realm")
        ),
        sa.CheckConstraint(CODE_FORMAT, name=op.f("ck_permissions_code_format")),
        sa.PrimaryKeyConstraint("realm", "code", name=op.f("pk_permissions")),
    )
    op.create_table(
        "roles",
        _uuid("id"),
        _uuid("tenant_id"),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("template_code", sa.String(length=32), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        *_timestamps(version=True),
        sa.CheckConstraint("btrim(name) <> ''", name=op.f("ck_roles_name")),
        sa.CheckConstraint(
            "is_system = (template_code IS NOT NULL)", name=op.f("ck_roles_system_template")
        ),
        _tenant_fk("roles"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_roles_tenant_id_id")),
        sa.UniqueConstraint(
            "tenant_id", "template_code", name=op.f("uq_roles_tenant_id_template_code")
        ),
    )
    op.create_index(
        "uq_roles_tenant_id_lower_name",
        "roles",
        ["tenant_id", sa.text("lower(name)")],
        unique=True,
    )
    op.create_table(
        "role_permissions",
        _uuid("id"),
        _uuid("tenant_id"),
        _uuid("role_id"),
        sa.Column(
            "permission_realm",
            sa.String(length=16),
            sa.Computed("'tenant'::character varying", persisted=True),
            nullable=False,
        ),
        sa.Column("permission_code", sa.String(length=100), nullable=False),
        *_timestamps(),
        _tenant_fk("role_permissions"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "role_id"],
            ["roles.tenant_id", "roles.id"],
            name=op.f("fk_role_permissions_tenant_id_role_id_roles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["permission_realm", "permission_code"],
            ["permissions.realm", "permissions.code"],
            name="fk_role_permissions_permission",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_permissions")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_role_permissions_tenant_id_id")),
        sa.UniqueConstraint(
            "role_id", "permission_code", name=op.f("uq_role_permissions_role_id_permission_code")
        ),
    )
    op.create_table(
        "membership_roles",
        _uuid("id"),
        _uuid("tenant_id"),
        _uuid("membership_id"),
        _uuid("role_id"),
        *_timestamps(),
        _tenant_fk("membership_roles"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_membership_roles_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "role_id"],
            ["roles.tenant_id", "roles.id"],
            name=op.f("fk_membership_roles_tenant_id_role_id_roles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_membership_roles")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_membership_roles_tenant_id_id")),
        sa.UniqueConstraint(
            "membership_id", "role_id", name=op.f("uq_membership_roles_membership_id_role_id")
        ),
    )
    op.create_index(op.f("ix_membership_roles_role_id"), "membership_roles", ["role_id"])

    # --- Permission catalogue (D-B4: synchronised only here, by migrations) ------------
    op.bulk_insert(
        sa.table(
            "permissions",
            sa.column("realm", sa.String()),
            sa.column("code", sa.String()),
            sa.column("scope", sa.String()),
            sa.column("module", sa.String()),
            sa.column("description", sa.String()),
        ),
        [
            {"realm": realm, "code": code, "scope": scope, "module": module, "description": text}
            for realm, code, scope, module, text in PERMISSIONS
        ],
    )

    # --- System roles for every existing tenant (no assignments) -----------------------
    for template_code, name, description, codes in SYSTEM_ROLES:
        op.execute(
            "INSERT INTO roles "
            "(id, tenant_id, name, description, template_code, is_system, version) "
            f"SELECT uuidv7(), t.id, {_sql_list([name])}, {_sql_list([description])}, "
            f"{_sql_list([template_code])}, true, 1 FROM tenants t"
        )
        op.execute(
            "INSERT INTO role_permissions (id, tenant_id, role_id, permission_code) "
            "SELECT uuidv7(), r.tenant_id, r.id, c.code FROM roles r "
            f"CROSS JOIN unnest(ARRAY[{_sql_list(codes)}]::varchar[]) AS c(code) "
            f"WHERE r.template_code = {_sql_list([template_code])}"
        )

    # --- D-B2: system roles are immutable ----------------------------------------------
    for function, body in TRIGGER_FUNCTIONS:
        op.execute(f"CREATE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $${body}$$")
    for table, function, events in TRIGGERS:
        op.execute(
            f"CREATE TRIGGER {function} BEFORE {events} ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}()"
        )

    # --- Privileges: replace the defaults ----------------------------------------------
    for table in TABLES:
        op.execute(f"REVOKE ALL ON TABLE {table} FROM {app_role}, {readonly_role}")
        op.execute(f"GRANT {PRIVILEGES[table]} ON TABLE {table} TO {app_role}")
    op.execute(f"GRANT SELECT ON TABLE permissions TO {readonly_role}")

    # --- Row-Level Security ------------------------------------------------------------
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY permissions_read ON permissions FOR SELECT "
        f"TO {app_role}, {readonly_role} USING (true)"
    )
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
    op.execute("DROP POLICY permissions_read ON permissions")
    for table, function, _events in reversed(TRIGGERS):
        op.execute(f"DROP TRIGGER {function} ON {table}")
    for function, _body in reversed(TRIGGER_FUNCTIONS):
        op.execute(f"DROP FUNCTION {function}()")
    for table in reversed(TABLES):
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.drop_table(table)
