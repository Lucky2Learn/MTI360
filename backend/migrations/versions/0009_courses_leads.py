# SQL is assembled only from the frozen constants below (no input): S608 is a false positive.
# ruff: noqa: S608
"""Courses and leads: catalogue, leads, follow-ups, activity, permissions and roles (Phase 02-1).

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-08

ADR-0020 (blueprint docs/architecture/PHASE-02-1-COURSES-LEADS-READINESS.md §15-§19):

* ``courses`` — the institute-wide catalogue (**no campus column**);
  ``leads`` (campus nullable: NULL is the institute pool, L6);
  ``lead_follow_ups``; ``lead_activities`` (append-only timeline).
  Composite foreign keys ``(tenant_id, x_id) → parent(tenant_id, id)`` so no
  row can point at another tenant's course, campus, membership or lead.
* Realm-agnostic tenant Row-Level Security (the ``campuses`` pattern of
  0003): ``tenant_id = app.tenant_id`` for reads and writes; without a tenant
  context nothing matches. Campus scope is application-enforced (D-B1).
* Privileges replace the defaults: the application role gets SELECT, INSERT,
  UPDATE (never DELETE) and only SELECT, INSERT on ``lead_activities``; the
  read-only role may read ``courses`` and nothing of the lead tables
  (personal data; ADR-0020 Y8).
* Permissions (D-B4): six tenant permissions. System roles (D-B2):
  ``ADMISSIONS_MANAGER`` and ``COUNSELLOR`` are cloned for every existing
  tenant, and every ``INSTITUTE_OWNER`` / ``ADMIN`` clone gains the six
  permissions (their templates are "everything" / "everything but
  role.delete"). Nobody is assigned the new roles.
* A tenant that already has a custom role named like a new system role makes
  the upgrade fail with a clear message instead of renaming tenant data.

The downgrade is a development operation that loses data: it removes the new
roles' assignments and the six permissions from every role (the system-role
protection triggers are suspended for those statements only, as the owner),
then drops the tables. No SECURITY DEFINER.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migrations.helpers import database_roles, quote_role

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# --- Frozen copies at this revision (never import app code into migrations) -----------
T = "nullif(current_setting('app.tenant_id', true), '')::uuid"
CODE_PATTERN = "^[A-Z0-9][A-Z0-9-]*$"
COURSE_CATEGORIES = ("PRE_SEA", "POST_SEA", "OTHER")
COURSE_STATUSES = ("DRAFT", "ACTIVE", "ARCHIVED")
DURATION_UNITS = ("DAYS", "WEEKS", "MONTHS", "YEARS")
LEAD_SOURCES = (
    "WEBSITE",
    "WHATSAPP",
    "PHONE",
    "WALK_IN",
    "INSTAGRAM",
    "FACEBOOK",
    "YOUTUBE",
    "GOOGLE",
    "REFERRAL",
    "EDUCATION_PORTAL",
    "OTHER",
)
LEAD_STATUSES = (
    "NEW",
    "CONTACTED",
    "QUALIFIED",
    "COUNSELLING",
    "INTERESTED",
    "APPLICATION",
    "ADMITTED",
    "NOT_ELIGIBLE",
    "LOST",
    "DEFERRED",
    "DUPLICATE",
)
REASON_REQUIRED = ("DEFERRED", "LOST", "NOT_ELIGIBLE")
FOLLOW_UP_KINDS = ("CALL", "WHATSAPP", "EMAIL", "MEETING", "VISIT", "OTHER")
FOLLOW_UP_STATUSES = ("OPEN", "DONE", "CANCELLED")
ACTIVITY_KINDS = (
    "CREATED",
    "UPDATED",
    "STATUS_CHANGED",
    "ASSIGNED",
    "FOLLOW_UP_SCHEDULED",
    "FOLLOW_UP_COMPLETED",
    "FOLLOW_UP_CANCELLED",
    "NOTE",
)
TEXT_MAX = 2000
NOTE_MAX = 4000

# (realm, code, scope, module, description) — equal to the code registry (drift test).
PERMISSIONS: tuple[tuple[str, str, str, str, str], ...] = (
    ("tenant", "course.read", "campus", "courses", "View the course catalogue"),
    (
        "tenant",
        "course.manage",
        "tenant",
        "courses",
        "Create, edit, activate and archive courses",
    ),
    ("tenant", "lead.read", "campus", "leads", "View leads and their history"),
    ("tenant", "lead.create", "campus", "leads", "Add leads"),
    (
        "tenant",
        "lead.update",
        "campus",
        "leads",
        "Edit leads, change their status, add notes and follow-ups",
    ),
    ("tenant", "lead.assign", "campus", "leads", "Assign leads to staff and campuses"),
)
CODES = tuple(code for _, code, *_ in PERMISSIONS)
# (template_code, name, description, permission codes)
NEW_SYSTEM_ROLES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "ADMISSIONS_MANAGER",
        "Admissions manager",
        "Manages the course catalogue and the admissions team's leads, including assignment.",
        CODES,
    ),
    (
        "COUNSELLOR",
        "Counsellor",
        "Works enquiries: adds and updates leads, notes and follow-ups; reads the catalogue.",
        ("course.read", "lead.read", "lead.create", "lead.update"),
    ),
)
EXTENDED_TEMPLATES = ("INSTITUTE_OWNER", "ADMIN")
NEW_TEMPLATES = tuple(template for template, *_ in NEW_SYSTEM_ROLES)
PROTECTION_TRIGGERS = (
    ("roles", "roles_protect_system"),
    ("role_permissions", "role_permissions_protect_system"),
)

TABLES = ("courses", "leads", "lead_follow_ups", "lead_activities")
PRIVILEGES = {
    "courses": "SELECT, INSERT, UPDATE",
    "leads": "SELECT, INSERT, UPDATE",
    "lead_follow_ups": "SELECT, INSERT, UPDATE",
    "lead_activities": "SELECT, INSERT",
}


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _sql_list(values: Sequence[str]) -> str:
    return ", ".join("'" + value.replace("'", "''") + "'" for value in values)


def _id(name: str = "id") -> sa.Column[Any]:
    return sa.Column(name, sa.Uuid(), nullable=False)


def _created() -> sa.Column[Any]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def _timestamps_and_version() -> list[sa.Column[Any]]:
    return [
        _created(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
    ]


def _tenant_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id"],
        ["tenants.id"],
        name=op.f(f"fk_{table}_tenant_id_tenants"),
        ondelete="RESTRICT",
    )


def _composite_fk(column: str, parent: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id", column],
        [f"{parent}.tenant_id", f"{parent}.id"],
        name=name,
        ondelete="RESTRICT",
    )


def _check(table: str, name: str, condition: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(condition, name=op.f(f"ck_{table}_{name}"))


def _keys(table: str) -> list[Any]:
    return [
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f(f"uq_{table}_tenant_id_id")),
        _tenant_fk(table),
    ]


def _refuse_role_name_clashes() -> None:
    names = [name.lower() for _, name, *_ in NEW_SYSTEM_ROLES]
    clashes = op.get_bind().execute(
        sa.text(
            "SELECT count(DISTINCT tenant_id) FROM roles "
            "WHERE lower(name) = ANY(:names) "
            "AND (template_code IS NULL OR NOT template_code = ANY(:templates))"
        ),
        {"names": names, "templates": list(NEW_TEMPLATES)},
    )
    count = clashes.scalar_one()
    if count:
        raise RuntimeError(
            f"{count} tenant(s) already have a custom role named like a new system role "
            f"({', '.join(name for _, name, *_ in NEW_SYSTEM_ROLES)}); rename it, then upgrade."
        )


def upgrade() -> None:
    roles = database_roles()
    app_role, readonly_role = quote_role(roles["app"]), quote_role(roles["readonly"])
    _refuse_role_name_clashes()

    # --- Tables -------------------------------------------------------------------------
    op.create_table(
        "courses",
        _id(),
        _id("tenant_id"),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'DRAFT'"), nullable=False
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("eligibility_summary", sa.Text(), nullable=True),
        sa.Column("duration_value", sa.Integer(), nullable=True),
        sa.Column("duration_unit", sa.String(length=8), nullable=True),
        *_timestamps_and_version(),
        *_keys("courses"),
        sa.UniqueConstraint("tenant_id", "code", name=op.f("uq_courses_tenant_id_code")),
        _check("courses", "code_format", f"code ~ '{CODE_PATTERN}'"),
        _check("courses", "category", _in("category", COURSE_CATEGORIES)),
        _check("courses", "status", _in("status", COURSE_STATUSES)),
        _check("courses", "duration_unit", _in("duration_unit", DURATION_UNITS)),
        _check("courses", "duration_value", "duration_value > 0 AND duration_value <= 1000"),
        _check("courses", "duration_pair", "(duration_value IS NULL) = (duration_unit IS NULL)"),
        _check("courses", "description", f"char_length(description) <= {TEXT_MAX}"),
        _check("courses", "eligibility_summary", f"char_length(eligibility_summary) <= {TEXT_MAX}"),
    )
    op.create_index(
        op.f("ix_courses_tenant_id_status_name"), "courses", ["tenant_id", "status", "name"]
    )

    op.create_table(
        "leads",
        _id(),
        _id("tenant_id"),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("mobile", sa.String(length=32), nullable=True),
        sa.Column("mobile_key", sa.String(length=16), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("email_normalized", sa.String(length=254), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("highest_qualification", sa.String(length=200), nullable=True),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("interested_course_id", sa.Uuid(), nullable=True),
        sa.Column("campus_id", sa.Uuid(), nullable=True),
        sa.Column("owner_membership_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'NEW'"), nullable=False),
        sa.Column("status_reason", sa.String(length=500), nullable=True),
        sa.Column(
            "status_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("duplicate_of_lead_id", sa.Uuid(), nullable=True),
        _id("created_by_membership_id"),
        *_timestamps_and_version(),
        *_keys("leads"),
        _composite_fk("interested_course_id", "courses", "fk_leads_course"),
        _composite_fk("campus_id", "campuses", "fk_leads_campus"),
        _composite_fk("owner_membership_id", "tenant_memberships", "fk_leads_owner"),
        _composite_fk("created_by_membership_id", "tenant_memberships", "fk_leads_created_by"),
        _composite_fk("duplicate_of_lead_id", "leads", "fk_leads_duplicate_of"),
        _check("leads", "full_name", "btrim(full_name) <> ''"),
        _check("leads", "contact", "mobile IS NOT NULL OR email IS NOT NULL"),
        _check("leads", "mobile_key", "(mobile IS NULL) = (mobile_key IS NULL)"),
        _check("leads", "email_normalized", "(email IS NULL) = (email_normalized IS NULL)"),
        _check("leads", "source", _in("source", LEAD_SOURCES)),
        _check("leads", "status", _in("status", LEAD_STATUSES)),
        _check(
            "leads",
            "status_reason",
            f"NOT ({_in('status', REASON_REQUIRED)}) OR status_reason IS NOT NULL",
        ),
        _check(
            "leads", "duplicate_of", "(status = 'DUPLICATE') = (duplicate_of_lead_id IS NOT NULL)"
        ),
        _check("leads", "duplicate_not_self", "duplicate_of_lead_id <> id"),
    )
    columns: tuple[str, ...]
    for columns in (
        ("tenant_id", "status", "created_at"),
        ("tenant_id", "owner_membership_id", "status"),
        ("tenant_id", "campus_id", "status"),
        ("tenant_id", "interested_course_id"),
    ):
        op.create_index(op.f(f"ix_leads_{'_'.join(columns)}"), "leads", list(columns))
    for column in ("mobile_key", "email_normalized"):
        op.create_index(
            f"ix_leads_tenant_id_{column}",
            "leads",
            ["tenant_id", column],
            postgresql_where=sa.text(f"{column} IS NOT NULL"),
        )

    op.create_table(
        "lead_follow_ups",
        _id(),
        _id("tenant_id"),
        _id("lead_id"),
        _id("assignee_membership_id"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("note", sa.String(length=1000), nullable=True),
        sa.Column("outcome", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'OPEN'"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_membership_id", sa.Uuid(), nullable=True),
        _id("created_by_membership_id"),
        *_timestamps_and_version(),
        *_keys("lead_follow_ups"),
        _composite_fk("lead_id", "leads", "fk_lead_follow_ups_lead"),
        _composite_fk(
            "assignee_membership_id", "tenant_memberships", "fk_lead_follow_ups_assignee"
        ),
        _composite_fk(
            "completed_by_membership_id", "tenant_memberships", "fk_lead_follow_ups_completed_by"
        ),
        _composite_fk(
            "created_by_membership_id", "tenant_memberships", "fk_lead_follow_ups_created_by"
        ),
        _check("lead_follow_ups", "kind", _in("kind", FOLLOW_UP_KINDS)),
        _check("lead_follow_ups", "status", _in("status", FOLLOW_UP_STATUSES)),
        _check(
            "lead_follow_ups", "completed_at", "(status <> 'OPEN') = (completed_at IS NOT NULL)"
        ),
        _check(
            "lead_follow_ups",
            "completed_by",
            "(status <> 'OPEN') = (completed_by_membership_id IS NOT NULL)",
        ),
        _check("lead_follow_ups", "outcome", "outcome IS NULL OR status = 'DONE'"),
    )
    for columns in (
        ("tenant_id", "lead_id", "status", "due_at"),
        ("tenant_id", "assignee_membership_id", "status", "due_at"),
    ):
        op.create_index(
            op.f(f"ix_lead_follow_ups_{'_'.join(columns)}"), "lead_follow_ups", list(columns)
        )

    op.create_table(
        "lead_activities",
        _id(),
        _id("tenant_id"),
        _id("lead_id"),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("actor_membership_id", sa.Uuid(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=True),
        _created(),
        *_keys("lead_activities"),
        _composite_fk("lead_id", "leads", "fk_lead_activities_lead"),
        _composite_fk("actor_membership_id", "tenant_memberships", "fk_lead_activities_actor"),
        _check("lead_activities", "kind", _in("kind", ACTIVITY_KINDS)),
        _check("lead_activities", "body_length", f"char_length(body) <= {NOTE_MAX}"),
        _check("lead_activities", "body_note_only", "(kind = 'NOTE') = (body IS NOT NULL)"),
        _check("lead_activities", "details_object", "jsonb_typeof(details) = 'object'"),
    )
    op.create_index(
        op.f("ix_lead_activities_tenant_id_lead_id_created_at"),
        "lead_activities",
        ["tenant_id", "lead_id", "created_at"],
    )

    # --- Privileges: replace the defaults -------------------------------------------------
    for table in TABLES:
        op.execute(f"REVOKE ALL ON TABLE {table} FROM {app_role}, {readonly_role}")
        op.execute(f"GRANT {PRIVILEGES[table]} ON TABLE {table} TO {app_role}")
    op.execute(f"GRANT SELECT ON TABLE courses TO {readonly_role}")

    # --- Row-Level Security: tenant-owned, realm-agnostic ---------------------------------
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    for table in ("courses", "leads", "lead_follow_ups"):
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} FOR ALL TO {app_role} "
            f"USING (tenant_id = {T}) WITH CHECK (tenant_id = {T})"
        )
    op.execute(
        f"CREATE POLICY lead_activities_tenant_read ON lead_activities FOR SELECT TO {app_role} "
        f"USING (tenant_id = {T})"
    )
    op.execute(
        f"CREATE POLICY lead_activities_tenant_insert ON lead_activities FOR INSERT "
        f"TO {app_role} WITH CHECK (tenant_id = {T})"
    )
    op.execute(
        f"CREATE POLICY courses_readonly_tenant_read ON courses FOR SELECT TO {readonly_role} "
        f"USING (tenant_id = {T})"
    )

    # --- Permission catalogue (D-B4) and system roles (D-B2) ------------------------------
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
    for template_code, name, description, codes in NEW_SYSTEM_ROLES:
        op.execute(
            "INSERT INTO roles "
            "(id, tenant_id, name, description, template_code, is_system, version) "
            f"SELECT uuidv7(), t.id, {_sql_list([name])}, {_sql_list([description])}, "
            f"{_sql_list([template_code])}, true, 1 FROM tenants t"
        )
        _grant(codes, (template_code,))
    _grant(CODES, EXTENDED_TEMPLATES)


def _grant(codes: Sequence[str], templates: Sequence[str]) -> None:
    op.execute(
        "INSERT INTO role_permissions (id, tenant_id, role_id, permission_code) "
        "SELECT uuidv7(), r.tenant_id, r.id, c.code FROM roles r "
        f"CROSS JOIN unnest(ARRAY[{_sql_list(codes)}]::varchar[]) AS c(code) "
        f"WHERE r.is_system AND r.template_code IN ({_sql_list(templates)})"
    )


def downgrade() -> None:
    new_roles = f"SELECT id FROM roles WHERE template_code IN ({_sql_list(NEW_TEMPLATES)})"
    op.execute(f"DELETE FROM membership_roles WHERE role_id IN ({new_roles})")
    for table, trigger in PROTECTION_TRIGGERS:
        op.execute(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}")
    op.execute(f"DELETE FROM role_permissions WHERE permission_code IN ({_sql_list(CODES)})")
    op.execute(f"DELETE FROM roles WHERE template_code IN ({_sql_list(NEW_TEMPLATES)})")
    for table, trigger in PROTECTION_TRIGGERS:
        op.execute(f"ALTER TABLE {table} ENABLE TRIGGER {trigger}")
    op.execute(f"DELETE FROM permissions WHERE realm = 'tenant' AND code IN ({_sql_list(CODES)})")
    for table in reversed(TABLES):
        op.drop_table(table)  # drops its indexes and policies
