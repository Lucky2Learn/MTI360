# SQL is assembled only from the frozen constants below (no input): S608 is a false positive.
# ruff: noqa: S608
"""Finance-lite: fee structures, non-tax fee invoices, offline payments and receipts (Phase 02-5).

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-10

ADR-0022:

* ``fee_structures`` (institute-wide per course; ``items`` frozen outside
  ``DRAFT`` by a trigger; one ``ACTIVE`` per course), ``invoices`` (non-tax
  fee invoices; one live invoice per admission; a five-column composite key
  binds admission, student, campus and course to one admission row),
  ``invoice_lines`` (structure and issued amounts), ``payments`` (offline;
  cheque and demand draft ``PENDING`` until cleared), ``receipts`` and
  ``finance_activities``. Amounts are integer paise, currency ``INR`` only.
* ``admissions`` gains ``UNIQUE (tenant_id, id, student_id, campus_id,
  course_id)``, the target of the fee invoice's key.
* ``tenant_sequences.name`` accepts ``INVOICE`` and ``RECEIPT``; for those,
  ``period`` is the Indian financial year's start year (ADR-0022 §3).
* Realm-agnostic tenant Row-Level Security. The application role gets
  SELECT, INSERT, UPDATE (never DELETE), and only SELECT, INSERT on
  ``invoice_lines``, ``receipts`` and ``finance_activities``. The read-only
  role reads ``fee_structures`` only (no personal or payment data).
* Permissions: seven tenant permissions. New system templates
  ``FINANCE_MANAGER`` (all seven) and ``FINANCE_OFFICER`` are cloned into
  every tenant; ``INSTITUTE_OWNER`` / ``ADMIN`` gain all seven,
  ``ADMISSIONS_MANAGER`` gains ``fee_structure.read`` and ``invoice.read``,
  ``COUNSELLOR`` gains ``fee_structure.read``. The finance templates also
  read courses and students. The upgrade refuses a custom role named like a
  new system role. Nobody is assigned a role.

The downgrade is a development operation that loses data: it drops the
finance tables, removes ``INVOICE`` / ``RECEIPT`` counters, the two system
roles (and their assignments) and the seven permissions. No SECURITY DEFINER.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migrations.helpers import database_roles, quote_role

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# --- Frozen copies at this revision (never import app code into migrations) -----------
T = "nullif(current_setting('app.tenant_id', true), '')::uuid"
CURRENCY = "INR"
MAX_AMOUNT_MINOR = 100_000_000_000
NAME_MAX = 200
FEE_HEAD_MAX = 100
REASON_MAX = 500
REFERENCE_MAX = 100
NUMBER_MAX = 32
HASH_LENGTH = 64
FEE_STRUCTURE_STATUSES = ("DRAFT", "ACTIVE", "ARCHIVED")
INVOICE_STATUSES = ("ISSUED", "PARTIALLY_PAID", "PAID", "CANCELLED")
PAYMENT_METHODS = ("CASH", "UPI", "BANK_TRANSFER", "CHEQUE", "DEMAND_DRAFT")
CLEARANCE_METHODS = ("CHEQUE", "DEMAND_DRAFT")
PAYMENT_STATUSES = ("PENDING", "CONFIRMED", "FAILED", "REVERSED")
ACTIVITY_KINDS = (
    "ISSUED",
    "CANCELLED",
    "PAYMENT_RECORDED",
    "PAYMENT_CONFIRMED",
    "PAYMENT_FAILED",
    "PAYMENT_REVERSED",
)
SEQUENCE_NAMES_0010 = ("APPLICATION", "ADMISSION", "STUDENT")
SEQUENCE_NAMES = (*SEQUENCE_NAMES_0010, "INVOICE", "RECEIPT")

# (realm, code, scope, module, description) — equal to the code registry (drift test).
PERMISSIONS: tuple[tuple[str, str, str, str, str], ...] = (
    ("tenant", "fee_structure.read", "campus", "finance", "View fee structures"),
    (
        "tenant",
        "fee_structure.manage",
        "tenant",
        "finance",
        "Create, edit, activate and archive fee structures",
    ),
    ("tenant", "invoice.read", "campus", "finance", "View fee invoices, payments and receipts"),
    ("tenant", "invoice.issue", "campus", "finance", "Issue fee invoices"),
    ("tenant", "invoice.cancel", "campus", "finance", "Cancel fee invoices"),
    (
        "tenant",
        "payment.record",
        "campus",
        "finance",
        "Record payments and confirm or fail pending cheques and demand drafts",
    ),
    ("tenant", "payment.reverse", "campus", "finance", "Reverse confirmed payments"),
)
CODES = tuple(code for _, code, *_ in PERMISSIONS)
FINANCE_OFFICER_CODES = (
    "fee_structure.read",
    "invoice.read",
    "invoice.issue",
    "payment.record",
    "course.read",
    "student.read",
)
FINANCE_MANAGER_CODES = (*CODES, "course.read", "student.read")
# (template_code, name, description, codes)
NEW_SYSTEM_ROLES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "FINANCE_MANAGER",
        "Finance manager",
        "Runs student fees: fee structures, fee invoices and their cancellation, payments, "
        "receipts and reversals; reads courses and students.",
        FINANCE_MANAGER_CODES,
    ),
    (
        "FINANCE_OFFICER",
        "Finance officer",
        "Collects student fees: issues fee invoices, records payments and confirms or fails "
        "cheques and demand drafts; reads fee structures, courses and students.",
        FINANCE_OFFICER_CODES,
    ),
)
NEW_TEMPLATES = tuple(template for template, *_ in NEW_SYSTEM_ROLES)
EXTENDED: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (CODES, ("INSTITUTE_OWNER", "ADMIN")),
    (("fee_structure.read", "invoice.read"), ("ADMISSIONS_MANAGER",)),
    (("fee_structure.read",), ("COUNSELLOR",)),
)
PROTECTION_TRIGGERS = (
    ("roles", "roles_protect_system"),
    ("role_permissions", "role_permissions_protect_system"),
)

TABLES = (
    "fee_structures",
    "invoices",
    "invoice_lines",
    "payments",
    "receipts",
    "finance_activities",
)
APPEND_ONLY = ("invoice_lines", "receipts", "finance_activities")
ADMISSIONS_KEY = "uq_admissions_tenant_id_id_student_id_campus_id_course_id"
FREEZE_FUNCTION = "fee_structures_freeze_items"
FREEZE_ERRCODE = "MT011"
FREEZE_BODY = f"""
        BEGIN
            IF OLD.status <> 'DRAFT' AND (
                NEW.items IS DISTINCT FROM OLD.items
                OR NEW.total_minor IS DISTINCT FROM OLD.total_minor
                OR NEW.course_id IS DISTINCT FROM OLD.course_id
                OR NEW.name IS DISTINCT FROM OLD.name
                OR NEW.currency IS DISTINCT FROM OLD.currency
            ) THEN
                RAISE EXCEPTION 'an active or archived fee structure cannot be changed'
                    USING ERRCODE = '{FREEZE_ERRCODE}';
            END IF;
            RETURN NEW;
        END
"""


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _sql_list(values: Sequence[str]) -> str:
    return ", ".join("'" + value.replace("'", "''") + "'" for value in values)


def _amount(column: str, *, positive: bool) -> str:
    low = f"{column} > 0" if positive else f"{column} >= 0"
    return f"{low} AND {column} <= {MAX_AMOUNT_MINOR}"


def _id(name: str = "id", *, nullable: bool = False) -> sa.Column[Any]:
    return sa.Column(name, sa.Uuid(), nullable=nullable)


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


def _currency(table: str) -> sa.CheckConstraint:
    return _check(table, "currency", f"currency = '{CURRENCY}'")


def _create_tables() -> None:
    op.create_table(
        "fee_structures",
        _id(),
        _id("tenant_id"),
        _id("course_id"),
        sa.Column("name", sa.String(length=NAME_MAX), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("total_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        _id("created_by_membership_id"),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        _created(),
        _updated(),
        _version(),
        *_keys("fee_structures"),
        _composite_fk("course_id", "courses", "fk_fee_structures_course"),
        _composite_fk(
            "created_by_membership_id", "tenant_memberships", "fk_fee_structures_created_by"
        ),
        _check("fee_structures", "name", "btrim(name) <> ''"),
        _check("fee_structures", "status", _in("status", FEE_STRUCTURE_STATUSES)),
        _check("fee_structures", "items_array", "jsonb_typeof(items) = 'array'"),
        _check("fee_structures", "total_minor", _amount("total_minor", positive=True)),
        _currency("fee_structures"),
        _check("fee_structures", "activated_at", "(status = 'DRAFT') = (activated_at IS NULL)"),
        _check(
            "fee_structures", "archived_at", "(status = 'ARCHIVED') = (archived_at IS NOT NULL)"
        ),
    )
    _index("fee_structures", "tenant_id", "course_id", "status")
    op.create_index(
        "uq_fee_structures_tenant_id_course_id_active",
        "fee_structures",
        ["tenant_id", "course_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    op.create_table(
        "invoices",
        _id(),
        _id("tenant_id"),
        sa.Column("number", sa.String(length=NUMBER_MAX), nullable=False),
        _id("admission_id"),
        _id("student_id"),
        _id("course_id"),
        _id("campus_id"),
        _id("fee_structure_id"),
        sa.Column("fee_structure_version", sa.Integer(), nullable=False),
        sa.Column("structure_total_minor", sa.BigInteger(), nullable=False),
        sa.Column("total_minor", sa.BigInteger(), nullable=False),
        sa.Column("paid_minor", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("adjusted", sa.Boolean(), nullable=False),
        sa.Column("adjustment_reason", sa.String(length=REASON_MAX), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("status_reason", sa.String(length=REASON_MAX), nullable=True),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        _id("issued_by_membership_id"),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        _id("cancelled_by_membership_id", nullable=True),
        _id("idempotency_key"),
        sa.Column("request_hash", sa.String(length=HASH_LENGTH), nullable=False),
        _created(),
        _updated(),
        _version(),
        *_keys("invoices"),
        sa.UniqueConstraint("tenant_id", "number", name=op.f("uq_invoices_tenant_id_number")),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name=op.f("uq_invoices_tenant_id_idempotency_key")
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            "student_id",
            "campus_id",
            name=op.f("uq_invoices_tenant_id_id_student_id_campus_id"),
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
            name="fk_invoices_admission",
            ondelete="RESTRICT",
        ),
        _composite_fk("fee_structure_id", "fee_structures", "fk_invoices_fee_structure"),
        _composite_fk("issued_by_membership_id", "tenant_memberships", "fk_invoices_issued_by"),
        _composite_fk(
            "cancelled_by_membership_id", "tenant_memberships", "fk_invoices_cancelled_by"
        ),
        _check("invoices", "status", _in("status", INVOICE_STATUSES)),
        _check("invoices", "total_minor", _amount("total_minor", positive=True)),
        _check("invoices", "structure_total", _amount("structure_total_minor", positive=True)),
        _check("invoices", "paid_minor", "paid_minor >= 0 AND paid_minor <= total_minor"),
        _check(
            "invoices",
            "status_paid",
            "(status IN ('ISSUED', 'CANCELLED') AND paid_minor = 0) "
            "OR (status = 'PARTIALLY_PAID' AND paid_minor > 0 AND paid_minor < total_minor) "
            "OR (status = 'PAID' AND paid_minor = total_minor)",
        ),
        _currency("invoices"),
        _check("invoices", "adjustment_reason", "adjusted = (adjustment_reason IS NOT NULL)"),
        _check("invoices", "status_reason", "(status = 'CANCELLED') = (status_reason IS NOT NULL)"),
        _check(
            "invoices",
            "cancelled",
            "(status = 'CANCELLED') = (cancelled_at IS NOT NULL) "
            "AND (cancelled_at IS NULL) = (cancelled_by_membership_id IS NULL)",
        ),
        _check("invoices", "request_hash", f"char_length(request_hash) = {HASH_LENGTH}"),
    )
    _index("invoices", "tenant_id", "campus_id", "status", "due_date")
    _index("invoices", "tenant_id", "student_id")
    _index("invoices", "tenant_id", "issued_at")
    op.create_index(
        "uq_invoices_tenant_id_admission_id_live",
        "invoices",
        ["tenant_id", "admission_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'CANCELLED'"),
    )

    op.create_table(
        "invoice_lines",
        _id(),
        _id("tenant_id"),
        _id("invoice_id"),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("fee_head", sa.String(length=FEE_HEAD_MAX), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("structure_amount_minor", sa.BigInteger(), nullable=True),
        _created(),
        *_keys("invoice_lines"),
        sa.UniqueConstraint(
            "tenant_id",
            "invoice_id",
            "position",
            name=op.f("uq_invoice_lines_tenant_id_invoice_id_position"),
        ),
        _composite_fk("invoice_id", "invoices", "fk_invoice_lines_invoice"),
        _check("invoice_lines", "position", "position BETWEEN 1 AND 100"),
        _check("invoice_lines", "fee_head", "btrim(fee_head) <> ''"),
        _check("invoice_lines", "amount_minor", _amount("amount_minor", positive=False)),
        _check(
            "invoice_lines",
            "structure_amount_minor",
            "structure_amount_minor IS NULL OR "
            f"({_amount('structure_amount_minor', positive=False)})",
        ),
    )

    op.create_table(
        "payments",
        _id(),
        _id("tenant_id"),
        _id("invoice_id"),
        _id("student_id"),
        _id("campus_id"),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("reference", sa.String(length=REFERENCE_MAX), nullable=True),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("status_reason", sa.String(length=REASON_MAX), nullable=True),
        _id("recorded_by_membership_id"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        _id("confirmed_by_membership_id", nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        _id("closed_by_membership_id", nullable=True),
        _id("idempotency_key"),
        sa.Column("request_hash", sa.String(length=HASH_LENGTH), nullable=False),
        _created(),
        _updated(),
        _version(),
        *_keys("payments"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name=op.f("uq_payments_tenant_id_idempotency_key")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "invoice_id", "student_id", "campus_id"],
            ["invoices.tenant_id", "invoices.id", "invoices.student_id", "invoices.campus_id"],
            name="fk_payments_invoice",
            ondelete="RESTRICT",
        ),
        _composite_fk("recorded_by_membership_id", "tenant_memberships", "fk_payments_recorded_by"),
        _composite_fk(
            "confirmed_by_membership_id", "tenant_memberships", "fk_payments_confirmed_by"
        ),
        _composite_fk("closed_by_membership_id", "tenant_memberships", "fk_payments_closed_by"),
        _check("payments", "amount_minor", _amount("amount_minor", positive=True)),
        _currency("payments"),
        _check("payments", "method", _in("method", PAYMENT_METHODS)),
        _check("payments", "status", _in("status", PAYMENT_STATUSES)),
        _check(
            "payments",
            "reference",
            "method = 'CASH' OR (reference IS NOT NULL AND btrim(reference) <> '')",
        ),
        _check(
            "payments",
            "clearance_method",
            f"status NOT IN ('PENDING', 'FAILED') OR {_in('method', CLEARANCE_METHODS)}",
        ),
        _check(
            "payments",
            "status_reason",
            "(status IN ('FAILED', 'REVERSED')) = (status_reason IS NOT NULL)",
        ),
        _check(
            "payments",
            "confirmed",
            "(status IN ('CONFIRMED', 'REVERSED')) = (confirmed_at IS NOT NULL) "
            "AND (confirmed_at IS NULL) = (confirmed_by_membership_id IS NULL)",
        ),
        _check(
            "payments",
            "closed",
            "(status IN ('FAILED', 'REVERSED')) = (closed_at IS NOT NULL) "
            "AND (closed_at IS NULL) = (closed_by_membership_id IS NULL)",
        ),
        _check("payments", "request_hash", f"char_length(request_hash) = {HASH_LENGTH}"),
    )
    _index("payments", "tenant_id", "invoice_id")
    _index("payments", "tenant_id", "campus_id", "status", "received_on")

    op.create_table(
        "receipts",
        _id(),
        _id("tenant_id"),
        sa.Column("number", sa.String(length=NUMBER_MAX), nullable=False),
        _id("payment_id"),
        sa.Column("invoice_number", sa.String(length=NUMBER_MAX), nullable=False),
        sa.Column("student_number", sa.String(length=NUMBER_MAX), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        *_keys("receipts"),
        sa.UniqueConstraint("tenant_id", "number", name=op.f("uq_receipts_tenant_id_number")),
        sa.UniqueConstraint(
            "tenant_id", "payment_id", name=op.f("uq_receipts_tenant_id_payment_id")
        ),
        _composite_fk("payment_id", "payments", "fk_receipts_payment"),
        _check("receipts", "amount_minor", _amount("amount_minor", positive=True)),
        _currency("receipts"),
        _check("receipts", "method", _in("method", PAYMENT_METHODS)),
    )

    op.create_table(
        "finance_activities",
        _id(),
        _id("tenant_id"),
        _id("invoice_id"),
        sa.Column("kind", sa.String(length=32), nullable=False),
        _id("actor_membership_id", nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        _created(),
        *_keys("finance_activities"),
        _composite_fk("invoice_id", "invoices", "fk_finance_activities_invoice"),
        _composite_fk("actor_membership_id", "tenant_memberships", "fk_finance_activities_actor"),
        _check("finance_activities", "kind", _in("kind", ACTIVITY_KINDS)),
        _check("finance_activities", "details_object", "jsonb_typeof(details) = 'object'"),
    )
    _index("finance_activities", "tenant_id", "invoice_id", "created_at")


def _replace_sequence_names(names: Sequence[str]) -> None:
    op.execute("ALTER TABLE tenant_sequences DROP CONSTRAINT ck_tenant_sequences_name")
    op.execute(
        "ALTER TABLE tenant_sequences ADD CONSTRAINT ck_tenant_sequences_name "
        f"CHECK ({_in('name', names)})"
    )


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
    _refuse_role_name_clashes()

    op.create_unique_constraint(
        ADMISSIONS_KEY, "admissions", ["tenant_id", "id", "student_id", "campus_id", "course_id"]
    )
    _create_tables()
    _replace_sequence_names(SEQUENCE_NAMES)

    # --- The fee-structure freeze (plain SECURITY INVOKER trigger) -------------------------
    op.execute(
        f"CREATE FUNCTION {FREEZE_FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $${FREEZE_BODY}$$"
    )
    op.execute(
        f"CREATE TRIGGER {FREEZE_FUNCTION} BEFORE UPDATE ON fee_structures "
        f"FOR EACH ROW EXECUTE FUNCTION {FREEZE_FUNCTION}()"
    )

    # --- Privileges: replace the defaults --------------------------------------------------
    for table in TABLES:
        op.execute(f"REVOKE ALL ON TABLE {table} FROM {app_role}, {readonly_role}")
        privileges = "SELECT, INSERT" if table in APPEND_ONLY else "SELECT, INSERT, UPDATE"
        op.execute(f"GRANT {privileges} ON TABLE {table} TO {app_role}")
    op.execute(f"GRANT SELECT ON TABLE fee_structures TO {readonly_role}")

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
        f"CREATE POLICY fee_structures_readonly_tenant_read ON fee_structures FOR SELECT "
        f"TO {readonly_role} USING (tenant_id = {T})"
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
    for codes, templates in EXTENDED:
        _grant(codes, templates)


def downgrade() -> None:
    new_roles = f"SELECT id FROM roles WHERE template_code IN ({_sql_list(NEW_TEMPLATES)})"
    op.execute(f"DELETE FROM membership_roles WHERE role_id IN ({new_roles})")
    for table, trigger in PROTECTION_TRIGGERS:
        op.execute(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}")
    op.execute(f"DELETE FROM role_permissions WHERE permission_code IN ({_sql_list(CODES)})")
    op.execute(f"DELETE FROM role_permissions WHERE role_id IN ({new_roles})")
    op.execute(f"DELETE FROM roles WHERE template_code IN ({_sql_list(NEW_TEMPLATES)})")
    for table, trigger in PROTECTION_TRIGGERS:
        op.execute(f"ALTER TABLE {table} ENABLE TRIGGER {trigger}")
    op.execute(f"DELETE FROM permissions WHERE realm = 'tenant' AND code IN ({_sql_list(CODES)})")
    for table in reversed(TABLES):
        op.drop_table(table)  # drops its indexes, policies and triggers
    op.execute(f"DROP FUNCTION {FREEZE_FUNCTION}()")
    op.execute("DELETE FROM tenant_sequences WHERE name IN ('INVOICE', 'RECEIPT')")
    _replace_sequence_names(SEQUENCE_NAMES_0010)
    op.drop_constraint(ADMISSIONS_KEY, "admissions", type_="unique")
