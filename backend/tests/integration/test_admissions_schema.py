# SQL is assembled only from the constant table names below: S608 is a false positive.
# ruff: noqa: S608
"""Admissions core schema, Row-Level Security and migration 0010 (Phase 02-2; ADR-0021 §13).

Raw SQL through the real runtime roles and trusted ``SET LOCAL`` settings, so
only the database protects the rows:

* tenant isolation (RLS) on every new table;
* no DELETE for anyone at runtime; ``stored_files`` and
  ``application_activities`` are append-only; the read-only role reads none
  of the new tables (personal data and documents);
* composite foreign keys reject another tenant's course, campus, lead,
  application, stored file or student; a stored file's object key is bound
  to its own tenant and ID; one admission per application;
* migration 0010: down (tables, permissions, lead activity kind and role
  descriptions removed), up again; templates and clones agree.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
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
    "tenant_sequences",
    "stored_files",
    "applications",
    "application_documents",
    "application_activities",
    "students",
    "admissions",
)
APPEND_ONLY = ("stored_files", "application_activities")
NEW_CODES = (
    "application.read",
    "application.create",
    "application.update",
    "application.review",
    "document.read",
    "document.upload",
    "document.verify",
    "admission.approve",
    "student.read",
)
SHA = "0" * 64
NOW = datetime.now(UTC)


@dataclass
class Rows:
    tenant: uuid.UUID
    membership: uuid.UUID
    campus: uuid.UUID
    course: uuid.UUID
    lead: uuid.UUID
    application: uuid.UUID
    stored_file: uuid.UUID
    document: uuid.UUID
    student: uuid.UUID
    admission: uuid.UUID


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


INSERT_APPLICATION = (
    "INSERT INTO applications (id, tenant_id, number, lead_id, course_id, campus_id, "
    "owner_membership_id, created_by_membership_id, full_name, status, status_reason, "
    "submitted_at, version) VALUES (:id, :t, :number, :lead, :course, :campus, :m, :m, "
    "'Arjun Nair', :status, :reason, :submitted, 1)"
)
INSERT_FILE = (
    "INSERT INTO stored_files (id, tenant_id, object_key, file_name, content_type, size_bytes, "
    "sha256, uploaded_by_membership_id) VALUES (:id, :t, :key, 'passport.pdf', "
    "'application/pdf', 1024, :sha, :m)"
)
INSERT_DOCUMENT = (
    "INSERT INTO application_documents (id, tenant_id, application_id, stored_file_id, "
    "document_type, status, uploaded_by_membership_id, version) VALUES (:id, :t, :application, "
    ":file, 'PASSPORT', 'UPLOADED', :m, 1)"
)
INSERT_STUDENT = (
    "INSERT INTO students (id, tenant_id, student_number, home_campus_id, full_name, "
    "created_by_membership_id, version) VALUES (:id, :t, :number, :campus, 'Arjun Nair', :m, 1)"
)
INSERT_ADMISSION = (
    "INSERT INTO admissions (id, tenant_id, admission_number, application_id, student_id, "
    "course_id, campus_id, approved_by_membership_id, version) VALUES (:id, :t, :number, "
    ":application, :student, :course, :campus, :m, 1)"
)


async def _rows(database: DatabaseUnderTest, tenant: uuid.UUID, membership: uuid.UUID) -> Rows:
    """One row in every new table for ``tenant`` (as the owner: RLS does not apply)."""
    campus = (await _owner(database, "SELECT id FROM campuses WHERE tenant_id = :t", t=tenant))[0][
        0
    ]
    ids = {name: uuid.uuid7() for name in ("course", "lead", "app", "file", "doc", "stu", "adm")}
    suffix = ids["course"].hex[-6:].upper()
    await _owner(
        database,
        "INSERT INTO courses (id, tenant_id, code, name, category, status, version) "
        "VALUES (:id, :t, :code, 'GP Rating', 'PRE_SEA', 'ACTIVE', 1)",
        id=ids["course"],
        t=tenant,
        code=f"GPR{suffix}",
    )
    await _owner(
        database,
        "INSERT INTO leads (id, tenant_id, full_name, mobile, mobile_key, source, status, "
        "created_by_membership_id, version) VALUES (:id, :t, 'Arjun Nair', '+91 90000 10001', "
        "'9000010001', 'WALK_IN', 'APPLICATION', :m, 1)",
        id=ids["lead"],
        t=tenant,
        m=membership,
    )
    await _owner(
        database,
        INSERT_APPLICATION,
        id=ids["app"],
        t=tenant,
        number=f"APP-2026-{suffix}",
        lead=ids["lead"],
        course=ids["course"],
        campus=campus,
        m=membership,
        status="APPROVED",
        reason=None,
        submitted=NOW,
    )
    await _owner(
        database,
        INSERT_FILE,
        id=ids["file"],
        t=tenant,
        key=f"tenants/{tenant}/files/{ids['file']}",
        sha=SHA,
        m=membership,
    )
    await _owner(
        database,
        INSERT_DOCUMENT,
        id=ids["doc"],
        t=tenant,
        application=ids["app"],
        file=ids["file"],
        m=membership,
    )
    await _owner(
        database,
        "INSERT INTO application_activities (id, tenant_id, application_id, kind, details) "
        "VALUES (:id, :t, :a, 'CREATED', '{}')",
        id=uuid.uuid7(),
        t=tenant,
        a=ids["app"],
    )
    await _owner(
        database,
        INSERT_STUDENT,
        id=ids["stu"],
        t=tenant,
        number=f"STU-2026-{suffix}",
        campus=campus,
        m=membership,
    )
    await _owner(
        database,
        INSERT_ADMISSION,
        id=ids["adm"],
        t=tenant,
        number=f"ADM-2026-{suffix}",
        application=ids["app"],
        student=ids["stu"],
        course=ids["course"],
        campus=campus,
        m=membership,
    )
    await _owner(
        database,
        "INSERT INTO tenant_sequences (id, tenant_id, name, period, last_value) "
        "VALUES (:id, :t, 'ADMISSION', 2026, 1) ON CONFLICT DO NOTHING",
        id=uuid.uuid7(),
        t=tenant,
    )
    return Rows(
        tenant,
        membership,
        campus,
        ids["course"],
        ids["lead"],
        ids["app"],
        ids["file"],
        ids["doc"],
        ids["stu"],
        ids["adm"],
    )


@pytest.fixture
async def rows(migrated_database: DatabaseUnderTest, world: World) -> tuple[Rows, Rows]:
    a = await _rows(migrated_database, world.tenant_a, world.memberships["alice_a"])
    b = await _rows(migrated_database, world.tenant_b, world.memberships["carol_b"])
    return a, b


async def test_every_new_table_is_isolated_by_tenant(
    app_db: async_sessionmaker[AsyncSession], rows: tuple[Rows, Rows]
) -> None:
    a, b = rows
    for table in TABLES:
        seen = await _run(app_db, f"SELECT tenant_id FROM {table}", tenant=a.tenant)
        assert seen == {a.tenant}, table
        assert await _run(app_db, f"SELECT id FROM {table}", tenant=None) == set(), table
    # Writing a row for another tenant is refused by the policy's WITH CHECK.
    assert "row-level security" in await _error(
        _run(
            app_db,
            INSERT_STUDENT,
            tenant=a.tenant,
            id=uuid.uuid7(),
            t=b.tenant,
            number="STU-2026-99999",
            campus=b.campus,
            m=b.membership,
        )
    )
    # Updating another tenant's application matches nothing.
    moved = await _run(
        app_db,
        "UPDATE applications SET full_name = 'Changed' WHERE id = :id",
        tenant=a.tenant,
        id=b.application,
    )
    assert moved == 0


async def test_no_delete_and_append_only_tables(
    app_db: async_sessionmaker[AsyncSession], rows: tuple[Rows, Rows]
) -> None:
    a, _ = rows
    for table in TABLES:
        assert "permission denied" in await _error(
            _run(app_db, f"DELETE FROM {table}", tenant=a.tenant)
        ), table
    for table in APPEND_ONLY:
        assert "permission denied" in await _error(
            _run(app_db, f"UPDATE {table} SET created_at = now()", tenant=a.tenant)
        ), table


async def test_the_readonly_role_reads_none_of_the_new_tables(
    readonly_db: async_sessionmaker[AsyncSession], rows: tuple[Rows, Rows]
) -> None:
    a, _ = rows
    for table in TABLES:
        assert "permission denied" in await _error(
            _run(readonly_db, f"SELECT id FROM {table}", tenant=a.tenant)
        ), table


async def test_composite_keys_reject_another_tenants_rows(
    migrated_database: DatabaseUnderTest, rows: tuple[Rows, Rows]
) -> None:
    a, b = rows
    base = {"t": a.tenant, "m": a.membership, "status": "DRAFT", "reason": None, "submitted": None}
    for field, foreign in (("course", b.course), ("campus", b.campus), ("lead", b.lead)):
        values = {"course": a.course, "campus": a.campus, "lead": a.lead, field: foreign}
        assert "foreign key" in await _error(
            _owner(
                migrated_database,
                INSERT_APPLICATION,
                id=uuid.uuid7(),
                number=f"APP-X-{uuid.uuid7().hex[-8:]}",
                **base,
                **values,
            )
        ), field
    assert "foreign key" in await _error(
        _owner(
            migrated_database,
            INSERT_DOCUMENT,
            id=uuid.uuid7(),
            t=a.tenant,
            application=a.application,
            file=b.stored_file,
            m=a.membership,
        )
    )
    application = uuid.uuid7()
    await _owner(
        migrated_database,
        INSERT_APPLICATION,
        id=application,
        number=f"APP-Y-{application.hex[-8:]}",
        course=a.course,
        campus=a.campus,
        lead=None,
        **{**base, "status": "APPROVED", "submitted": NOW},
    )
    assert "foreign key" in await _error(
        _owner(
            migrated_database,
            INSERT_ADMISSION,
            id=uuid.uuid7(),
            t=a.tenant,
            number=f"ADM-Y-{application.hex[-8:]}",
            application=application,
            student=b.student,
            course=a.course,
            campus=a.campus,
            m=a.membership,
        )
    )


async def test_object_keys_are_bound_to_the_tenant_and_row(
    migrated_database: DatabaseUnderTest, rows: tuple[Rows, Rows]
) -> None:
    a, b = rows
    file_id = uuid.uuid7()
    for key in (
        f"tenants/{b.tenant}/files/{file_id}",  # another tenant's prefix
        f"tenants/{a.tenant}/files/{uuid.uuid7()}",  # another row's key
        f"tenants/{a.tenant}/files/../{file_id}",
        "public/passport.pdf",
    ):
        assert "ck_stored_files_object_key" in await _error(
            _owner(
                migrated_database,
                INSERT_FILE,
                id=file_id,
                t=a.tenant,
                key=key,
                sha=SHA,
                m=a.membership,
            )
        ), key
    assert "ck_stored_files_content_type" in await _error(
        _owner(
            migrated_database,
            INSERT_FILE.replace("'application/pdf'", "'text/html'"),
            id=file_id,
            t=a.tenant,
            key=f"tenants/{a.tenant}/files/{file_id}",
            sha=SHA,
            m=a.membership,
        )
    )


async def test_one_admission_per_application_and_status_rules(
    migrated_database: DatabaseUnderTest, rows: tuple[Rows, Rows]
) -> None:
    a, _ = rows
    assert "uq_admissions_tenant_id_application_id" in await _error(
        _owner(
            migrated_database,
            INSERT_ADMISSION,
            id=uuid.uuid7(),
            t=a.tenant,
            number=f"ADM-Z-{uuid.uuid7().hex[-8:]}",
            application=a.application,
            student=a.student,
            course=a.course,
            campus=a.campus,
            m=a.membership,
        )
    )
    base = {"t": a.tenant, "m": a.membership, "lead": None, "course": a.course, "campus": a.campus}
    for status, reason, submitted, constraint in (
        ("REJECTED", None, NOW, "ck_applications_status_reason"),
        ("SUBMITTED", None, None, "ck_applications_submitted_at"),
        ("WITHDRAWN", None, NOW, "ck_applications_status"),
    ):
        assert constraint in await _error(
            _owner(
                migrated_database,
                INSERT_APPLICATION,
                id=uuid.uuid7(),
                number=f"APP-Z-{uuid.uuid7().hex[-8:]}",
                status=status,
                reason=reason,
                submitted=submitted,
                **base,
            )
        ), status
    # A document replaced twice, or rejected without a reason, is refused.
    assert "ck_application_documents_rejection_reason" in await _error(
        _owner(
            migrated_database,
            "UPDATE application_documents SET status = 'REJECTED', reviewed_at = now(), "
            "reviewed_by_membership_id = :m WHERE id = :id",
            id=a.document,
            m=a.membership,
        )
    )


# --- Migration 0010 ------------------------------------------------------------------------


async def _system_roles(database: DatabaseUnderTest, tenant: uuid.UUID) -> dict[str, set[str]]:
    rows = await _owner(
        database,
        "SELECT r.template_code, array_agg(rp.permission_code) FROM roles r "
        "JOIN role_permissions rp ON rp.role_id = r.id "
        "WHERE r.tenant_id = :t AND r.is_system GROUP BY r.id, r.template_code",
        t=tenant,
    )
    return {template: set(codes) for template, codes in rows}


async def test_the_admissions_migration_round_trips(
    migrated_database: DatabaseUnderTest, world: World, rows: tuple[Rows, Rows]
) -> None:
    a, _ = rows
    config = migrated_database.alembic_config()
    expected = {t.code.value: set(t.permissions) for t in system_role_templates()}
    descriptions = {t.code.value: t.description for t in system_role_templates()}
    await _owner(
        migrated_database,
        "INSERT INTO lead_activities (id, tenant_id, lead_id, kind, details) "
        "VALUES (:id, :t, :l, 'APPLICATION_STARTED', '{}')",
        id=uuid.uuid7(),
        t=a.tenant,
        l=a.lead,
    )
    tables = "SELECT count(*) FROM pg_class WHERE relname = ANY(:t) AND relkind = 'r'"

    await anyio.to_thread.run_sync(command.downgrade, config, "0009")
    try:
        assert (await _owner(migrated_database, tables, t=list(TABLES)))[0][0] == 0
        left = await _owner(
            migrated_database,
            "SELECT (SELECT count(*) FROM permissions WHERE code = ANY(:c)) "
            "+ (SELECT count(*) FROM role_permissions WHERE permission_code = ANY(:c)) "
            "+ (SELECT count(*) FROM lead_activities WHERE kind = 'APPLICATION_STARTED')",
            c=list(NEW_CODES),
        )
        assert left[0][0] == 0
        roles = await _system_roles(migrated_database, world.tenant_a)
        assert set(roles) == set(expected)
        assert not any(set(NEW_CODES) & codes for codes in roles.values())
        counsellor = await _owner(
            migrated_database,
            "SELECT DISTINCT description FROM roles WHERE template_code = 'COUNSELLOR'",
        )
        assert [row[0] for row in counsellor] == [
            "Works enquiries: adds and updates leads, notes and follow-ups; reads the catalogue."
        ]
        # The 0009 lead activity kinds are back: APPLICATION_STARTED is refused again.
        assert "ck_lead_activities_kind" in await _error(
            _owner(
                migrated_database,
                "INSERT INTO lead_activities (id, tenant_id, lead_id, kind, details) "
                "VALUES (:id, :t, :l, 'APPLICATION_STARTED', '{}')",
                id=uuid.uuid7(),
                t=a.tenant,
                l=a.lead,
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
    finally:
        await anyio.to_thread.run_sync(command.upgrade, config, "head")

    assert (await _owner(migrated_database, tables, t=list(TABLES)))[0][0] == len(TABLES)
    for tenant in (world.tenant_a, world.tenant_b):
        assert await _system_roles(migrated_database, tenant) == expected
    current = await _owner(
        migrated_database,
        "SELECT DISTINCT template_code, description FROM roles "
        "WHERE template_code IN ('ADMISSIONS_MANAGER', 'COUNSELLOR')",
    )
    assert {row[0]: row[1] for row in current} == {
        code: descriptions[code] for code in ("ADMISSIONS_MANAGER", "COUNSELLOR")
    }
    await anyio.to_thread.run_sync(command.check, config)
