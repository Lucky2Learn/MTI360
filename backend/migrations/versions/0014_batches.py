# SQL is assembled only from the frozen constants below (no input): S608 is a false positive.
# ruff: noqa: S608
"""Batches: batches, student allocations and their history (Phase 02-6).

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-20

* ``batches`` — one intake of one course at one campus; code unique per
  tenant; capacity 1-500; ``end_date >= start_date``; statuses ``OPEN``,
  ``CLOSED``, ``CANCELLED`` (only when empty). ``allocated_count`` is kept by
  the trigger below and checked ``<= capacity``.
* ``batch_allocations`` — the admission ↔ batch history. Composite keys bind
  ``(admission, student, campus, course)`` to one admission and ``(batch,
  course, campus)`` to one batch, so an allocation can never cross courses,
  campuses or tenants. One ``ACTIVE`` allocation per admission (partial
  unique index). The payment basis (``PAID``, ``OVERRIDE`` with reason,
  invoice state and outstanding amount, or ``TRANSFER``) is recorded.
* ``batch_activities`` — append-only history.
* Trigger ``batch_allocations_count`` (plain SECURITY INVOKER): inserting an
  ``ACTIVE`` allocation increments the batch's count **only while the batch is
  OPEN** (SQLSTATE ``MT014`` otherwise); ending one decrements it; an
  allocation's identity never changes and an ``ENDED`` row is immutable
  (``MT015``). The batch row update serialises concurrent allocations, and the
  capacity CHECK rejects the one that would over-fill the batch.
* ``admissions.status`` accepts ``ENROLLED``. Existing admissions are not
  changed (no backfill).
* Realm-agnostic tenant Row-Level Security. The application role gets SELECT,
  INSERT, UPDATE on ``batches`` and ``batch_allocations`` (never DELETE) and
  SELECT, INSERT on ``batch_activities``. The read-only role reads
  ``batches`` only (no personal data).
* Permissions: ``batch.read``, ``batch.manage``, ``batch.allocate`` (campus).
  ``INSTITUTE_OWNER`` / ``ADMIN`` / ``ADMISSIONS_MANAGER`` gain all three;
  ``COUNSELLOR``, ``FINANCE_MANAGER`` and ``FINANCE_OFFICER`` gain
  ``batch.read``. Nobody is assigned a role.

The downgrade is a development operation that loses data: it returns
``ENROLLED`` admissions to ``ADMITTED``, drops the tables, the trigger
function and the permissions. No SECURITY DEFINER.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migrations.helpers import database_roles, quote_role

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# --- Frozen copies at this revision (never import app code into migrations) -----------
T = "nullif(current_setting('app.tenant_id', true), '')::uuid"
CODE_PATTERN = "^[A-Z0-9][A-Z0-9-]*$"
CODE_MAX = 32
NAME_MAX = 200
INTAKE_MAX = 100
REASON_MAX = 500
CAPACITY_MIN = 1
CAPACITY_MAX = 500
BATCH_STATUSES = ("OPEN", "CLOSED", "CANCELLED")
ALLOCATION_STATUSES = ("ACTIVE", "ENDED")
END_REASONS = ("TRANSFERRED", "WITHDRAWN")
PAYMENT_BASES = ("PAID", "OVERRIDE", "TRANSFER")
INVOICE_STATES = ("PAID", "PARTIALLY_PAID", "ISSUED", "NO_INVOICE")
ACTIVITY_KINDS = (
    "CREATED",
    "UPDATED",
    "STATUS_CHANGED",
    "ALLOCATED",
    "TRANSFERRED_OUT",
    "TRANSFERRED_IN",
    "WITHDRAWN",
)
ADMISSION_STATUSES_0013 = ("ADMITTED",)
ADMISSION_STATUSES = ("ADMITTED", "ENROLLED")

# (realm, code, scope, module, description) — equal to the code registry (drift test).
PERMISSIONS: tuple[tuple[str, str, str, str, str], ...] = (
    ("tenant", "batch.read", "campus", "batches", "View batches and their allocations"),
    (
        "tenant",
        "batch.manage",
        "campus",
        "batches",
        "Create and edit batches; open, close and cancel them",
    ),
    (
        "tenant",
        "batch.allocate",
        "campus",
        "batches",
        "Allocate admitted students to batches, transfer and withdraw them",
    ),
)
CODES = tuple(code for _, code, *_ in PERMISSIONS)
EXTENDED: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (CODES, ("INSTITUTE_OWNER", "ADMIN", "ADMISSIONS_MANAGER")),
    (("batch.read",), ("COUNSELLOR", "FINANCE_MANAGER", "FINANCE_OFFICER")),
)
PROTECTION_TRIGGERS = (
    ("roles", "roles_protect_system"),
    ("role_permissions", "role_permissions_protect_system"),
)

TABLES = ("batches", "batch_allocations", "batch_activities")
APPEND_ONLY = ("batch_activities",)
COUNT_FUNCTION = "batch_allocations_count"
NOT_OPEN_ERRCODE = "MT014"
IMMUTABLE_ERRCODE = "MT015"
COUNT_BODY = f"""
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.status = 'ACTIVE' THEN
                    UPDATE batches SET allocated_count = allocated_count + 1
                     WHERE tenant_id = NEW.tenant_id AND id = NEW.batch_id
                       AND status = 'OPEN';
                    IF NOT FOUND THEN
                        RAISE EXCEPTION 'students are allocated only to an open batch'
                            USING ERRCODE = '{NOT_OPEN_ERRCODE}';
                    END IF;
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.status = 'ENDED'
               OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
               OR NEW.batch_id IS DISTINCT FROM OLD.batch_id
               OR NEW.admission_id IS DISTINCT FROM OLD.admission_id
               OR NEW.student_id IS DISTINCT FROM OLD.student_id
               OR NEW.payment_basis IS DISTINCT FROM OLD.payment_basis
               OR NEW.allocated_at IS DISTINCT FROM OLD.allocated_at THEN
                RAISE EXCEPTION 'an allocation''s history cannot be changed'
                    USING ERRCODE = '{IMMUTABLE_ERRCODE}';
            END IF;
            IF OLD.status = 'ACTIVE' AND NEW.status = 'ENDED' THEN
                UPDATE batches SET allocated_count = allocated_count - 1
                 WHERE tenant_id = OLD.tenant_id AND id = OLD.batch_id;
            END IF;
            RETURN NEW;
        END
"""


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _sql_list(values: Sequence[str]) -> str:
    return ", ".join("'" + value.replace("'", "''") + "'" for value in values)


def _id(name: str = "id", *, nullable: bool = False) -> sa.Column[Any]:
    return sa.Column(name, sa.Uuid(), nullable=nullable)


def _ts(name: str, *, nullable: bool = False, default: bool = True) -> sa.Column[Any]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("now()") if default else None,
        nullable=nullable,
    )


def _version() -> sa.Column[Any]:
    return sa.Column("version", sa.Integer(), nullable=False)


def _keys(table: str) -> list[Any]:
    return [
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f(f"uq_{table}_tenant_id_id")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f(f"fk_{table}_tenant_id_tenants"),
            ondelete="RESTRICT",
        ),
    ]


def _composite_fk(column: str, parent: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id", column],
        [f"{parent}.tenant_id", f"{parent}.id"],
        name=name,
        ondelete="RESTRICT",
    )


def _check(table: str, name: str, condition: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(condition, name=op.f(f"ck_{table}_{name}"))


def _index(table: str, *columns: str) -> None:
    op.create_index(op.f(f"ix_{table}_{'_'.join(columns)}"), table, list(columns))


def _create_tables() -> None:
    op.create_table(
        "batches",
        _id(),
        _id("tenant_id"),
        _id("course_id"),
        _id("campus_id"),
        sa.Column("code", sa.String(length=CODE_MAX), nullable=False),
        sa.Column("name", sa.String(length=NAME_MAX), nullable=False),
        sa.Column("intake_label", sa.String(length=INTAKE_MAX), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("allocated_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("status_reason", sa.String(length=REASON_MAX), nullable=True),
        _id("created_by_membership_id"),
        _ts("created_at"),
        _ts("updated_at"),
        _version(),
        *_keys("batches"),
        sa.UniqueConstraint("tenant_id", "code", name=op.f("uq_batches_tenant_id_code")),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            "course_id",
            "campus_id",
            name=op.f("uq_batches_tenant_id_id_course_id_campus_id"),
        ),
        _composite_fk("course_id", "courses", "fk_batches_course"),
        _composite_fk("campus_id", "campuses", "fk_batches_campus"),
        _composite_fk("created_by_membership_id", "tenant_memberships", "fk_batches_created_by"),
        _check("batches", "code_format", f"code ~ '{CODE_PATTERN}'"),
        _check("batches", "name", "btrim(name) <> ''"),
        _check("batches", "intake_label", "intake_label IS NULL OR btrim(intake_label) <> ''"),
        _check("batches", "capacity", f"capacity BETWEEN {CAPACITY_MIN} AND {CAPACITY_MAX}"),
        _check(
            "batches", "allocated_count", "allocated_count >= 0 AND allocated_count <= capacity"
        ),
        _check("batches", "dates", "end_date >= start_date"),
        _check("batches", "status", _in("status", BATCH_STATUSES)),
        _check("batches", "cancelled_empty", "status <> 'CANCELLED' OR allocated_count = 0"),
    )
    _index("batches", "tenant_id", "campus_id", "status", "start_date")
    _index("batches", "tenant_id", "course_id", "status")

    op.create_table(
        "batch_allocations",
        _id(),
        _id("tenant_id"),
        _id("batch_id"),
        _id("course_id"),
        _id("campus_id"),
        _id("admission_id"),
        _id("student_id"),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("payment_basis", sa.String(length=16), nullable=False),
        sa.Column("override_reason", sa.String(length=REASON_MAX), nullable=True),
        sa.Column("override_invoice_state", sa.String(length=16), nullable=True),
        sa.Column("override_outstanding_minor", sa.BigInteger(), nullable=True),
        _id("transferred_from_id", nullable=True),
        _ts("allocated_at"),
        _id("allocated_by_membership_id"),
        sa.Column("end_reason", sa.String(length=16), nullable=True),
        sa.Column("end_note", sa.String(length=REASON_MAX), nullable=True),
        _ts("ended_at", nullable=True, default=False),
        _id("ended_by_membership_id", nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        _version(),
        *_keys("batch_allocations"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "batch_id", "course_id", "campus_id"],
            ["batches.tenant_id", "batches.id", "batches.course_id", "batches.campus_id"],
            name="fk_batch_allocations_batch",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "admission_id", "student_id", "campus_id", "course_id"],
            [
                "admissions.tenant_id",
                "admissions.id",
                "admissions.student_id",
                "admissions.campus_id",
                "admissions.course_id",
            ],
            name="fk_batch_allocations_admission",
            ondelete="RESTRICT",
        ),
        _composite_fk("transferred_from_id", "batch_allocations", "fk_batch_allocations_from"),
        _composite_fk(
            "allocated_by_membership_id",
            "tenant_memberships",
            "fk_batch_allocations_allocated_by",
        ),
        _composite_fk(
            "ended_by_membership_id", "tenant_memberships", "fk_batch_allocations_ended_by"
        ),
        _check("batch_allocations", "status", _in("status", ALLOCATION_STATUSES)),
        _check(
            "batch_allocations",
            "end_reason",
            f"end_reason IS NULL OR {_in('end_reason', END_REASONS)}",
        ),
        _check(
            "batch_allocations",
            "ended",
            "(status = 'ENDED') = (end_reason IS NOT NULL) "
            "AND (status = 'ENDED') = (ended_at IS NOT NULL) "
            "AND (status = 'ENDED') = (ended_by_membership_id IS NOT NULL)",
        ),
        _check(
            "batch_allocations",
            "end_note",
            "(end_reason IS NULL) = (end_note IS NULL) "
            "AND (end_note IS NULL OR btrim(end_note) <> '')",
        ),
        _check("batch_allocations", "payment_basis", _in("payment_basis", PAYMENT_BASES)),
        _check(
            "batch_allocations",
            "transfer_basis",
            "(payment_basis = 'TRANSFER') = (transferred_from_id IS NOT NULL)",
        ),
        _check(
            "batch_allocations",
            "override",
            "(payment_basis = 'OVERRIDE') = (override_reason IS NOT NULL) "
            "AND (payment_basis = 'OVERRIDE') = (override_invoice_state IS NOT NULL) "
            "AND (override_reason IS NULL OR btrim(override_reason) <> '')",
        ),
        _check(
            "batch_allocations",
            "override_invoice_state",
            "override_invoice_state IS NULL OR "
            f"({_in('override_invoice_state', INVOICE_STATES)} "
            "AND override_invoice_state <> 'PAID')",
        ),
        _check(
            "batch_allocations",
            "override_outstanding",
            "override_outstanding_minor IS NULL OR "
            "(payment_basis = 'OVERRIDE' AND override_outstanding_minor > 0)",
        ),
    )
    _index("batch_allocations", "tenant_id", "batch_id", "status")
    _index("batch_allocations", "tenant_id", "student_id")
    _index("batch_allocations", "tenant_id", "admission_id")
    op.create_index(
        "uq_batch_allocations_tenant_id_admission_id_active",
        "batch_allocations",
        ["tenant_id", "admission_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    op.create_table(
        "batch_activities",
        _id(),
        _id("tenant_id"),
        _id("batch_id"),
        _id("allocation_id", nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        _id("actor_membership_id", nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        _ts("created_at"),
        *_keys("batch_activities"),
        _composite_fk("batch_id", "batches", "fk_batch_activities_batch"),
        _composite_fk("allocation_id", "batch_allocations", "fk_batch_activities_allocation"),
        _composite_fk("actor_membership_id", "tenant_memberships", "fk_batch_activities_actor"),
        _check("batch_activities", "kind", _in("kind", ACTIVITY_KINDS)),
        _check("batch_activities", "details_object", "jsonb_typeof(details) = 'object'"),
    )
    _index("batch_activities", "tenant_id", "batch_id", "created_at")
    _index("batch_activities", "tenant_id", "allocation_id")


def _replace_admission_statuses(statuses: Sequence[str]) -> None:
    name = op.f("ck_admissions_status")
    op.drop_constraint(name, "admissions", type_="check")
    op.create_check_constraint(name, "admissions", _in("status", statuses))


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

    _replace_admission_statuses(ADMISSION_STATUSES)
    _create_tables()

    # --- Seat count, open-batch rule and immutable history (SECURITY INVOKER) ---------------
    op.execute(
        f"CREATE FUNCTION {COUNT_FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $${COUNT_BODY}$$"
    )
    op.execute(
        f"CREATE TRIGGER {COUNT_FUNCTION} AFTER INSERT OR UPDATE ON batch_allocations "
        f"FOR EACH ROW EXECUTE FUNCTION {COUNT_FUNCTION}()"
    )

    # --- Privileges: replace the defaults --------------------------------------------------
    for table in TABLES:
        op.execute(f"REVOKE ALL ON TABLE {table} FROM {app_role}, {readonly_role}")
        privileges = "SELECT, INSERT" if table in APPEND_ONLY else "SELECT, INSERT, UPDATE"
        op.execute(f"GRANT {privileges} ON TABLE {table} TO {app_role}")
    op.execute(f"GRANT SELECT ON TABLE batches TO {readonly_role}")

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
    op.execute(
        f"CREATE POLICY batches_readonly_tenant_read ON batches FOR SELECT "
        f"TO {readonly_role} USING (tenant_id = {T})"
    )

    # --- Permission catalogue and system roles --------------------------------------------
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
    for codes, templates in EXTENDED:
        _grant(codes, templates)


def downgrade() -> None:
    for table, trigger in PROTECTION_TRIGGERS:
        op.execute(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}")
    op.execute(f"DELETE FROM role_permissions WHERE permission_code IN ({_sql_list(CODES)})")
    for table, trigger in PROTECTION_TRIGGERS:
        op.execute(f"ALTER TABLE {table} ENABLE TRIGGER {trigger}")
    op.execute(f"DELETE FROM permissions WHERE realm = 'tenant' AND code IN ({_sql_list(CODES)})")
    for table in reversed(TABLES):
        op.drop_table(table)  # drops its indexes, policies and triggers
    op.execute(f"DROP FUNCTION {COUNT_FUNCTION}()")
    op.execute("UPDATE admissions SET status = 'ADMITTED' WHERE status = 'ENROLLED'")
    _replace_admission_statuses(ADMISSION_STATUSES_0013)
