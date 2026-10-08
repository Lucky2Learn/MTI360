# SQL is assembled only from the constant table names below: S608 is a false positive.
# ruff: noqa: S608
"""Courses and leads schema, Row-Level Security and migration 0009 (Phase 02-1).

Raw SQL through the real runtime roles and trusted ``SET LOCAL`` settings, so
only the database protects the rows:

* tenant isolation (RLS) on every new table, also for the read-only role;
* no DELETE for anyone at runtime; ``lead_activities`` is append-only; the
  read-only role reads courses and nothing of the lead tables;
* composite foreign keys reject another tenant's course, campus, membership
  or lead;
* migration 0009: down, refusal on a role-name clash, up again; existing
  tenants have exactly the four system roles with their template permissions.
"""

import uuid
from collections.abc import AsyncIterator
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

TABLES = ("courses", "leads", "lead_follow_ups", "lead_activities")
NEW_CODES = (
    "course.read",
    "course.manage",
    "lead.read",
    "lead.create",
    "lead.update",
    "lead.assign",
)
INSERT_COURSE = (
    "INSERT INTO courses (id, tenant_id, code, name, category, version) "
    "VALUES (:id, :row_tenant, :code, 'GP Rating', 'PRE_SEA', 1)"
)
INSERT_LEAD = (
    "INSERT INTO leads (id, tenant_id, full_name, mobile, mobile_key, source, "
    "created_by_membership_id, interested_course_id, campus_id, owner_membership_id, "
    "duplicate_of_lead_id, status, version) VALUES (:id, :row_tenant, 'Arjun Nair', "
    "'+91 90000 10001', '9000010001', 'WALK_IN', :creator, :course, :campus, :owner, "
    ":duplicate, :status, 1)"
)


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


async def _run(
    factory: async_sessionmaker[AsyncSession],
    sql: str,
    *,
    tenant: uuid.UUID | None,
    realm: Realm = Realm.TENANT,
    **params: Any,
) -> Any:
    context = RequestContext(realm=realm, request_id=uuid.uuid7(), tenant_id=tenant)
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


async def _owner(database: DatabaseUnderTest, sql: str, **params: Any) -> list[Any]:
    engine = create_async_engine(database.owner_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            result = await connection.execute(text(sql), params)
            return list(result.all()) if result.returns_rows else []
    finally:
        await engine.dispose()


async def _course(factory: async_sessionmaker[AsyncSession], tenant: uuid.UUID) -> uuid.UUID:
    course_id = uuid.uuid7()
    code = f"C{course_id.hex[-8:]}".upper()
    await _run(factory, INSERT_COURSE, tenant=tenant, row_tenant=tenant, id=course_id, code=code)
    return course_id


async def _lead(
    factory: async_sessionmaker[AsyncSession], tenant: uuid.UUID, creator: uuid.UUID, **refs: Any
) -> uuid.UUID:
    lead_id = uuid.uuid7()
    values = {"course": None, "campus": None, "owner": None, "duplicate": None, "status": "NEW"}
    await _run(
        factory,
        INSERT_LEAD,
        tenant=tenant,
        row_tenant=tenant,
        id=lead_id,
        creator=creator,
        **(values | refs),
    )
    return lead_id


# --- Row-Level Security --------------------------------------------------------------------


async def test_every_new_table_is_isolated_by_tenant(
    app_db: async_sessionmaker[AsyncSession],
    readonly_db: async_sessionmaker[AsyncSession],
    world: World,
) -> None:
    a, b = world.tenant_a, world.tenant_b
    creator_a = world.memberships["alice_a"]
    course_a = await _course(app_db, a)
    lead_a = await _lead(app_db, a, creator_a, course=course_a)
    await _run(
        app_db,
        "INSERT INTO lead_activities (id, tenant_id, lead_id, kind) "
        "VALUES (:id, :t, :l, 'CREATED')",
        tenant=a,
        id=uuid.uuid7(),
        t=a,
        l=lead_a,
    )
    await _run(
        app_db,
        "INSERT INTO lead_follow_ups (id, tenant_id, lead_id, assignee_membership_id, due_at, "
        "kind, created_by_membership_id, version) VALUES (:id, :t, :l, :m, now(), 'CALL', :m, 1)",
        tenant=a,
        id=uuid.uuid7(),
        t=a,
        l=lead_a,
        m=creator_a,
    )
    for table in TABLES:
        own = f"SELECT count(*) FROM {table} WHERE tenant_id = :t"
        assert await _run(app_db, own, tenant=a, t=a) != {0}, table
        assert await _run(app_db, own, tenant=b, t=a) == {0}, table  # B sees none of A's rows
        assert await _run(app_db, f"SELECT count(*) FROM {table}", tenant=None) == {0}, table
    # Writes for another tenant are refused; updates of another tenant's rows match nothing.
    refused = await _error(
        _run(app_db, INSERT_COURSE, tenant=b, row_tenant=a, id=uuid.uuid7(), code="GPR")
    )
    assert "row-level security" in refused
    assert (
        await _run(app_db, "UPDATE courses SET name = 'x' WHERE id = :c", tenant=b, c=course_a) == 0
    )
    assert await _run(app_db, "UPDATE leads SET city = 'x' WHERE id = :l", tenant=b, l=lead_a) == 0
    # The read-only role reads courses of the trusted tenant only.
    assert course_a in await _run(readonly_db, "SELECT id FROM courses", tenant=a)
    assert course_a not in await _run(readonly_db, "SELECT id FROM courses", tenant=b)


async def test_runtime_privileges(migrated_database: DatabaseUnderTest) -> None:
    roles = migrated_database.roles
    checks = {
        (roles["app"], table, privilege): expected
        for table in TABLES
        for privilege, expected in (
            ("SELECT", True),
            ("INSERT", True),
            ("UPDATE", table != "lead_activities"),
            ("DELETE", False),
            ("TRUNCATE", False),
        )
    } | {
        (roles["readonly"], table, privilege): table == "courses" and privilege == "SELECT"
        for table in TABLES
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE")
    }
    for (role, table, privilege), expected in checks.items():
        rows = await _owner(
            migrated_database,
            "SELECT has_table_privilege(:r, :t, :p)",
            r=role,
            t=table,
            p=privilege,
        )
        assert rows[0][0] is expected, (role, table, privilege)
    policies = await _owner(
        migrated_database,
        "SELECT tablename, policyname FROM pg_policies WHERE tablename = ANY(:t)",
        t=list(TABLES),
    )
    assert {tuple(row) for row in policies} == {
        ("courses", "courses_tenant_isolation"),
        ("courses", "courses_readonly_tenant_read"),
        ("leads", "leads_tenant_isolation"),
        ("lead_follow_ups", "lead_follow_ups_tenant_isolation"),
        ("lead_activities", "lead_activities_tenant_read"),
        ("lead_activities", "lead_activities_tenant_insert"),
    }
    secured = await _owner(
        migrated_database,
        "SELECT count(*) FROM pg_class WHERE relname = ANY(:t) AND relrowsecurity",
        t=list(TABLES),
    )
    assert secured[0][0] == len(TABLES)


async def test_composite_foreign_keys_reject_another_tenants_references(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    a, b = world.tenant_a, world.tenant_b
    creator_a, member_b = world.memberships["alice_a"], world.memberships["carol_b"]
    course_b = await _course(app_db, b)
    lead_b = await _lead(app_db, b, member_b)
    for refs in (
        {"course": course_b},
        {"campus": world.campus_b1},
        {"owner": member_b},
        {"duplicate": lead_b, "status": "DUPLICATE"},
    ):
        message = await _error(_lead(app_db, a, creator_a, **refs))
        assert "foreign key" in message, refs
    assert "foreign key" in await _error(_lead(app_db, a, member_b))  # creator of tenant B


async def test_check_constraints_keep_leads_consistent(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    a, creator = world.tenant_a, world.memberships["alice_a"]
    original = await _lead(app_db, a, creator)
    no_contact = (
        "INSERT INTO leads (id, tenant_id, full_name, source, created_by_membership_id, version) "
        "VALUES (:id, :t, 'Arjun Nair', 'WALK_IN', :c, 1)"
    )
    assert "ck_leads_contact" in await _error(
        _run(app_db, no_contact, tenant=a, id=uuid.uuid7(), t=a, c=creator)
    )
    assert "ck_leads_status_reason" in await _error(_lead(app_db, a, creator, status="LOST"))
    assert "ck_leads_duplicate_of" in await _error(_lead(app_db, a, creator, status="DUPLICATE"))
    assert "ck_leads_duplicate_of" in await _error(_lead(app_db, a, creator, duplicate=original))
    assert "ck_leads_status" in await _error(_lead(app_db, a, creator, status="ENROLLED"))
    # 02-2 states already exist.
    await _lead(app_db, a, creator, status="APPLICATION")
    note = (
        "INSERT INTO lead_activities (id, tenant_id, lead_id, kind, body) "
        "VALUES (:id, :t, :l, :k, :b)"
    )
    assert "ck_lead_activities_body_note_only" in await _error(
        _run(app_db, note, tenant=a, id=uuid.uuid7(), t=a, l=original, k="NOTE", b=None)
    )
    assert "ck_lead_activities_body_note_only" in await _error(
        _run(app_db, note, tenant=a, id=uuid.uuid7(), t=a, l=original, k="CREATED", b="x")
    )


# --- Migration 0009 ------------------------------------------------------------------------


async def _system_roles(database: DatabaseUnderTest, tenant: uuid.UUID) -> dict[str, set[str]]:
    rows = await _owner(
        database,
        "SELECT r.template_code, array_agg(rp.permission_code) FROM roles r "
        "JOIN role_permissions rp ON rp.role_id = r.id "
        "WHERE r.tenant_id = :t AND r.is_system GROUP BY r.id, r.template_code",
        t=tenant,
    )
    found: dict[str, set[str]] = {}
    for template, codes in rows:
        assert template not in found, f"duplicate system role {template}"
        found[template] = set(codes)
    return found


async def test_the_courses_leads_migration_round_trips(
    migrated_database: DatabaseUnderTest, app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    config = migrated_database.alembic_config()
    expected = {t.code.value: set(t.permissions) for t in system_role_templates()}
    assert await _system_roles(migrated_database, world.tenant_a) == expected
    # A counsellor assignment and some business rows that the downgrade must remove.
    counsellor = (
        await _owner(
            migrated_database,
            "SELECT id FROM roles WHERE tenant_id = :t AND template_code = 'COUNSELLOR'",
            t=world.tenant_a,
        )
    )[0][0]
    await _owner(
        migrated_database,
        "INSERT INTO membership_roles (id, tenant_id, membership_id, role_id) "
        "VALUES (:id, :t, :m, :r)",
        id=uuid.uuid7(),
        t=world.tenant_a,
        m=world.memberships["dave_a"],
        r=counsellor,
    )
    await _lead(app_db, world.tenant_a, world.memberships["alice_a"])
    tables = "SELECT count(*) FROM pg_class WHERE relname = ANY(:t) AND relkind = 'r'"

    await anyio.to_thread.run_sync(command.downgrade, config, "0008")
    try:
        assert (await _owner(migrated_database, tables, t=list(TABLES)))[0][0] == 0
        left = await _owner(
            migrated_database,
            "SELECT (SELECT count(*) FROM permissions WHERE code = ANY(:c)) "
            "+ (SELECT count(*) FROM role_permissions WHERE permission_code = ANY(:c)) "
            "+ (SELECT count(*) FROM roles "
            "   WHERE template_code IN ('ADMISSIONS_MANAGER', 'COUNSELLOR'))",
            c=list(NEW_CODES),
        )
        assert left[0][0] == 0
        before = await _system_roles(migrated_database, world.tenant_a)
        assert set(before) == {"INSTITUTE_OWNER", "ADMIN"}
        assert not before["INSTITUTE_OWNER"] & set(NEW_CODES)
        # The T01 system-role protection is back in force after the downgrade.
        assert "system role" in await _error(
            _owner(
                migrated_database,
                "DELETE FROM role_permissions WHERE role_id = :r",
                r=world.roles["admin_a"],
            )
        )
        # A custom role named like a new system role blocks the upgrade (no silent rename).
        clash = uuid.uuid7()
        await _owner(
            migrated_database,
            "INSERT INTO roles (id, tenant_id, name, is_system, version) "
            "VALUES (:id, :t, 'counsellor', false, 1)",
            id=clash,
            t=world.tenant_b,
        )
        with pytest.raises(RuntimeError, match="custom role named like a new system role"):
            await anyio.to_thread.run_sync(command.upgrade, config, "head")
        await _owner(migrated_database, "DELETE FROM roles WHERE id = :id", id=clash)
    finally:
        await anyio.to_thread.run_sync(command.upgrade, config, "head")

    assert (await _owner(migrated_database, tables, t=list(TABLES)))[0][0] == len(TABLES)
    for tenant in (world.tenant_a, world.tenant_b):
        assert await _system_roles(migrated_database, tenant) == expected
    unassigned = await _owner(
        migrated_database,
        "SELECT count(*) FROM membership_roles mr JOIN roles r ON r.id = mr.role_id "
        "WHERE r.template_code IN ('ADMISSIONS_MANAGER', 'COUNSELLOR')",
    )
    assert unassigned[0][0] == 0  # the migration assigns nobody
    await anyio.to_thread.run_sync(command.check, config)
