# SQL is assembled only from the constant table names below: S608 is a false positive.
# ruff: noqa: S608
"""Batch schema, Row-Level Security and migration 0014 (Phase 02-6).

Raw SQL through the real runtime roles, so only the database protects rows —
the application's checks are bypassed on purpose:

* tenant isolation (RLS) on every batch table; no DELETE for anyone at
  runtime; ``batch_activities`` is insert-only; the read-only role reads
  ``batches`` only;
* composite keys: an allocation's admission, student, course and campus are
  one admission's, and its batch, course and campus one batch's;
* one ACTIVE allocation per admission; capacity, dates and status rules;
* the seat-count trigger: allocation only into an OPEN batch, never beyond
  capacity, ended allocations decrement and are immutable;
* ``admissions.status`` accepts ENROLLED;
* migration 0014: down (tables, function, permissions removed; ENROLLED back
  to ADMITTED), up again; ``alembic check`` clean.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date
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

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

TABLES = ("batches", "batch_allocations", "batch_activities")
CODES = ("batch.read", "batch.manage", "batch.allocate")


@dataclass
class Rows:
    tenant: uuid.UUID
    membership: uuid.UUID
    campus: uuid.UUID
    other_campus: uuid.UUID
    course: uuid.UUID
    other_course: uuid.UUID
    student: uuid.UUID
    admission: uuid.UUID
    second_student: uuid.UUID
    second_admission: uuid.UUID
    batch: uuid.UUID
    allocation: uuid.UUID


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


INSERT_BATCH = (
    "INSERT INTO batches (id, tenant_id, course_id, campus_id, code, name, start_date, end_date, "
    "capacity, status, created_by_membership_id, version) VALUES (:id, :t, :course, :campus, "
    ":code, 'DNS Batch', :start, :end, :capacity, :status, :m, 1)"
)
INSERT_ALLOCATION = (
    "INSERT INTO batch_allocations (id, tenant_id, batch_id, course_id, campus_id, admission_id, "
    "student_id, status, payment_basis, override_reason, override_invoice_state, "
    "allocated_by_membership_id, version) VALUES (:id, :t, :batch, :course, :campus, "
    ":admission, :student, 'ACTIVE', :basis, :reason, :state, :m, 1)"
)


def _batch(rows: Rows, **changes: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "id": uuid.uuid7(),
        "t": rows.tenant,
        "course": rows.course,
        "campus": rows.campus,
        "code": f"B-{uuid.uuid7().hex[-8:].upper()}",
        "start": date(2026, 7, 1),
        "end": date(2027, 6, 30),
        "capacity": 2,
        "status": "OPEN",
        "m": rows.membership,
    }
    return {**values, **changes}


def _allocation(rows: Rows, **changes: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "id": uuid.uuid7(),
        "t": rows.tenant,
        "batch": rows.batch,
        "course": rows.course,
        "campus": rows.campus,
        "admission": rows.second_admission,
        "student": rows.second_student,
        "basis": "OVERRIDE",
        "reason": "Sponsor pays",
        "state": "NO_INVOICE",
        "m": rows.membership,
    }
    return {**values, **changes}


async def _admitted(
    database: DatabaseUnderTest,
    tenant: uuid.UUID,
    membership: uuid.UUID,
    course: uuid.UUID,
    campus: uuid.UUID,
) -> tuple[uuid.UUID, uuid.UUID]:
    app, student, admission = uuid.uuid7(), uuid.uuid7(), uuid.uuid7()
    suffix = admission.hex[-8:].upper()
    await _owner(
        database,
        "INSERT INTO applications (id, tenant_id, number, course_id, campus_id, "
        "owner_membership_id, created_by_membership_id, full_name, status, submitted_at, "
        "version) VALUES (:id, :t, :number, :course, :campus, :m, :m, 'Kavya Menon', "
        "'ADMITTED', now(), 1)",
        id=app,
        t=tenant,
        number=f"APP-{suffix}",
        course=course,
        campus=campus,
        m=membership,
    )
    await _owner(
        database,
        "INSERT INTO students (id, tenant_id, student_number, home_campus_id, full_name, "
        "created_by_membership_id, version) VALUES (:id, :t, :number, :campus, 'Kavya Menon', "
        ":m, 1)",
        id=student,
        t=tenant,
        number=f"STU-{suffix}",
        campus=campus,
        m=membership,
    )
    await _owner(
        database,
        "INSERT INTO admissions (id, tenant_id, admission_number, application_id, student_id, "
        "course_id, campus_id, approved_by_membership_id, version) VALUES (:id, :t, :number, "
        ":app, :stu, :course, :campus, :m, 1)",
        id=admission,
        t=tenant,
        number=f"ADM-{suffix}",
        app=app,
        stu=student,
        course=course,
        campus=campus,
        m=membership,
    )
    return student, admission


async def _rows(
    database: DatabaseUnderTest, world: World, tenant: uuid.UUID, membership: uuid.UUID
) -> Rows:
    campuses = [
        row[0]
        for row in await _owner(
            database, "SELECT id FROM campuses WHERE tenant_id = :t ORDER BY code", t=tenant
        )
    ]
    campus = campuses[0]
    other_campus = campuses[-1]
    courses = []
    for code in ("DNS", "GME"):
        course = uuid.uuid7()
        await _owner(
            database,
            "INSERT INTO courses (id, tenant_id, code, name, category, status, version) "
            "VALUES (:id, :t, :code, 'Course', 'PRE_SEA', 'ACTIVE', 1)",
            id=course,
            t=tenant,
            code=f"{code}{course.hex[-6:].upper()}",
        )
        courses.append(course)
    student, admission = await _admitted(database, tenant, membership, courses[0], campus)
    second_student, second_admission = await _admitted(
        database, tenant, membership, courses[0], campus
    )
    rows = Rows(
        tenant,
        membership,
        campus,
        other_campus,
        courses[0],
        courses[1],
        student,
        admission,
        second_student,
        second_admission,
        uuid.uuid7(),
        uuid.uuid7(),
    )
    await _owner(database, INSERT_BATCH, **_batch(rows, id=rows.batch))
    await _owner(
        database,
        INSERT_ALLOCATION,
        **_allocation(rows, id=rows.allocation, admission=admission, student=student),
    )
    await _owner(
        database,
        "UPDATE admissions SET status = 'ENROLLED' WHERE id = :id",
        id=admission,
    )
    await _owner(
        database,
        "INSERT INTO batch_activities (id, tenant_id, batch_id, allocation_id, kind, details) "
        "VALUES (:id, :t, :b, :a, 'ALLOCATED', '{}')",
        id=uuid.uuid7(),
        t=tenant,
        b=rows.batch,
        a=rows.allocation,
    )
    return rows


@pytest.fixture
async def rows(migrated_database: DatabaseUnderTest, world: World) -> tuple[Rows, Rows]:
    a = await _rows(migrated_database, world, world.tenant_a, world.memberships["alice_a"])
    b = await _rows(migrated_database, world, world.tenant_b, world.memberships["carol_b"])
    return a, b


async def test_every_batch_table_is_isolated_by_tenant(
    app_db: async_sessionmaker[AsyncSession], rows: tuple[Rows, Rows]
) -> None:
    a, b = rows
    for table in TABLES:
        seen = await _run(app_db, f"SELECT tenant_id FROM {table}", tenant=a.tenant)
        assert seen == {a.tenant}, table
        assert await _run(app_db, f"SELECT id FROM {table}", tenant=None) == set(), table
    # A's context cannot change or point at B's rows.
    assert (
        await _run(
            app_db,
            "UPDATE batches SET name = 'Taken' WHERE id = :id",
            tenant=a.tenant,
            id=b.batch,
        )
        == 0
    )
    message = await _error(
        _run(app_db, INSERT_ALLOCATION, tenant=a.tenant, **_allocation(b, t=a.tenant))
    )
    assert message  # B's batch and admission are invisible to A's composite keys


async def test_no_delete_and_insert_only_activity(
    app_db: async_sessionmaker[AsyncSession], rows: tuple[Rows, Rows]
) -> None:
    a, _ = rows
    for table in TABLES:
        message = await _error(_run(app_db, f"DELETE FROM {table}", tenant=a.tenant))
        assert "permission denied" in message, table
    message = await _error(
        _run(app_db, "UPDATE batch_activities SET kind = 'CREATED'", tenant=a.tenant)
    )
    assert "permission denied" in message


async def test_the_readonly_role_reads_batches_only(
    readonly_db: async_sessionmaker[AsyncSession], rows: tuple[Rows, Rows]
) -> None:
    a, _ = rows
    assert await _run(readonly_db, "SELECT tenant_id FROM batches", tenant=a.tenant) == {a.tenant}
    for table in ("batch_allocations", "batch_activities"):
        message = await _error(_run(readonly_db, f"SELECT id FROM {table}", tenant=a.tenant))
        assert "permission denied" in message, table


async def test_composite_keys_bind_an_allocation_to_one_admission_and_batch(
    app_db: async_sessionmaker[AsyncSession], rows: tuple[Rows, Rows]
) -> None:
    a, _ = rows
    other_batch = uuid.uuid7()
    await _run(
        app_db,
        INSERT_BATCH,
        tenant=a.tenant,
        **_batch(a, id=other_batch, course=a.other_course),
    )
    for changes in (
        {"course": a.other_course},  # the admission's course is another
        {"campus": a.other_campus},  # campus differs from the batch's and admission's
        {"student": a.student},  # another admission's student
        {"batch": other_batch, "course": a.other_course},  # a batch of another course
    ):
        message = await _error(
            _run(app_db, INSERT_ALLOCATION, tenant=a.tenant, **_allocation(a, **changes))
        )
        assert "foreign key" in message, changes


async def test_one_active_allocation_per_admission_and_row_rules(
    app_db: async_sessionmaker[AsyncSession], rows: tuple[Rows, Rows]
) -> None:
    a, _ = rows
    second = uuid.uuid7()
    await _run(app_db, INSERT_BATCH, tenant=a.tenant, **_batch(a, id=second))
    message = await _error(
        _run(
            app_db,
            INSERT_ALLOCATION,
            tenant=a.tenant,
            **_allocation(a, batch=second, admission=a.admission, student=a.student),
        )
    )
    assert "uq_batch_allocations_tenant_id_admission_id_active" in message
    for changes in (
        {"basis": "OVERRIDE", "reason": None},  # an override needs its reason
        {"basis": "PAID", "reason": "x"},  # reasons only with an override
        {"basis": "OVERRIDE", "state": "PAID"},  # a paid invoice is never overridden
        {"basis": "TRANSFER", "reason": None, "state": None},  # a transfer names its source
    ):
        message = await _error(
            _run(app_db, INSERT_ALLOCATION, tenant=a.tenant, **_allocation(a, **changes))
        )
        assert "check constraint" in message, changes
    for bad_batch in (
        {"capacity": 0},
        {"capacity": 501},
        {"end": date(2026, 6, 30)},
        {"code": "lower-case"},
        {"status": "FULL"},
    ):
        message = await _error(
            _run(app_db, INSERT_BATCH, tenant=a.tenant, **_batch(a, **bad_batch))
        )
        assert "check constraint" in message, bad_batch
    message = await _error(_run(app_db, INSERT_BATCH, tenant=a.tenant, **_batch(a, code=None)))
    assert "null" in message
    # Codes are unique per institute.
    code = f"DUP-{uuid.uuid7().hex[-6:].upper()}"
    await _run(app_db, INSERT_BATCH, tenant=a.tenant, **_batch(a, code=code))
    message = await _error(_run(app_db, INSERT_BATCH, tenant=a.tenant, **_batch(a, code=code)))
    assert "uq_batches_tenant_id_code" in message


async def test_the_seat_count_trigger_enforces_open_and_capacity(
    app_db: async_sessionmaker[AsyncSession], rows: tuple[Rows, Rows]
) -> None:
    a, _ = rows
    count = "SELECT allocated_count FROM batches WHERE id = :id"
    assert await _run(app_db, count, tenant=a.tenant, id=a.batch) == {1}
    # Capacity cannot be reduced below the active allocations.
    message = await _error(
        _run(app_db, "UPDATE batches SET capacity = 0 WHERE id = :id", tenant=a.tenant, id=a.batch)
    )
    assert "check constraint" in message
    # A closed batch takes nobody.
    await _run(
        app_db, "UPDATE batches SET status = 'CLOSED' WHERE id = :id", tenant=a.tenant, id=a.batch
    )
    message = await _error(_run(app_db, INSERT_ALLOCATION, tenant=a.tenant, **_allocation(a)))
    assert "open batch" in message
    # An empty batch cannot be cancelled with allocations.
    message = await _error(
        _run(
            app_db,
            "UPDATE batches SET status = 'CANCELLED' WHERE id = :id",
            tenant=a.tenant,
            id=a.batch,
        )
    )
    assert "check constraint" in message
    await _run(
        app_db, "UPDATE batches SET status = 'OPEN' WHERE id = :id", tenant=a.tenant, id=a.batch
    )
    # Over capacity: a one-seat batch with its seat taken refuses a second allocation.
    full = uuid.uuid7()
    await _run(app_db, INSERT_BATCH, tenant=a.tenant, **_batch(a, id=full, capacity=1))
    await _run(app_db, INSERT_ALLOCATION, tenant=a.tenant, **_allocation(a, batch=full))
    assert await _run(app_db, count, tenant=a.tenant, id=full) == {1}
    # Ending an allocation frees the seat; an ended allocation is immutable.
    await _run(
        app_db,
        "UPDATE batch_allocations SET status = 'ENDED', end_reason = 'WITHDRAWN', "
        "end_note = 'Left', ended_at = now(), ended_by_membership_id = :m WHERE batch_id = :b",
        tenant=a.tenant,
        m=a.membership,
        b=full,
    )
    assert await _run(app_db, count, tenant=a.tenant, id=full) == {0}
    message = await _error(
        _run(
            app_db,
            "UPDATE batch_allocations SET status = 'ACTIVE', end_reason = NULL, end_note = NULL, "
            "ended_at = NULL, ended_by_membership_id = NULL WHERE batch_id = :b",
            tenant=a.tenant,
            b=full,
        )
    )
    assert "history cannot be changed" in message
    message = await _error(
        _run(
            app_db,
            "UPDATE batch_allocations SET batch_id = :other WHERE id = :id",
            tenant=a.tenant,
            other=full,
            id=a.allocation,
        )
    )
    assert "history cannot be changed" in message


async def test_capacity_is_enforced_by_the_database_alone(
    migrated_database: DatabaseUnderTest,
    app_db: async_sessionmaker[AsyncSession],
    rows: tuple[Rows, Rows],
) -> None:
    a, _ = rows
    full = uuid.uuid7()
    await _run(app_db, INSERT_BATCH, tenant=a.tenant, **_batch(a, id=full, capacity=1))
    third_student, third_admission = await _admitted(
        migrated_database, a.tenant, a.membership, a.course, a.campus
    )
    await _run(app_db, INSERT_ALLOCATION, tenant=a.tenant, **_allocation(a, batch=full))
    message = await _error(
        _run(
            app_db,
            INSERT_ALLOCATION,
            tenant=a.tenant,
            **_allocation(a, batch=full, admission=third_admission, student=third_student),
        )
    )
    assert "ck_batches_allocated_count" in message


async def test_the_batches_migration_round_trips(
    migrated_database: DatabaseUnderTest, rows: tuple[Rows, Rows]
) -> None:
    a, _ = rows
    config = migrated_database.alembic_config()
    await anyio.to_thread.run_sync(command.downgrade, config, "0013")
    try:
        tables = await _owner(
            migrated_database,
            "SELECT count(*) FROM pg_class WHERE relname = ANY(:t) AND relkind = 'r'",
            t=list(TABLES),
        )
        assert tables[0][0] == 0
        assert (
            await _owner(
                migrated_database,
                "SELECT count(*) FROM pg_proc WHERE proname = 'batch_allocations_count'",
            )
        )[0][0] == 0
        assert (
            await _owner(
                migrated_database,
                "SELECT count(*) FROM permissions WHERE code = ANY(:c)",
                c=list(CODES),
            )
        )[0][0] == 0
        assert (
            await _owner(
                migrated_database,
                "SELECT count(*) FROM role_permissions WHERE permission_code = ANY(:c)",
                c=list(CODES),
            )
        )[0][0] == 0
        status = await _owner(
            migrated_database, "SELECT status FROM admissions WHERE id = :id", id=a.admission
        )
        assert status[0][0] == "ADMITTED"  # the downgrade returns ENROLLED to ADMITTED
    finally:
        await anyio.to_thread.run_sync(command.upgrade, config, "head")
    # Upgraded again: permissions granted to every tenant's system roles, nobody assigned.
    granted = await _owner(
        migrated_database,
        "SELECT r.template_code, array_agg(rp.permission_code ORDER BY 1) FROM roles r "
        "JOIN role_permissions rp ON rp.role_id = r.id WHERE r.tenant_id = :t "
        "AND rp.permission_code = ANY(:c) GROUP BY r.template_code",
        t=a.tenant,
        c=list(CODES),
    )
    by_template = {row[0]: set(row[1]) for row in granted}
    assert by_template == {
        "INSTITUTE_OWNER": set(CODES),
        "ADMIN": set(CODES),
        "ADMISSIONS_MANAGER": set(CODES),
        "COUNSELLOR": {"batch.read"},
        "FINANCE_MANAGER": {"batch.read"},
        "FINANCE_OFFICER": {"batch.read"},
    }
    await anyio.to_thread.run_sync(command.check, config)
