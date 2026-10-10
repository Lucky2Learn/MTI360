# SQL is assembled only from the frozen constants below (no input): S608 is a false positive.
# ruff: noqa: S608
"""Admissions core: applications, documents, admissions, students and numbering (Phase 02-2).

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-09

ADR-0021:

* ``tenant_sequences`` (per-tenant, per-year counters), ``stored_files``
  (object-storage metadata; the key is tied to the row's tenant and ID by a
  CHECK), ``applications`` (campus required, L6), ``application_documents``
  (replaced, never deleted), ``application_activities`` (append-only),
  ``students`` and ``admissions`` (one per application). Composite foreign
  keys ``(tenant_id, x_id) → parent(tenant_id, id)`` throughout.
* Realm-agnostic tenant Row-Level Security (the pattern of 0003/0009).
* Privileges replace the defaults: the application role gets SELECT, INSERT,
  UPDATE (never DELETE), and only SELECT, INSERT on ``stored_files`` and
  ``application_activities``. The read-only role gets **nothing** on these
  tables (personal data and documents).
* ``lead_activities.kind`` gains ``APPLICATION_STARTED`` (ADR-0021 §10).
* Permissions (D-B4): nine tenant permissions. Every ``INSTITUTE_OWNER`` /
  ``ADMIN`` clone gains all nine; ``ADMISSIONS_MANAGER`` gains all nine and
  ``COUNSELLOR`` six (ADR-0021 §11). The descriptions of the last two are
  updated with the system-role protection trigger suspended for that one
  statement, as the owner. Nobody is assigned a role.

The downgrade is a development operation that loses data: it drops the
tables (and their documents' metadata; stored objects stay in the bucket),
removes the ``APPLICATION_STARTED`` lead activities, the nine permissions and
the description changes. No SECURITY DEFINER.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migrations.helpers import database_roles, quote_role

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# --- Frozen copies at this revision (never import app code into migrations) -----------
T = "nullif(current_setting('app.tenant_id', true), '')::uuid"
SEQUENCE_NAMES = ("APPLICATION", "ADMISSION", "STUDENT")
APPLICATION_STATUSES = (
    "DRAFT",
    "SUBMITTED",
    "UNDER_REVIEW",
    "DOCUMENT_VERIFICATION",
    "ELIGIBLE",
    "CORRECTION_REQUIRED",
    "APPROVED",
    "ADMITTED",
    "REJECTED",
    "NOT_ELIGIBLE",
)
APPLICATION_REASON_REQUIRED = ("CORRECTION_REQUIRED", "NOT_ELIGIBLE", "REJECTED")
APPLICATION_ACTIVITY_KINDS = (
    "CREATED",
    "UPDATED",
    "SUBMITTED",
    "STATUS_CHANGED",
    "DOCUMENT_UPLOADED",
    "DOCUMENT_VERIFIED",
    "DOCUMENT_REJECTED",
    "ADMITTED",
)
CONTENT_TYPES = ("application/pdf", "image/jpeg", "image/png")
MAX_FILE_BYTES = 10 * 1024 * 1024
DOCUMENT_TYPES = (
    "CDC",
    "ID_PROOF",
    "INDOS",
    "MARKSHEET_10",
    "MARKSHEET_12",
    "MEDICAL_CERTIFICATE",
    "OTHER",
    "PASSPORT",
    "PHOTO",
)
DOCUMENT_STATUSES = ("REJECTED", "UNDER_REVIEW", "UPLOADED", "VERIFIED")
STUDENT_STATUSES = ("ACTIVE",)
ADMISSION_STATUSES = ("ADMITTED",)
TEXT_MAX = 2000
LEAD_ACTIVITY_KINDS_0009 = (
    "CREATED",
    "UPDATED",
    "STATUS_CHANGED",
    "ASSIGNED",
    "FOLLOW_UP_SCHEDULED",
    "FOLLOW_UP_COMPLETED",
    "FOLLOW_UP_CANCELLED",
    "NOTE",
)
LEAD_ACTIVITY_KINDS = (*LEAD_ACTIVITY_KINDS_0009, "APPLICATION_STARTED")

# (realm, code, scope, module, description) — equal to the code registry (drift test).
PERMISSIONS: tuple[tuple[str, str, str, str, str], ...] = (
    ("tenant", "application.read", "campus", "applications", "View applications and their history"),
    ("tenant", "application.create", "campus", "applications", "Start applications"),
    ("tenant", "application.update", "campus", "applications", "Edit and submit applications"),
    (
        "tenant",
        "application.review",
        "campus",
        "applications",
        "Review applications: approve, reject or request corrections",
    ),
    ("tenant", "document.read", "campus", "documents", "View and download application documents"),
    ("tenant", "document.upload", "campus", "documents", "Upload application documents"),
    ("tenant", "document.verify", "campus", "documents", "Verify or reject application documents"),
    (
        "tenant",
        "admission.approve",
        "campus",
        "students",
        "Approve admissions and create student records",
    ),
    ("tenant", "student.read", "campus", "students", "View students"),
)
CODES = tuple(code for _, code, *_ in PERMISSIONS)
COUNSELLOR_CODES = (
    "application.read",
    "application.create",
    "application.update",
    "document.read",
    "document.upload",
    "student.read",
)
EXTENDED_TEMPLATES = ("INSTITUTE_OWNER", "ADMIN", "ADMISSIONS_MANAGER")
# (template_code, description at 0010, description at 0009)
DESCRIPTIONS: tuple[tuple[str, str, str], ...] = (
    (
        "ADMISSIONS_MANAGER",
        "Runs admissions: the course catalogue, leads and their assignment, applications, "
        "document verification, review and admission approval.",
        "Manages the course catalogue and the admissions team's leads, including assignment.",
    ),
    (
        "COUNSELLOR",
        "Works enquiries and applications: leads, notes and follow-ups, application drafts "
        "and document uploads; reads the catalogue and students.",
        "Works enquiries: adds and updates leads, notes and follow-ups; reads the catalogue.",
    ),
)
PROTECTION_TRIGGERS = (
    ("roles", "roles_protect_system"),
    ("role_permissions", "role_permissions_protect_system"),
)

TABLES = (
    "tenant_sequences",
    "stored_files",
    "applications",
    "application_documents",
    "application_activities",
    "students",
    "admissions",
)
APPEND_ONLY = ("stored_files", "application_activities")


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


def _updated() -> sa.Column[Any]:
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def _version() -> sa.Column[Any]:
    return sa.Column("version", sa.Integer(), nullable=False)


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


def _index(table: str, *columns: str) -> None:
    op.create_index(op.f(f"ix_{table}_{'_'.join(columns)}"), table, list(columns))


def _contact_columns() -> list[sa.Column[Any]]:
    return [
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("mobile", sa.String(length=32), nullable=True),
        sa.Column("mobile_key", sa.String(length=16), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("email_normalized", sa.String(length=254), nullable=True),
    ]


def _contact_checks(table: str) -> list[sa.CheckConstraint]:
    return [
        _check(table, "full_name", "btrim(full_name) <> ''"),
        _check(table, "mobile_key", "(mobile IS NULL) = (mobile_key IS NULL)"),
        _check(table, "email_normalized", "(email IS NULL) = (email_normalized IS NULL)"),
    ]


def _create_tables() -> None:
    op.create_table(
        "tenant_sequences",
        _id(),
        _id("tenant_id"),
        sa.Column("name", sa.String(length=16), nullable=False),
        sa.Column("period", sa.Integer(), nullable=False),
        sa.Column("last_value", sa.BigInteger(), nullable=False),
        _created(),
        _updated(),
        *_keys("tenant_sequences"),
        sa.UniqueConstraint(
            "tenant_id", "name", "period", name=op.f("uq_tenant_sequences_tenant_id_name_period")
        ),
        _check("tenant_sequences", "name", _in("name", SEQUENCE_NAMES)),
        _check("tenant_sequences", "period", "period BETWEEN 2000 AND 9999"),
        _check("tenant_sequences", "last_value", "last_value > 0"),
    )

    op.create_table(
        "stored_files",
        _id(),
        _id("tenant_id"),
        sa.Column("object_key", sa.String(length=200), nullable=False),
        sa.Column("file_name", sa.String(length=120), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        _id("uploaded_by_membership_id"),
        _created(),
        *_keys("stored_files"),
        _composite_fk(
            "uploaded_by_membership_id", "tenant_memberships", "fk_stored_files_uploaded_by"
        ),
        _check(
            "stored_files",
            "object_key",
            "object_key = 'tenants/' || tenant_id::text || '/files/' || id::text",
        ),
        _check("stored_files", "file_name", "btrim(file_name) <> ''"),
        _check("stored_files", "content_type", _in("content_type", CONTENT_TYPES)),
        _check("stored_files", "size_bytes", f"size_bytes > 0 AND size_bytes <= {MAX_FILE_BYTES}"),
        _check("stored_files", "sha256", "sha256 ~ '^[0-9a-f]{64}$'"),
    )

    op.create_table(
        "applications",
        _id(),
        _id("tenant_id"),
        sa.Column("number", sa.String(length=32), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=True),
        _id("course_id"),
        _id("campus_id"),
        _id("owner_membership_id"),
        _id("created_by_membership_id"),
        sa.Column(
            "status", sa.String(length=24), server_default=sa.text("'DRAFT'"), nullable=False
        ),
        sa.Column("status_reason", sa.String(length=500), nullable=True),
        sa.Column(
            "status_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_membership_id", sa.Uuid(), nullable=True),
        sa.Column("declared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declared_by_membership_id", sa.Uuid(), nullable=True),
        *_contact_columns(),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=120), nullable=True),
        sa.Column("postal_code", sa.String(length=16), nullable=True),
        sa.Column("highest_qualification", sa.String(length=200), nullable=True),
        sa.Column("education_details", sa.Text(), nullable=True),
        sa.Column("indos_number", sa.String(length=16), nullable=True),
        sa.Column("cdc_number", sa.String(length=32), nullable=True),
        sa.Column("eligibility_notes", sa.Text(), nullable=True),
        _created(),
        _updated(),
        _version(),
        *_keys("applications"),
        sa.UniqueConstraint("tenant_id", "number", name=op.f("uq_applications_tenant_id_number")),
        _composite_fk("lead_id", "leads", "fk_applications_lead"),
        _composite_fk("course_id", "courses", "fk_applications_course"),
        _composite_fk("campus_id", "campuses", "fk_applications_campus"),
        _composite_fk("owner_membership_id", "tenant_memberships", "fk_applications_owner"),
        _composite_fk(
            "created_by_membership_id", "tenant_memberships", "fk_applications_created_by"
        ),
        _composite_fk(
            "reviewed_by_membership_id", "tenant_memberships", "fk_applications_reviewed_by"
        ),
        _composite_fk(
            "declared_by_membership_id", "tenant_memberships", "fk_applications_declared_by"
        ),
        *_contact_checks("applications"),
        _check("applications", "status", _in("status", APPLICATION_STATUSES)),
        _check(
            "applications",
            "status_reason",
            f"NOT ({_in('status', APPLICATION_REASON_REQUIRED)}) OR status_reason IS NOT NULL",
        ),
        _check("applications", "submitted_at", "status = 'DRAFT' OR submitted_at IS NOT NULL"),
        _check(
            "applications",
            "declaration",
            "(declared_at IS NULL) = (declared_by_membership_id IS NULL)",
        ),
        _check(
            "applications",
            "reviewed",
            "(reviewed_at IS NULL) = (reviewed_by_membership_id IS NULL)",
        ),
        _check(
            "applications", "education_details", f"char_length(education_details) <= {TEXT_MAX}"
        ),
        _check(
            "applications", "eligibility_notes", f"char_length(eligibility_notes) <= {TEXT_MAX}"
        ),
    )
    _index("applications", "tenant_id", "status", "created_at")
    _index("applications", "tenant_id", "campus_id", "status")
    _index("applications", "tenant_id", "lead_id")
    _index("applications", "tenant_id", "course_id")

    op.create_table(
        "application_documents",
        _id(),
        _id("tenant_id"),
        _id("application_id"),
        _id("stored_file_id"),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_membership_id", sa.Uuid(), nullable=True),
        _id("uploaded_by_membership_id"),
        sa.Column("replaces_document_id", sa.Uuid(), nullable=True),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=True),
        _created(),
        _updated(),
        _version(),
        *_keys("application_documents"),
        sa.UniqueConstraint(
            "tenant_id",
            "stored_file_id",
            name=op.f("uq_application_documents_tenant_id_stored_file_id"),
        ),
        _composite_fk("application_id", "applications", "fk_application_documents_application"),
        _composite_fk("stored_file_id", "stored_files", "fk_application_documents_file"),
        _composite_fk(
            "uploaded_by_membership_id",
            "tenant_memberships",
            "fk_application_documents_uploaded_by",
        ),
        _composite_fk(
            "reviewed_by_membership_id",
            "tenant_memberships",
            "fk_application_documents_reviewed_by",
        ),
        _composite_fk(
            "replaces_document_id", "application_documents", "fk_application_documents_replaces"
        ),
        _check("application_documents", "document_type", _in("document_type", DOCUMENT_TYPES)),
        _check("application_documents", "status", _in("status", DOCUMENT_STATUSES)),
        _check(
            "application_documents",
            "rejection_reason",
            "(status = 'REJECTED') = (rejection_reason IS NOT NULL)",
        ),
        _check(
            "application_documents",
            "reviewed_at",
            "(status IN ('VERIFIED', 'REJECTED')) = (reviewed_at IS NOT NULL)",
        ),
        _check(
            "application_documents",
            "reviewed_by",
            "(reviewed_at IS NULL) = (reviewed_by_membership_id IS NULL)",
        ),
        _check("application_documents", "replaces_not_self", "replaces_document_id <> id"),
    )
    _index("application_documents", "tenant_id", "application_id", "document_type")
    _index("application_documents", "tenant_id", "status", "created_at")
    op.create_index(
        "uq_application_documents_tenant_id_replaces_document_id",
        "application_documents",
        ["tenant_id", "replaces_document_id"],
        unique=True,
        postgresql_where=sa.text("replaces_document_id IS NOT NULL"),
    )

    op.create_table(
        "application_activities",
        _id(),
        _id("tenant_id"),
        _id("application_id"),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("actor_membership_id", sa.Uuid(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        _created(),
        *_keys("application_activities"),
        _composite_fk("application_id", "applications", "fk_application_activities_application"),
        _composite_fk(
            "actor_membership_id", "tenant_memberships", "fk_application_activities_actor"
        ),
        _check("application_activities", "kind", _in("kind", APPLICATION_ACTIVITY_KINDS)),
        _check("application_activities", "details_object", "jsonb_typeof(details) = 'object'"),
    )
    _index("application_activities", "tenant_id", "application_id", "created_at")

    op.create_table(
        "students",
        _id(),
        _id("tenant_id"),
        sa.Column("student_number", sa.String(length=32), nullable=False),
        _id("home_campus_id"),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'ACTIVE'"), nullable=False
        ),
        *_contact_columns(),
        sa.Column("city", sa.String(length=120), nullable=True),
        _id("created_by_membership_id"),
        _created(),
        _updated(),
        _version(),
        *_keys("students"),
        sa.UniqueConstraint(
            "tenant_id", "student_number", name=op.f("uq_students_tenant_id_student_number")
        ),
        _composite_fk("home_campus_id", "campuses", "fk_students_home_campus"),
        _composite_fk("created_by_membership_id", "tenant_memberships", "fk_students_created_by"),
        *_contact_checks("students"),
        _check("students", "status", _in("status", STUDENT_STATUSES)),
    )
    _index("students", "tenant_id", "home_campus_id", "created_at")
    for column in ("mobile_key", "email_normalized"):
        op.create_index(
            f"ix_students_tenant_id_{column}",
            "students",
            ["tenant_id", column],
            postgresql_where=sa.text(f"{column} IS NOT NULL"),
        )

    op.create_table(
        "admissions",
        _id(),
        _id("tenant_id"),
        sa.Column("admission_number", sa.String(length=32), nullable=False),
        _id("application_id"),
        _id("student_id"),
        _id("course_id"),
        _id("campus_id"),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'ADMITTED'"), nullable=False
        ),
        _id("approved_by_membership_id"),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        _created(),
        _updated(),
        _version(),
        *_keys("admissions"),
        sa.UniqueConstraint(
            "tenant_id", "admission_number", name=op.f("uq_admissions_tenant_id_admission_number")
        ),
        sa.UniqueConstraint(
            "tenant_id", "application_id", name=op.f("uq_admissions_tenant_id_application_id")
        ),
        _composite_fk("application_id", "applications", "fk_admissions_application"),
        _composite_fk("student_id", "students", "fk_admissions_student"),
        _composite_fk("course_id", "courses", "fk_admissions_course"),
        _composite_fk("campus_id", "campuses", "fk_admissions_campus"),
        _composite_fk(
            "approved_by_membership_id", "tenant_memberships", "fk_admissions_approved_by"
        ),
        _check("admissions", "status", _in("status", ADMISSION_STATUSES)),
    )
    _index("admissions", "tenant_id", "student_id")
    _index("admissions", "tenant_id", "campus_id", "created_at")


def _replace_lead_activity_kinds(kinds: Sequence[str]) -> None:
    name = op.f("ck_lead_activities_kind")
    op.drop_constraint(name, "lead_activities", type_="check")
    op.create_check_constraint(name, "lead_activities", _in("kind", kinds))


def _set_descriptions(column: int) -> None:
    op.execute("ALTER TABLE roles DISABLE TRIGGER roles_protect_system")
    for row in DESCRIPTIONS:
        op.execute(
            f"UPDATE roles SET description = {_sql_list([row[column]])} "
            f"WHERE is_system AND template_code = {_sql_list([row[0]])}"
        )
    op.execute("ALTER TABLE roles ENABLE TRIGGER roles_protect_system")


def _grant(codes: Sequence[str], templates: Sequence[str]) -> None:
    op.execute(
        "INSERT INTO role_permissions (id, tenant_id, role_id, permission_code) "
        "SELECT uuidv7(), r.tenant_id, r.id, c.code FROM roles r "
        f"CROSS JOIN unnest(ARRAY[{_sql_list(codes)}]::varchar[]) AS c(code) "
        f"WHERE r.is_system AND r.template_code IN ({_sql_list(templates)})"
    )


def upgrade() -> None:
    roles = database_roles()
    app_role, readonly_role = quote_role(roles["app"]), quote_role(roles["readonly"])

    _create_tables()
    _replace_lead_activity_kinds(LEAD_ACTIVITY_KINDS)

    # --- Privileges: replace the defaults (nothing for the read-only role) ------------------
    for table in TABLES:
        op.execute(f"REVOKE ALL ON TABLE {table} FROM {app_role}, {readonly_role}")
        privileges = "SELECT, INSERT" if table in APPEND_ONLY else "SELECT, INSERT, UPDATE"
        op.execute(f"GRANT {privileges} ON TABLE {table} TO {app_role}")

    # --- Row-Level Security: tenant-owned, realm-agnostic ---------------------------------
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        if table in APPEND_ONLY:
            op.execute(
                f"CREATE POLICY {table}_tenant_read ON {table} FOR SELECT TO {app_role} "
                f"USING (tenant_id = {T})"
            )
            op.execute(
                f"CREATE POLICY {table}_tenant_insert ON {table} FOR INSERT TO {app_role} "
                f"WITH CHECK (tenant_id = {T})"
            )
        else:
            op.execute(
                f"CREATE POLICY {table}_tenant_isolation ON {table} FOR ALL TO {app_role} "
                f"USING (tenant_id = {T}) WITH CHECK (tenant_id = {T})"
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
    _grant(CODES, EXTENDED_TEMPLATES)
    _grant(COUNSELLOR_CODES, ("COUNSELLOR",))
    _set_descriptions(1)


def downgrade() -> None:
    _set_descriptions(2)
    for table, trigger in PROTECTION_TRIGGERS:
        op.execute(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}")
    op.execute(f"DELETE FROM role_permissions WHERE permission_code IN ({_sql_list(CODES)})")
    for table, trigger in PROTECTION_TRIGGERS:
        op.execute(f"ALTER TABLE {table} ENABLE TRIGGER {trigger}")
    op.execute(f"DELETE FROM permissions WHERE realm = 'tenant' AND code IN ({_sql_list(CODES)})")
    op.execute("DELETE FROM lead_activities WHERE kind = 'APPLICATION_STARTED'")
    _replace_lead_activity_kinds(LEAD_ACTIVITY_KINDS_0009)
    for table in reversed(TABLES):
        op.drop_table(table)  # drops its indexes and policies
