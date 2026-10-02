"""Tenant isolation at the database and repository layers (T01-03; ADR-0004, ADR-0014).

Two tenants, A and B, each with one campus that has the same code. Every
guarantee is exercised against real PostgreSQL:

* Row-Level Security through the real runtime roles (``mti_app``,
  ``mti_readonly``) and the trusted ``SET LOCAL`` context, with raw SQL.
* The ORM filter and the repository, also as the **owner**, which bypasses
  RLS: the application layers must isolate tenants on their own.
* ``system_context`` end to end, including a real HTTP request.

The test database is shared and tenant rows cannot be deleted, so every test
builds its own tenants and never counts a whole table.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import pytest
from conftest import DatabaseUnderTest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Column, MetaData, Table, Uuid, delete, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import aliased
from sqlalchemy.pool import NullPool

from app.api.realms import REALM_PREFIXES, Access, realm_router
from app.core.audit import AuditCategory, AuditEventType, AuditTarget, write_audit_event
from app.core.audit.writer import AUDIT_TABLE
from app.core.context import Realm, RequestContext, current_context, optional_context
from app.core.db import create_sessionmaker
from app.core.db.session import context_transaction
from app.core.errors import NotFoundError
from app.core.tenancy import (
    MissingTenantContextError,
    SystemContextError,
    TenantMismatchError,
    TenantScopedRepository,
    system_context,
    tenant_foreign_key,
)
from app.main import create_app
from app.modules.institute.models import Campus
from app.modules.tenants.models import Tenant

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

RLS_VIOLATION = "row-level security"
PERMISSION_DENIED = "permission denied"
FK_VIOLATION = "foreign key constraint"

SYSTEM_PROBE = AuditEventType("tenancy.system_probe", AuditCategory.ADMIN)


class CampusRepository(TenantScopedRepository[Campus]):
    model = Campus


# --- Fixtures and helpers ----------------------------------------------------------------


@asynccontextmanager
async def _factory(
    url: str, **engine_options: Any
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(url, **(engine_options or {"poolclass": NullPool}))
    try:
        yield create_sessionmaker(engine)
    finally:
        await engine.dispose()


@pytest.fixture
async def app_db(
    migrated_database: DatabaseUnderTest,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with _factory(migrated_database.app_url) as factory:
        yield factory


@pytest.fixture
async def owner_db(
    migrated_database: DatabaseUnderTest,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """The owner bypasses RLS (not forced): only the application layers can isolate."""
    async with _factory(migrated_database.owner_url) as factory:
        yield factory


@pytest.fixture
async def readonly_db(
    migrated_database: DatabaseUnderTest,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with _factory(migrated_database.readonly_url) as factory:
        yield factory


@dataclass(frozen=True)
class World:
    a: uuid.UUID
    b: uuid.UUID
    campus_a: uuid.UUID
    campus_b: uuid.UUID
    code: str

    @property
    def campuses(self) -> list[uuid.UUID]:
        return [self.campus_a, self.campus_b]

    @property
    def tenants(self) -> list[uuid.UUID]:
        return [self.a, self.b]


@pytest.fixture
async def world(app_db: async_sessionmaker[AsyncSession]) -> World:
    """Tenants A and B, created through the system realm as the application role."""
    async with system_context(app_db) as session:
        tenant_a = Tenant(name="Eastern Maritime Training Institute")
        tenant_b = Tenant(name="Konkan Nautical Academy")
        session.add_all([tenant_a, tenant_b])
    code = f"MUM-{uuid.uuid7().hex[-6:].upper()}"
    campuses: dict[uuid.UUID, uuid.UUID] = {}
    for tenant in (tenant_a, tenant_b):
        async with system_context(app_db, tenant_id=tenant.id) as session:
            campus = await CampusRepository(session).add(Campus(name="Mumbai Campus", code=code))
            campuses[tenant.id] = campus.id
    return World(tenant_a.id, tenant_b.id, campuses[tenant_a.id], campuses[tenant_b.id], code)


@asynccontextmanager
async def _as(
    factory: async_sessionmaker[AsyncSession], realm: Realm, tenant: uuid.UUID | None = None
) -> AsyncIterator[AsyncSession]:
    """A transaction with a trusted context (``SET LOCAL``), as the role of ``factory``."""
    context = RequestContext(realm=realm, request_id=uuid.uuid7(), tenant_id=tenant)
    async with context_transaction(factory, context) as session:
        yield session


async def _visible(
    factory: async_sessionmaker[AsyncSession],
    realm: Realm,
    tenant: uuid.UUID | None,
    table: str,
    ids: list[uuid.UUID],
) -> set[uuid.UUID]:
    """IDs of ``table`` visible with raw SQL (no ORM filter, only RLS)."""
    async with _as(factory, realm, tenant) as session:
        result = await session.execute(
            text(f"SELECT id FROM {table} WHERE id = ANY(:ids)"),  # noqa: S608 - fixed names
            {"ids": ids},
        )
        return set(result.scalars())


async def _error(coroutine: Any) -> str | None:
    try:
        await coroutine
    except DBAPIError as error:
        return str(error.orig).lower()
    return None


async def _execute(
    factory: async_sessionmaker[AsyncSession],
    realm: Realm,
    tenant: uuid.UUID | None,
    sql: str,
    **params: Any,
) -> int:
    """Run raw SQL in a trusted context; the number of affected rows."""
    async with _as(factory, realm, tenant) as session:
        result = await session.execute(text(sql), params)
        return result.rowcount  # type: ignore[attr-defined, no-any-return]


async def _campus_names(
    owner_db: async_sessionmaker[AsyncSession], world: World
) -> dict[uuid.UUID, str]:
    async with owner_db() as session:
        rows = await session.execute(
            text("SELECT tenant_id, name FROM campuses WHERE id = ANY(:ids)"),
            {"ids": world.campuses},
        )
        return {row.tenant_id: row.name for row in rows}


CONTEXT_SETTINGS = (
    "SELECT current_setting('app.realm', true), current_setting('app.tenant_id', true), "
    "current_setting('app.request_id', true), current_setting('app.user_id', true)"
)

INSERT_CAMPUS = (
    "INSERT INTO campuses (id, tenant_id, name, code, version) "
    "VALUES (:id, :tenant_id, 'Chennai Campus', :code, 1)"
)


# --- RLS: campuses (tenant-owned, realm-agnostic) ------------------------------------------


async def test_each_tenant_reads_only_its_own_campuses(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    for realm in (Realm.TENANT, Realm.STUDENT, Realm.SYSTEM):
        assert await _visible(app_db, realm, world.a, "campuses", world.campuses) == {
            world.campus_a
        }
        assert await _visible(app_db, realm, world.b, "campuses", world.campuses) == {
            world.campus_b
        }


@pytest.mark.parametrize("realm", list(Realm))
async def test_without_a_tenant_context_no_campus_is_visible(
    app_db: async_sessionmaker[AsyncSession], world: World, realm: Realm
) -> None:
    # Platform, system or any other realm without a trusted tenant: fail closed.
    assert await _visible(app_db, realm, None, "campuses", world.campuses) == set()


async def test_a_tenant_cannot_insert_a_campus_into_another_tenant(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    message = await _error(
        _execute(
            app_db,
            Realm.TENANT,
            world.a,
            INSERT_CAMPUS,
            id=uuid.uuid7(),
            tenant_id=world.b,
            code="CHN",
        )
    )
    no_context = await _error(
        _execute(
            app_db,
            Realm.PLATFORM,
            None,
            INSERT_CAMPUS,
            id=uuid.uuid7(),
            tenant_id=world.b,
            code="CHN",
        )
    )

    assert RLS_VIOLATION in (message or "")
    assert RLS_VIOLATION in (no_context or "")
    assert await _visible(app_db, Realm.TENANT, world.b, "campuses", world.campuses) == {
        world.campus_b
    }


async def test_a_tenant_cannot_update_or_move_another_tenants_campus(
    app_db: async_sessionmaker[AsyncSession],
    owner_db: async_sessionmaker[AsyncSession],
    world: World,
) -> None:
    rename = "UPDATE campuses SET name = 'Hijacked Campus' WHERE id = :id"
    move = "UPDATE campuses SET tenant_id = :other WHERE id = :id"

    assert await _execute(app_db, Realm.TENANT, world.a, rename, id=world.campus_b) == 0
    assert RLS_VIOLATION in (
        await _error(
            _execute(app_db, Realm.TENANT, world.a, move, id=world.campus_a, other=world.b)
        )
        or ""
    )
    assert await _execute(app_db, Realm.TENANT, world.a, rename, id=world.campus_a) == 1
    names = await _campus_names(owner_db, world)
    assert names == {world.a: "Hijacked Campus", world.b: "Mumbai Campus"}


async def test_the_application_role_cannot_delete_campuses_or_tenants(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    for sql, row in (
        ("DELETE FROM campuses WHERE id = :id", world.campus_a),
        ("DELETE FROM tenants WHERE id = :id", world.a),
    ):
        message = await _error(_execute(app_db, Realm.SYSTEM, world.a, sql, id=row))
        assert PERMISSION_DENIED in (message or ""), sql


async def test_the_readonly_role_reads_its_tenant_only_and_never_writes(
    readonly_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    assert await _visible(readonly_db, Realm.TENANT, world.a, "campuses", world.campuses) == {
        world.campus_a
    }
    assert await _visible(readonly_db, Realm.TENANT, world.a, "tenants", world.tenants) == {world.a}
    for realm in (Realm.PLATFORM, Realm.SYSTEM):
        assert await _visible(readonly_db, realm, None, "tenants", world.tenants) == set()
        assert await _visible(readonly_db, realm, None, "campuses", world.campuses) == set()
    for sql in (
        INSERT_CAMPUS,
        "UPDATE campuses SET name = 'Changed' WHERE id = :campus",
        "UPDATE tenants SET name = 'Changed' WHERE id = :tenant_id",
    ):
        message = await _error(
            _execute(
                readonly_db,
                Realm.TENANT,
                world.a,
                sql,
                id=uuid.uuid7(),
                tenant_id=world.a,
                code="RO",
                campus=world.campus_a,
            )
        )
        assert PERMISSION_DENIED in (message or ""), sql


async def test_a_malformed_tenant_setting_fails_closed(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    async def query() -> None:
        async with app_db() as session, session.begin():
            await session.execute(
                text("SELECT set_config('app.tenant_id', :v, true)"), {"v": "' OR true --"}
            )
            await session.execute(text("SELECT id FROM campuses"))

    assert "invalid input syntax for type uuid" in (await _error(query()) or "")


async def test_composite_foreign_keys_reject_cross_tenant_links(
    owner_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    metadata = MetaData()
    Table("campuses", metadata, Column("tenant_id", Uuid), Column("id", Uuid))
    probe = Table(
        "probe_campus_children",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("tenant_id", Uuid, nullable=False),
        Column("campus_id", Uuid, nullable=False),
        tenant_foreign_key("campus_id", "campuses"),
    )
    insert_child = probe.insert()

    async with owner_db() as session:
        transaction = await session.begin()
        try:
            connection = await session.connection()
            await connection.run_sync(lambda sync: probe.create(sync))
            await connection.execute(
                insert_child,
                {"id": uuid.uuid7(), "tenant_id": world.a, "campus_id": world.campus_a},
            )
            savepoint = await connection.begin_nested()
            message = await _error(
                connection.execute(
                    insert_child,
                    {"id": uuid.uuid7(), "tenant_id": world.a, "campus_id": world.campus_b},
                )
            )
            await savepoint.rollback()
        finally:
            await transaction.rollback()  # the probe table never persists

    assert FK_VIOLATION in (message or "")


# --- RLS: tenants (global registry, realm-aware) --------------------------------------------


async def test_platform_and_system_read_every_tenant(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    for realm in (Realm.PLATFORM, Realm.SYSTEM):
        assert await _visible(app_db, realm, None, "tenants", world.tenants) == set(world.tenants)


@pytest.mark.parametrize("realm", [Realm.TENANT, Realm.STUDENT, Realm.PUBLIC, Realm.WEBHOOK])
async def test_other_realms_read_only_their_trusted_tenant(
    app_db: async_sessionmaker[AsyncSession], world: World, realm: Realm
) -> None:
    assert await _visible(app_db, realm, world.a, "tenants", world.tenants) == {world.a}
    assert await _visible(app_db, realm, world.b, "tenants", world.tenants) == {world.b}
    assert await _visible(app_db, realm, None, "tenants", world.tenants) == set()


async def test_only_platform_and_system_insert_or_update_tenants(
    app_db: async_sessionmaker[AsyncSession],
    owner_db: async_sessionmaker[AsyncSession],
    world: World,
) -> None:
    insert = "INSERT INTO tenants (id, name, status, version) VALUES (:id, 'Rogue', 'ACTIVE', 1)"
    suspend = "UPDATE tenants SET status = 'SUSPENDED' WHERE id = :id"

    for realm in (Realm.TENANT, Realm.STUDENT, Realm.PUBLIC, Realm.WEBHOOK):
        message = await _error(_execute(app_db, realm, world.a, insert, id=uuid.uuid7()))
        assert RLS_VIOLATION in (message or ""), realm
        # Own row is readable but never writable outside platform and system.
        assert await _execute(app_db, realm, world.a, suspend, id=world.a) == 0, realm

    assert await _execute(app_db, Realm.PLATFORM, None, suspend, id=world.a) == 1
    assert await _execute(app_db, Realm.SYSTEM, None, insert, id=uuid.uuid7()) == 1
    async with owner_db() as session:
        status = (
            await session.execute(
                text("SELECT status FROM tenants WHERE id = :id"), {"id": world.a}
            )
        ).scalar()
    assert status == "SUSPENDED"


# --- ORM filter -----------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["app_url", "owner_url"])
async def test_orm_selects_aliases_and_joins_are_tenant_filtered(
    migrated_database: DatabaseUnderTest, world: World, role: str
) -> None:
    other = aliased(Campus)
    async with (
        _factory(getattr(migrated_database, role)) as factory,
        _as(factory, Realm.TENANT, world.a) as session,
    ):
        plain = set(
            (
                await session.execute(select(Campus.id).where(Campus.id.in_(world.campuses)))
            ).scalars()
        )
        alias = set(
            (await session.execute(select(other.id).where(other.id.in_(world.campuses)))).scalars()
        )
        pairs = (
            await session.execute(
                select(Campus.id, other.id)
                .join(other, other.code == Campus.code)
                .where(Campus.code == world.code)
            )
        ).all()
        by_id = await session.get(Campus, world.campus_b)

    assert plain == {world.campus_a}
    assert alias == {world.campus_a}
    assert [tuple(pair) for pair in pairs] == [(world.campus_a, world.campus_a)]
    assert by_id is None


async def test_orm_bulk_update_and_delete_touch_only_the_trusted_tenant(
    owner_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    # As the owner, RLS does not apply: only the ORM filter protects tenant B.
    async with _as(owner_db, Realm.TENANT, world.a) as session:
        updated = await session.execute(
            update(Campus).where(Campus.code == world.code).values(name="Renamed Campus")
        )
    assert updated.rowcount == 1  # type: ignore[attr-defined]
    assert await _campus_names(owner_db, world) == {
        world.a: "Renamed Campus",
        world.b: "Mumbai Campus",
    }

    async with _as(owner_db, Realm.TENANT, world.a) as session:
        deleted = await session.execute(delete(Campus).where(Campus.code == world.code))
    assert deleted.rowcount == 1  # type: ignore[attr-defined]
    assert await _campus_names(owner_db, world) == {world.b: "Mumbai Campus"}


@pytest.mark.parametrize("realm", [Realm.PLATFORM, Realm.SYSTEM, Realm.TENANT])
async def test_orm_queries_without_a_tenant_raise_even_for_the_owner(
    owner_db: async_sessionmaker[AsyncSession], world: World, realm: Realm
) -> None:
    async with _as(owner_db, realm, None) as session:
        with pytest.raises(MissingTenantContextError):
            await session.execute(select(Campus).where(Campus.id.in_(world.campuses)))
        with pytest.raises(MissingTenantContextError):
            await session.execute(update(Campus).values(name="Everywhere"))


# --- Repository ----------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["app_url", "owner_url"])
async def test_the_repository_reads_only_the_trusted_tenant(
    migrated_database: DatabaseUnderTest, world: World, role: str
) -> None:
    async with (
        _factory(getattr(migrated_database, role)) as factory,
        _as(factory, Realm.TENANT, world.a) as session,
    ):
        repository = CampusRepository(session)
        own = await repository.get(world.campus_a)
        missing = await repository.find(world.campus_b)
        with pytest.raises(NotFoundError):
            await repository.get(world.campus_b)
        with pytest.raises(NotFoundError):
            await repository.get(uuid.uuid7())
        listed = await repository.list(limit=100, offset=0)
        count = await repository.count()

    assert own.tenant_id == world.a
    assert missing is None
    assert [campus.id for campus in listed] == [world.campus_a]
    assert count == 1


async def test_the_repository_stamps_the_trusted_tenant_and_rejects_another(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    async with _as(app_db, Realm.TENANT, world.a) as session:
        repository = CampusRepository(session)
        stamped = await repository.add(Campus(name="Vizag Campus", code="VIZAG"))
        with pytest.raises(TenantMismatchError):
            await repository.add(Campus(tenant_id=world.b, name="Smuggled Campus", code="SMUGGLED"))

    async with _as(app_db, Realm.TENANT, world.b) as session:
        b_codes = {
            campus.code for campus in await CampusRepository(session).list(limit=100, offset=0)
        }

    assert stamped.tenant_id == world.a
    assert b_codes == {world.code}


# --- system_context --------------------------------------------------------------------------


async def test_system_context_publishes_one_trusted_system_context(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    async with system_context(app_db, tenant_id=world.a) as session:
        context = current_context()
        settings = (await session.execute(text(CONTEXT_SETTINGS))).one()
        orm_ids = set(
            (
                await session.execute(select(Campus.id).where(Campus.id.in_(world.campuses)))
            ).scalars()
        )
    async with system_context(app_db, tenant_id=world.a):
        second_request = current_context().request_id

    assert context.realm is Realm.SYSTEM
    assert context.tenant_id == world.a
    assert context.principal_id is None
    assert context.request_id.version == 7
    assert second_request != context.request_id
    assert tuple(settings) == ("system", str(world.a), str(context.request_id), None)
    assert orm_ids == {world.campus_a}
    assert optional_context() is None


async def test_system_context_leaks_nothing_after_exit_or_failure(
    migrated_database: DatabaseUnderTest, world: World
) -> None:
    # One pooled connection: the next transaction reuses it and must see no context.
    async with _factory(migrated_database.app_url, pool_size=1, max_overflow=0) as factory:

        async def failing_job() -> None:
            async with system_context(factory, tenant_id=world.a) as session:
                await CampusRepository(session).add(
                    Campus(name="Rolled Back Campus", code="ROLLBACK")
                )
                raise RuntimeError("job failed")

        with pytest.raises(RuntimeError):
            await failing_job()
        assert optional_context() is None
        async with factory() as session, session.begin():
            settings = (await session.execute(text(CONTEXT_SETTINGS))).one()
        async with system_context(factory, tenant_id=world.a) as session:
            codes = {c.code for c in await CampusRepository(session).list(limit=100, offset=0)}

    assert tuple(settings) == ("", "", "", None)
    assert codes == {world.code}


async def test_nested_system_contexts_restore_the_outer_context(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    inner_ids: set[uuid.UUID] = set()

    async def failing_inner_job() -> None:
        async with system_context(app_db, tenant_id=world.b) as inner:
            assert current_context().tenant_id == world.b
            query = select(Campus.id).where(Campus.id.in_(world.campuses))
            inner_ids.update((await inner.execute(query)).scalars())
            raise RuntimeError("inner job failed")

    async with system_context(app_db, tenant_id=world.a) as outer:
        outer_context = current_context()
        with pytest.raises(RuntimeError):
            await failing_inner_job()
        assert current_context() is outer_context
        outer_ids = set(
            (await outer.execute(select(Campus.id).where(Campus.id.in_(world.campuses)))).scalars()
        )

    assert inner_ids == {world.campus_b}
    assert outer_ids == {world.campus_a}
    assert optional_context() is None


async def test_audit_events_written_in_system_context_carry_its_context(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    async with system_context(app_db, tenant_id=world.a) as session:
        request_id = current_context().request_id
        await write_audit_event(session, SYSTEM_PROBE, target=AuditTarget("tenant", world.a))

    async with _as(app_db, Realm.PLATFORM) as session:
        row = (
            await session.execute(select(AUDIT_TABLE).where(AUDIT_TABLE.c.request_id == request_id))
        ).one()

    assert (row.realm, row.tenant_id, row.principal_id) == ("system", world.a, None)
    assert (row.category, row.event_type, row.target_id) == (
        "admin",
        "tenancy.system_probe",
        world.a,
    )


async def test_system_context_is_refused_inside_an_http_request(
    migrated_database: DatabaseUnderTest, world: World
) -> None:
    application: FastAPI = create_app(migrated_database.settings())
    public = realm_router(Realm.PUBLIC, access=Access.ANONYMOUS)
    outcome: list[str] = []

    @public.get("/probe/system-context", tags=["probe"])
    async def escalate(request: Request) -> None:
        try:
            async with system_context(request.app.state.sessionmaker, tenant_id=world.a):
                outcome.append("opened")
        except SystemContextError:
            outcome.append("refused")
            raise

    application.include_router(public, prefix=REALM_PREFIXES[Realm.PUBLIC])
    transport = ASGITransport(app=application, raise_app_exceptions=False)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/v1/public/probe/system-context")
    finally:
        await application.state.engine.dispose()

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert outcome == ["refused"]
