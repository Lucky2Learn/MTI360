# SQL is assembled only from the constant table names below: S608 is a false positive.
# ruff: noqa: S608
"""Finance-lite schema, Row-Level Security and migration 0011 (Phase 02-5; ADR-0022).

Raw SQL through the real runtime roles and trusted ``SET LOCAL`` settings, so
only the database protects the rows:

* tenant isolation (RLS) on every finance table; no DELETE for anyone at
  runtime; ``invoice_lines``, ``receipts`` and ``finance_activities`` are
  insert-only; the read-only role reads ``fee_structures`` only;
* composite keys: a fee invoice's admission, student, campus and course are
  one admission's; a payment's student and campus are its invoice's; nothing
  points at another tenant's row;
* one ACTIVE fee structure per course, frozen once active; one live fee
  invoice per admission; INR only; the status, reason and reference rules;
* ``tenant_sequences`` accepts INVOICE and RECEIPT;
* migration 0011: down (tables, permissions, finance roles, counters and the
  admissions key removed), up again; templates and clones agree.
"""

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, cast

import anyio
import pytest
from alembic import command
from conftest import DatabaseUnderTest
from identity_support import World, build_world
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.context import Realm, RequestContext
from app.core.db import create_sessionmaker
from app.core.db.session import context_transaction
from app.modules.access.templates import system_role_templates

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

TABLES = (
    "fee_structures",
    "invoices",
    "invoice_lines",
    "payments",
    "receipts",
    "finance_activities",
)
INSERT_ONLY = ("invoice_lines", "receipts", "finance_activities")
NEW_CODES = (
    "fee_structure.read",
    "fee_structure.manage",
    "invoice.read",
    "invoice.issue",
    "invoice.cancel",
    "payment.record",
    "payment.reverse",
)
HASH = "a" * 64
NOW = datetime.now(UTC)
ITEMS = json.dumps([{"fee_head": "Tuition", "amount_minor": 25_000_000}])


@dataclass
class Rows:
    tenant: uuid.UUID
    membership: uuid.UUID
    campus: uuid.UUID
    course: uuid.UUID
    application: uuid.UUID
    student: uuid.UUID
    admission: uuid.UUID
    structure: uuid.UUID
    invoice: uuid.UUID
    payment: uuid.UUID


@pytest.fixture
async def app_db(
    migrated_database: DatabaseUnderTest,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(migrated_database.app_url, poolclass=NullPool)
    try:
        yield create_sessionmaker(engine)
    finally:
        await engine.dispose()


@pytest.fixture
async def readonly_db(
    migrated_database: DatabaseUnderTest,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(migrated_database.readonly_url, poolclass=NullPool)
    try:
        yield create_sessionmaker(engine)
    finally:
        await engine.dispose()


@pytest.fixture
async def world(app_db: async_sessionmaker[AsyncSession]) -> World:
    return await build_world(app_db)


async def _owner(database: DatabaseUnderTest, sql: str, **params: Any) -> list[Any]:
    engine = create_async_engine(database.owner_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            result = await connection.execute(text(sql), params)
            return list(result.all()) if result.returns_rows else []
    finally:
        await engine.dispose()


async def _run(
    factory: async_sessionmaker[AsyncSession], sql: str, *, tenant: uuid.UUID | None, **params: Any
) -> Any:
    context = RequestContext(realm=Realm.TENANT, request_id=uuid.uuid7(), tenant_id=tenant)
    async with context_transaction(factory, context) as db:
        result = cast(CursorResult[Any], await db.execute(text(sql), params))
        if result.returns_rows:
            return set(result.scalars())
        return result.rowcount


async def _error(coroutine: Any) -> str:
    try:
        await coroutine
    except DBAPIError as error:
        return str(error.orig).lower()
    return ""


INSERT_STRUCTURE = (
    "INSERT INTO fee_structures (id, tenant_id, course_id, name, status, items, total_minor, "
    "currency, created_by_membership_id, activated_at, version) VALUES (:id, :t, :course, "
    "'DNS 2026', :status, CAST(:items AS jsonb), 25000000, 'INR', :m, :activated, 1)"
)
INSERT_INVOICE = (
    "INSERT INTO invoices (id, tenant_id, number, admission_id, student_id, course_id, "
    "campus_id, fee_structure_id, fee_structure_version, structure_total_minor, total_minor, "
    "paid_minor, currency, due_date, adjusted, adjustment_reason, status, status_reason, "
    "issued_by_membership_id, cancelled_at, cancelled_by_membership_id, idempotency_key, "
    "request_hash, version) VALUES (:id, :t, :number, :admission, :student, :course, :campus, "
    ":structure, 1, 25000000, :total, :paid, :currency, :due, :adjusted, :adj_reason, "
    ":status, :reason, :m, :cancelled_at, :cancelled_by, :key, :hash, 1)"
)
INSERT_PAYMENT = (
    "INSERT INTO payments (id, tenant_id, invoice_id, student_id, campus_id, amount_minor, "
    "currency, method, reference, received_on, status, status_reason, "
    "recorded_by_membership_id, confirmed_at, confirmed_by_membership_id, closed_at, "
    "closed_by_membership_id, idempotency_key, request_hash, version) VALUES (:id, :t, "
    ":invoice, :student, :campus, :amount, 'INR', :method, :reference, :received, :status, "
    ":reason, :m, :confirmed_at, :confirmed_by, :closed_at, :closed_by, :key, :hash, 1)"
)


def _invoice(rows: Rows, **changes: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "id": uuid.uuid7(),
        "t": rows.tenant,
        "number": f"INV-FY2026-27-{uuid.uuid7().hex[-6:]}",
        "admission": rows.admission,
        "student": rows.student,
        "course": rows.course,
        "campus": rows.campus,
        "structure": rows.structure,
        "total": 25_000_000,
        "paid": 0,
        "currency": "INR",
        "due": date(2026, 6, 30),
        "adjusted": False,
        "adj_reason": None,
        "status": "ISSUED",
        "reason": None,
        "m": rows.membership,
        "cancelled_at": None,
        "cancelled_by": None,
        "key": uuid.uuid4(),
        "hash": HASH,
    }
    return {**values, **changes}


def _payment(rows: Rows, **changes: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "id": uuid.uuid7(),
        "t": rows.tenant,
        "invoice": rows.invoice,
        "student": rows.student,
        "campus": rows.campus,
        "amount": 5_000_000,
        "method": "CASH",
        "reference": None,
        "received": date(2026, 6, 1),
        "status": "CONFIRMED",
        "reason": None,
        "m": rows.membership,
        "confirmed_at": NOW,
        "confirmed_by": rows.membership,
        "closed_at": None,
        "closed_by": None,
        "key": uuid.uuid4(),
        "hash": HASH,
    }
    return {**values, **changes}


async def _rows(database: DatabaseUnderTest, tenant: uuid.UUID, membership: uuid.UUID) -> Rows:
    """An admitted student with a fee structure, an invoice, a payment, a receipt and activity."""
    campus = (await _owner(database, "SELECT id FROM campuses WHERE tenant_id = :t", t=tenant))[0][
        0
    ]
    ids = {name: uuid.uuid7() for name in ("course", "app", "stu", "adm", "fs", "inv", "pay")}
    suffix = ids["course"].hex[-6:].upper()
    await _owner(
        database,
        "INSERT INTO courses (id, tenant_id, code, name, category, status, version) "
        "VALUES (:id, :t, :code, 'Diploma in Nautical Science', 'PRE_SEA', 'ACTIVE', 1)",
        id=ids["course"],
        t=tenant,
        code=f"DNS{suffix}",
    )
    await _owner(
        database,
        "INSERT INTO applications (id, tenant_id, number, course_id, campus_id, "
        "owner_membership_id, created_by_membership_id, full_name, status, submitted_at, "
        "version) VALUES (:id, :t, :number, :course, :campus, :m, :m, 'Kavya Menon', "
        "'ADMITTED', :now, 1)",
        id=ids["app"],
        t=tenant,
        number=f"APP-2026-{suffix}",
        course=ids["course"],
        campus=campus,
        m=membership,
        now=NOW,
    )
    await _owner(
        database,
        "INSERT INTO students (id, tenant_id, student_number, home_campus_id, full_name, "
        "created_by_membership_id, version) VALUES (:id, :t, :number, :campus, 'Kavya Menon', "
        ":m, 1)",
        id=ids["stu"],
        t=tenant,
        number=f"STU-2026-{suffix}",
        campus=campus,
        m=membership,
    )
    await _owner(
        database,
        "INSERT INTO admissions (id, tenant_id, admission_number, application_id, student_id, "
        "course_id, campus_id, approved_by_membership_id, version) VALUES (:id, :t, :number, "
        ":app, :stu, :course, :campus, :m, 1)",
        id=ids["adm"],
        t=tenant,
        number=f"ADM-2026-{suffix}",
        app=ids["app"],
        stu=ids["stu"],
        course=ids["course"],
        campus=campus,
        m=membership,
    )
    await _owner(
        database,
        INSERT_STRUCTURE,
        id=ids["fs"],
        t=tenant,
        course=ids["course"],
        status="ACTIVE",
        items=ITEMS,
        m=membership,
        activated=NOW,
    )
    rows = Rows(
        tenant,
        membership,
        campus,
        ids["course"],
        ids["app"],
        ids["stu"],
        ids["adm"],
        ids["fs"],
        ids["inv"],
        ids["pay"],
    )
    await _owner(
        database,
        INSERT_INVOICE,
        **_invoice(rows, id=ids["inv"], status="PARTIALLY_PAID", paid=5_000_000),
    )
    await _owner(
        database,
        "INSERT INTO invoice_lines (id, tenant_id, invoice_id, position, fee_head, amount_minor, "
        "structure_amount_minor) VALUES (:id, :t, :inv, 1, 'Tuition', 25000000, 25000000)",
        id=uuid.uuid7(),
        t=tenant,
        inv=ids["inv"],
    )
    await _owner(database, INSERT_PAYMENT, **_payment(rows, id=ids["pay"]))
    await _owner(
        database,
        "INSERT INTO receipts (id, tenant_id, number, payment_id, invoice_number, "
        "student_number, amount_minor, currency, method) VALUES (:id, :t, :number, :pay, "
        "'INV-FY2026-27-00001', :stu, 5000000, 'INR', 'CASH')",
        id=uuid.uuid7(),
        t=tenant,
        number=f"RCT-FY2026-27-{suffix}",
        pay=ids["pay"],
        stu=f"STU-2026-{suffix}",
    )
    await _owner(
        database,
        "INSERT INTO finance_activities (id, tenant_id, invoice_id, kind, details) "
        "VALUES (:id, :t, :inv, 'ISSUED', '{}')",
        id=uuid.uuid7(),
        t=tenant,
        inv=ids["inv"],
    )
    return rows


@pytest.fixture
async def rows(migrated_database: DatabaseUnderTest, world: World) -> tuple[Rows, Rows]:
    a = await _rows(migrated_database, world.tenant_a, world.memberships["alice_a"])
    b = await _rows(migrated_database, world.tenant_b, world.memberships["carol_b"])
    return a, b


async def test_every_finance_table_is_isolated_by_tenant(
    app_db: async_sessionmaker[AsyncSession], rows: tuple[Rows, Rows]
) -> None:
    a, b = rows
    for table in TABLES:
        seen = await _run(app_db, f"SELECT tenant_id FROM {table}", tenant=a.tenant)
        assert seen == {a.tenant}, table
        assert await _run(app_db, f"SELECT id FROM {table}", tenant=None) == set(), table
    # Writing a row for another tenant is refused by the policy's WITH CHECK.
    assert "row-level security" in await _error(
        _run(app_db, INSERT_PAYMENT, tenant=a.tenant, **_payment(b))
    )
    # Updating another tenant's invoice matches nothing.
    moved = await _run(
        app_db,
        "UPDATE invoices SET due_date = due_date + 1 WHERE id = :id",
        tenant=a.tenant,
        id=b.invoice,
    )
    assert moved == 0


async def test_no_delete_and_insert_only_tables(
    app_db: async_sessionmaker[AsyncSession], rows: tuple[Rows, Rows]
) -> None:
    a, _ = rows
    for table in TABLES:
        assert "permission denied" in await _error(
            _run(app_db, f"DELETE FROM {table}", tenant=a.tenant)
        ), table
    for table in INSERT_ONLY:
        assert "permission denied" in await _error(
            _run(app_db, f"UPDATE {table} SET created_at = now()", tenant=a.tenant)
            if table != "receipts"
            else _run(app_db, "UPDATE receipts SET issued_at = now()", tenant=a.tenant)
        ), table


async def test_the_readonly_role_reads_fee_structures_only(
    readonly_db: async_sessionmaker[AsyncSession], rows: tuple[Rows, Rows]
) -> None:
    a, _ = rows
    assert await _run(readonly_db, "SELECT tenant_id FROM fee_structures", tenant=a.tenant) == {
        a.tenant
    }
    for table in TABLES[1:]:
        assert "permission denied" in await _error(
            _run(readonly_db, f"SELECT id FROM {table}", tenant=a.tenant)
        ), table


async def test_composite_keys_bind_invoices_and_payments_to_one_admission(
    migrated_database: DatabaseUnderTest, rows: tuple[Rows, Rows]
) -> None:
    a, b = rows
    # Cancelled rows, so that the one-live-invoice index does not answer first.
    cancelled = {
        "status": "CANCELLED",
        "reason": "Test",
        "cancelled_at": NOW,
        "cancelled_by": a.membership,
    }
    # Another tenant's rows, and a student, campus or course that is not the admission's.
    for change in (
        {"admission": b.admission},
        {"student": b.student},
        {"structure": b.structure},
        {"course": b.course},
        {"campus": b.campus},
    ):
        assert "foreign key" in await _error(
            _owner(migrated_database, INSERT_INVOICE, **_invoice(a, **cancelled, **change))
        ), change
    other_student = uuid.uuid7()
    await _owner(
        migrated_database,
        "INSERT INTO students (id, tenant_id, student_number, home_campus_id, full_name, "
        "created_by_membership_id, version) VALUES (:id, :t, :n, :c, 'Rohan Das', :m, 1)",
        id=other_student,
        t=a.tenant,
        n=f"STU-2026-{other_student.hex[-6:]}",
        c=a.campus,
        m=a.membership,
    )
    assert "fk_invoices_admission" in await _error(
        _owner(
            migrated_database,
            INSERT_INVOICE,
            **_invoice(a, **cancelled, student=other_student),
        )
    )
    # A payment's student and campus are its invoice's.
    for change in ({"invoice": b.invoice}, {"student": other_student}, {"campus": b.campus}):
        assert "foreign key" in await _error(
            _owner(migrated_database, INSERT_PAYMENT, **_payment(a, **change))
        ), change


async def test_one_active_structure_per_course_frozen_once_active(
    migrated_database: DatabaseUnderTest, rows: tuple[Rows, Rows]
) -> None:
    a, _ = rows
    assert "uq_fee_structures_tenant_id_course_id_active" in await _error(
        _owner(
            migrated_database,
            INSERT_STRUCTURE,
            id=uuid.uuid7(),
            t=a.tenant,
            course=a.course,
            status="ACTIVE",
            items=ITEMS,
            m=a.membership,
            activated=NOW,
        )
    )
    for change in (
        "items = '[]'::jsonb",
        "total_minor = 1",
        "name = 'Renamed'",
    ):
        assert "cannot be changed" in await _error(
            _owner(
                migrated_database,
                f"UPDATE fee_structures SET {change} WHERE id = :id",
                id=a.structure,
            )
        ), change
    # A draft may change; archiving the active one is allowed (status and timestamps only).
    draft = uuid.uuid7()
    await _owner(
        migrated_database,
        INSERT_STRUCTURE,
        id=draft,
        t=a.tenant,
        course=a.course,
        status="DRAFT",
        items=ITEMS,
        m=a.membership,
        activated=None,
    )
    await _owner(
        migrated_database,
        "UPDATE fee_structures SET name = 'DNS 2027', total_minor = 1 WHERE id = :id",
        id=draft,
    )
    await _owner(
        migrated_database,
        "UPDATE fee_structures SET status = 'ARCHIVED', archived_at = now() WHERE id = :id",
        id=a.structure,
    )
    for status, activated, constraint in (
        ("ACTIVE", None, "ck_fee_structures_activated_at"),
        ("PUBLISHED", NOW, "ck_fee_structures_status"),
    ):
        assert constraint in await _error(
            _owner(
                migrated_database,
                INSERT_STRUCTURE,
                id=uuid.uuid7(),
                t=a.tenant,
                course=a.course,
                status=status,
                items=ITEMS,
                m=a.membership,
                activated=activated,
            )
        ), status


async def test_one_live_invoice_per_admission_and_invoice_rules(
    migrated_database: DatabaseUnderTest, rows: tuple[Rows, Rows]
) -> None:
    a, _ = rows
    assert "uq_invoices_tenant_id_admission_id_live" in await _error(
        _owner(migrated_database, INSERT_INVOICE, **_invoice(a))
    )
    for change, constraint in (
        ({"currency": "USD"}, "ck_invoices_currency"),
        ({"total": 0}, "ck_invoices_total_minor"),
        ({"status": "PAID", "paid": 1}, "ck_invoices_status_paid"),
        ({"status": "ISSUED", "paid": 1}, "ck_invoices_status_paid"),
        ({"adjusted": True}, "ck_invoices_adjustment_reason"),
        ({"adj_reason": "Scholarship"}, "ck_invoices_adjustment_reason"),
        (
            {"status": "CANCELLED", "cancelled_at": NOW, "cancelled_by": a.membership},
            "ck_invoices_status_reason",
        ),
        ({"status": "CANCELLED", "reason": "Wrong course"}, "ck_invoices_cancelled"),
        ({"hash": "short"}, "ck_invoices_request_hash"),
    ):
        assert constraint in await _error(
            _owner(migrated_database, INSERT_INVOICE, **_invoice(a, **change))
        ), change
    # Paid above the total breaks both the range and the status rule.
    error = await _error(_owner(migrated_database, INSERT_INVOICE, **_invoice(a, paid=30_000_000)))
    assert "ck_invoices_paid_minor" in error or "ck_invoices_status_paid" in error
    # A cancelled invoice frees the admission for its replacement, which needs a new number.
    await _owner(
        migrated_database,
        "UPDATE payments SET status = 'REVERSED', status_reason = 'Entered twice', "
        "closed_at = now(), closed_by_membership_id = :m WHERE id = :id",
        id=a.payment,
        m=a.membership,
    )
    await _owner(
        migrated_database,
        "UPDATE invoices SET status = 'CANCELLED', paid_minor = 0, status_reason = 'Wrong fee', "
        "cancelled_at = now(), cancelled_by_membership_id = :m WHERE id = :id",
        id=a.invoice,
        m=a.membership,
    )
    number = (
        await _owner(migrated_database, "SELECT number FROM invoices WHERE id = :id", id=a.invoice)
    )[0][0]
    assert "uq_invoices_tenant_id_number" in await _error(
        _owner(migrated_database, INSERT_INVOICE, **_invoice(a, number=number))
    )
    await _owner(migrated_database, INSERT_INVOICE, **_invoice(a))


async def test_payment_rules(migrated_database: DatabaseUnderTest, rows: tuple[Rows, Rows]) -> None:
    a, _ = rows
    pending = {"status": "PENDING", "confirmed_at": None, "confirmed_by": None}
    for change, constraint in (
        ({"amount": 0}, "ck_payments_amount_minor"),
        ({"method": "CARD"}, "ck_payments_method"),
        ({"method": "UPI"}, "ck_payments_reference"),
        ({"method": "UPI", "reference": "  "}, "ck_payments_reference"),
        ({**pending, "method": "UPI", "reference": "UTR1"}, "ck_payments_clearance_method"),
        ({**pending, "method": "CASH"}, "ck_payments_clearance_method"),
        ({"confirmed_at": None}, "ck_payments_confirmed"),
        ({"confirmed_by": None}, "ck_payments_confirmed"),
        (
            {"status": "REVERSED", "closed_at": NOW, "closed_by": a.membership},
            "ck_payments_status_reason",
        ),
        ({"status": "REVERSED", "reason": "Entered twice"}, "ck_payments_closed"),
        ({"key": None}, "null value"),
    ):
        assert constraint in await _error(
            _owner(migrated_database, INSERT_PAYMENT, **_payment(a, **change))
        ), change
    # A pending cheque and a failed demand draft are valid.
    await _owner(
        migrated_database,
        INSERT_PAYMENT,
        **_payment(a, **pending, method="CHEQUE", reference="Cheque 004512"),
    )
    await _owner(
        migrated_database,
        INSERT_PAYMENT,
        **_payment(
            a,
            status="FAILED",
            reason="Not honoured",
            confirmed_at=None,
            confirmed_by=None,
            closed_at=NOW,
            closed_by=a.membership,
            method="DEMAND_DRAFT",
            reference="DD 77881",
        ),
    )
    # One idempotency key per tenant and operation; one receipt per payment.
    key = uuid.uuid4()
    await _owner(migrated_database, INSERT_PAYMENT, **_payment(a, key=key))
    assert "uq_payments_tenant_id_idempotency_key" in await _error(
        _owner(migrated_database, INSERT_PAYMENT, **_payment(a, key=key))
    )
    assert "uq_receipts_tenant_id_payment_id" in await _error(
        _owner(
            migrated_database,
            "INSERT INTO receipts (id, tenant_id, number, payment_id, invoice_number, "
            "student_number, amount_minor, currency, method) VALUES (:id, :t, 'RCT-X', :pay, "
            "'INV-X', 'STU-X', 1, 'INR', 'CASH')",
            id=uuid.uuid7(),
            t=a.tenant,
            pay=a.payment,
        )
    )


async def test_finance_sequences_are_accepted(
    migrated_database: DatabaseUnderTest, rows: tuple[Rows, Rows]
) -> None:
    a, _ = rows
    for name in ("INVOICE", "RECEIPT"):
        await _owner(
            migrated_database,
            "INSERT INTO tenant_sequences (id, tenant_id, name, period, last_value) "
            "VALUES (:id, :t, :name, 2026, 1) ON CONFLICT DO NOTHING",
            id=uuid.uuid7(),
            t=a.tenant,
            name=name,
        )
    assert "ck_tenant_sequences_name" in await _error(
        _owner(
            migrated_database,
            "INSERT INTO tenant_sequences (id, tenant_id, name, period, last_value) "
            "VALUES (:id, :t, 'CREDIT_NOTE', 2026, 1)",
            id=uuid.uuid7(),
            t=a.tenant,
        )
    )


# --- Migration 0011 ------------------------------------------------------------------------


async def _system_roles(database: DatabaseUnderTest, tenant: uuid.UUID) -> dict[str, set[str]]:
    rows = await _owner(
        database,
        "SELECT r.template_code, array_agg(rp.permission_code) FROM roles r "
        "JOIN role_permissions rp ON rp.role_id = r.id "
        "WHERE r.tenant_id = :t AND r.is_system GROUP BY r.id, r.template_code",
        t=tenant,
    )
    return {template: set(codes) for template, codes in rows}


async def test_the_finance_migration_round_trips(
    migrated_database: DatabaseUnderTest, world: World, rows: tuple[Rows, Rows]
) -> None:
    a, _ = rows
    config = migrated_database.alembic_config()
    expected = {t.code.value: set(t.permissions) for t in system_role_templates()}
    tables = "SELECT count(*) FROM pg_class WHERE relname = ANY(:t) AND relkind = 'r'"
    key = (
        "SELECT count(*) FROM pg_constraint "
        "WHERE conname = 'uq_admissions_tenant_id_id_student_id_campus_id_course_id'"
    )
    await _owner(
        migrated_database,
        "INSERT INTO tenant_sequences (id, tenant_id, name, period, last_value) "
        "VALUES (:id, :t, 'RECEIPT', 2031, 4)",
        id=uuid.uuid7(),
        t=a.tenant,
    )
    # A finance role assignment that the downgrade must remove.
    officer = (
        await _owner(
            migrated_database,
            "SELECT id FROM roles WHERE tenant_id = :t AND template_code = 'FINANCE_OFFICER'",
            t=a.tenant,
        )
    )[0][0]
    await _owner(
        migrated_database,
        "INSERT INTO membership_roles (id, tenant_id, membership_id, role_id) "
        "VALUES (:id, :t, :m, :r)",
        id=uuid.uuid7(),
        t=a.tenant,
        m=a.membership,
        r=officer,
    )

    await anyio.to_thread.run_sync(command.downgrade, config, "0010")
    try:
        assert (await _owner(migrated_database, tables, t=list(TABLES)))[0][0] == 0
        assert (await _owner(migrated_database, key))[0][0] == 0
        left = await _owner(
            migrated_database,
            "SELECT (SELECT count(*) FROM permissions WHERE code = ANY(:c)) "
            "+ (SELECT count(*) FROM role_permissions WHERE permission_code = ANY(:c)) "
            "+ (SELECT count(*) FROM roles WHERE template_code LIKE 'FINANCE_%') "
            "+ (SELECT count(*) FROM tenant_sequences WHERE name IN ('INVOICE', 'RECEIPT'))",
            c=list(NEW_CODES),
        )
        assert left[0][0] == 0
        roles = await _system_roles(migrated_database, world.tenant_a)
        assert set(roles) == {"INSTITUTE_OWNER", "ADMIN", "ADMISSIONS_MANAGER", "COUNSELLOR"}
        assert not any(set(NEW_CODES) & codes for codes in roles.values())
        # The 0010 sequence names are back: INVOICE is refused again.
        assert "ck_tenant_sequences_name" in await _error(
            _owner(
                migrated_database,
                "INSERT INTO tenant_sequences (id, tenant_id, name, period, last_value) "
                "VALUES (:id, :t, 'INVOICE', 2026, 1)",
                id=uuid.uuid7(),
                t=a.tenant,
            )
        )
        # The T01 system-role protection is back in force after the downgrade.
        assert "system role" in await _error(
            _owner(
                migrated_database,
                "UPDATE roles SET description = 'x' WHERE id = :r",
                r=world.roles["admin_a"],
            )
        )
        # A custom role named like a new system role blocks the upgrade (no silent rename).
        clash = uuid.uuid7()
        await _owner(
            migrated_database,
            "INSERT INTO roles (id, tenant_id, name, is_system, version) "
            "VALUES (:id, :t, 'Finance Officer', false, 1)",
            id=clash,
            t=world.tenant_b,
        )
        with pytest.raises(RuntimeError, match="custom role named like a new system role"):
            await anyio.to_thread.run_sync(command.upgrade, config, "head")
        await _owner(migrated_database, "DELETE FROM roles WHERE id = :id", id=clash)
    finally:
        await anyio.to_thread.run_sync(command.upgrade, config, "head")

    assert (await _owner(migrated_database, tables, t=list(TABLES)))[0][0] == len(TABLES)
    assert (await _owner(migrated_database, key))[0][0] == 1
    for tenant in (world.tenant_a, world.tenant_b):
        assert await _system_roles(migrated_database, tenant) == expected
    unassigned = await _owner(
        migrated_database,
        "SELECT count(*) FROM membership_roles mr JOIN roles r ON r.id = mr.role_id "
        "WHERE r.template_code LIKE 'FINANCE_%'",
    )
    assert unassigned[0][0] == 0
    await anyio.to_thread.run_sync(command.check, config)
