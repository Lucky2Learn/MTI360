"""Database foundation against real PostgreSQL (T01-01; ADR-0001, ADR-0004).

Migrations, least-privilege roles, the transaction-per-request session with
SET LOCAL context, and the column mixins. Runs against the test database from
``TEST_*_DATABASE_URL`` (skipped when unset unless REQUIRE_DATABASE_TESTS=1).
"""

import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast
from urllib.parse import urlsplit

import anyio
import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from conftest import DatabaseUnderTest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import MetaData, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.pool import NullPool

from app.api.realms import REALM_PREFIXES, Access, realm_router
from app.core.context import Realm, RequestContext
from app.core.db import NAMING_CONVENTION, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin
from app.core.db.session import DbSession, _transaction
from app.core.errors import NotFoundError
from app.main import create_app

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


async def _scalar(url: str, sql: str) -> Any:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return (await connection.execute(text(sql))).scalar()
    finally:
        await engine.dispose()


async def _denied(url: str, sql: str) -> bool:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(sql))
    except DBAPIError as error:
        return "permission denied" in str(error.orig).lower()
    finally:
        await engine.dispose()
    return False


def _head(config: Config) -> str:
    """The current Alembic head, derived from the scripts (never a fixed revision)."""
    head = ScriptDirectory.from_config(config).get_current_head()
    assert head is not None
    return head


# --- Migrations -------------------------------------------------------------------


async def test_migrations_are_at_head_without_model_drift(
    migrated_database: DatabaseUnderTest,
) -> None:
    version = await _scalar(migrated_database.owner_url, "SELECT version_num FROM alembic_version")

    assert version == _head(migrated_database.alembic_config())
    # `alembic check` raises when the models and the migrations differ. Alembic
    # runs its own event loop, so it is called from a worker thread.
    await anyio.to_thread.run_sync(command.check, migrated_database.alembic_config())


async def test_migrations_downgrade_and_upgrade_cleanly(
    migrated_database: DatabaseUnderTest,
) -> None:
    config = migrated_database.alembic_config()

    await anyio.to_thread.run_sync(command.downgrade, config, "base")
    assert await _scalar(migrated_database.owner_url, "SELECT count(*) FROM alembic_version") == 0
    # The baseline downgrade restores the default privileges of the app role.
    assert not await _denied(
        migrated_database.app_url, "UPDATE alembic_version SET version_num = version_num"
    )
    await anyio.to_thread.run_sync(command.upgrade, config, "head")

    assert await _scalar(
        migrated_database.owner_url, "SELECT version_num FROM alembic_version"
    ) == _head(config)


# --- Least privilege (ADR-0004) -------------------------------------------------------


async def test_runtime_roles_are_unprivileged_and_do_not_own_the_schema(
    migrated_database: DatabaseUnderTest,
) -> None:
    for url in (migrated_database.app_url, migrated_database.readonly_url):
        attributes = await _scalar(
            url,
            "SELECT row(rolsuper, rolbypassrls, rolcreaterole, rolcreatedb)::text "
            "FROM pg_roles WHERE rolname = current_user",
        )
        assert attributes == "(f,f,f,f)"
        assert not await _scalar(url, "SELECT has_schema_privilege('public', 'CREATE')")
        assert await _denied(url, "CREATE TABLE probe_forbidden (id int)")

    owner = await _scalar(
        migrated_database.app_url,
        "SELECT nspowner::regrole::text FROM pg_namespace WHERE nspname = 'public'",
    )
    assert owner == urlsplit(migrated_database.owner_url).username


async def test_runtime_roles_can_read_but_never_change_the_migration_state(
    migrated_database: DatabaseUnderTest,
) -> None:
    head = _head(migrated_database.alembic_config())
    for url in (migrated_database.app_url, migrated_database.readonly_url):
        assert await _scalar(url, "SELECT version_num FROM alembic_version") == head
        assert await _denied(url, "UPDATE alembic_version SET version_num = 'forged'")
        assert await _denied(url, "DELETE FROM alembic_version")


# --- Transaction per request ------------------------------------------------------------


async def _single_connection_app(database: DatabaseUnderTest) -> tuple[FastAPI, AsyncEngine]:
    """App whose pool holds ONE connection, so a temporary table is visible to requests."""
    app = create_app(database.settings())
    await app.state.engine.dispose()
    engine = create_async_engine(database.app_url, pool_size=1, max_overflow=0)
    app.state.engine = engine
    app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "CREATE TEMPORARY TABLE probe_rows (name text, "
                "CONSTRAINT probe_rows_name_key UNIQUE (name) DEFERRABLE INITIALLY DEFERRED)"
            )
        )

    router = realm_router(Realm.PUBLIC, access=Access.ANONYMOUS)

    @router.post("/probe/rows/{name}")
    async def insert(name: str, session: DbSession) -> dict[str, str]:
        await session.execute(text("INSERT INTO probe_rows VALUES (:n)"), {"n": name})
        return {"inserted": name}

    @router.post("/probe/rows/{name}/fail")
    async def insert_then_fail(name: str, session: DbSession) -> None:
        await session.execute(text("INSERT INTO probe_rows VALUES (:n)"), {"n": name})
        raise NotFoundError()

    @router.post("/probe/deferred-violation")
    async def deferred(session: DbSession) -> dict[str, str]:
        # The unique violation is only detected at COMMIT.
        await session.execute(text("INSERT INTO probe_rows VALUES ('dup'), ('dup')"))
        return {"status": "handler returned"}

    @router.get("/probe/rows")
    async def names(session: DbSession) -> list[str]:
        result = await session.execute(text("SELECT name FROM probe_rows ORDER BY name"))
        return list(result.scalars())

    @router.get("/probe/settings")
    async def settings(session: DbSession) -> dict[str, str]:
        row = (
            await session.execute(
                text(
                    "SELECT current_setting('app.realm', true), "
                    "current_setting('app.request_id', true), "
                    "coalesce(current_setting('app.tenant_id', true), ''), "
                    "coalesce(current_setting('app.user_id', true), '')"
                )
            )
        ).one()
        return dict(zip(("realm", "request_id", "tenant_id", "user_id"), row, strict=True))

    app.include_router(router, prefix=REALM_PREFIXES[Realm.PUBLIC])
    return app, engine


@pytest.fixture
async def db_client(
    migrated_database: DatabaseUnderTest,
) -> AsyncIterator[tuple[AsyncClient, AsyncEngine]]:
    app, engine = await _single_connection_app(migrated_database)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            yield client, engine
    finally:
        await engine.dispose()


BASE = "/api/v1/public/probe"


async def test_request_commits_on_success_and_rolls_back_on_error(
    db_client: tuple[AsyncClient, AsyncEngine],
) -> None:
    client, _ = db_client

    assert (await client.post(f"{BASE}/rows/kept")).status_code == 200
    failed = await client.post(f"{BASE}/rows/discarded/fail")

    assert failed.status_code == 404
    assert (await client.get(f"{BASE}/rows")).json() == ["kept"]


async def test_commit_happens_before_the_response_is_sent(
    db_client: tuple[AsyncClient, AsyncEngine],
) -> None:
    client, _ = db_client

    response = await client.post(f"{BASE}/deferred-violation")

    # The handler returned, but the commit failed: the client must not see success.
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert (await client.get(f"{BASE}/rows")).json() == []


async def test_context_is_set_local_and_never_leaks_to_the_next_transaction(
    db_client: tuple[AsyncClient, AsyncEngine],
) -> None:
    client, engine = db_client

    response = await client.get(f"{BASE}/settings")
    values = response.json()

    assert values["realm"] == "public"
    assert values["request_id"] == response.headers["X-Request-ID"]
    assert values["tenant_id"] == ""
    assert values["user_id"] == ""
    # Same pooled connection, next transaction: nothing survives.
    async with engine.connect() as connection:
        leftover = (
            await connection.execute(text("SELECT current_setting('app.realm', true)"))
        ).scalar()
    assert leftover in (None, "")


@pytest.mark.parametrize(
    ("realm", "expects_user_id"),
    [(Realm.TENANT, True), (Realm.STUDENT, True), (Realm.PLATFORM, False)],
)
async def test_user_id_is_published_only_for_user_realms(
    migrated_database: DatabaseUnderTest, realm: Realm, expects_user_id: bool
) -> None:
    engine = create_async_engine(migrated_database.app_url, poolclass=NullPool)
    principal, tenant = uuid.uuid7(), uuid.uuid7()
    context = RequestContext(
        realm=realm, request_id=uuid.uuid7(), principal_id=principal, tenant_id=tenant
    )
    request = SimpleNamespace(
        state=SimpleNamespace(context=context),
        app=SimpleNamespace(state=SimpleNamespace(sessionmaker=async_sessionmaker(engine))),
    )
    try:
        transaction = cast(AsyncGenerator[AsyncSession], _transaction(cast(Request, request)))
        session = await anext(transaction)
        user_id, tenant_id = (
            await session.execute(
                text(
                    "SELECT current_setting('app.user_id', true), "
                    "current_setting('app.tenant_id', true)"
                )
            )
        ).one()
        await transaction.aclose()
    finally:
        await engine.dispose()

    assert tenant_id == str(tenant)
    assert (user_id == str(principal)) is expects_user_id
    assert user_id in (str(principal), None, "")


# --- Mixins ----------------------------------------------------------------------------


class _ProbeBase(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class _Vessel(UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, _ProbeBase):
    __tablename__ = "probe_vessels"
    __table_args__ = {"prefixes": ["TEMPORARY"]}  # noqa: RUF012 - SQLAlchemy convention

    name: Mapped[str] = mapped_column()


async def test_mixins_generate_uuid7_timestamps_and_optimistic_locking(
    migrated_database: DatabaseUnderTest,
) -> None:
    engine = create_async_engine(migrated_database.app_url, pool_size=1, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_ProbeBase.metadata.create_all)

        async with sessions() as session, session.begin():
            vessel = _Vessel(name="MV Coral Star")
            session.add(vessel)
        assert vessel.id.version == 7
        assert vessel.version == 1

        async with sessions() as session:
            created, updated = (
                await session.execute(
                    select(_Vessel.created_at, _Vessel.updated_at).where(_Vessel.id == vessel.id)
                )
            ).one()
        assert isinstance(created, datetime)
        assert created.tzinfo is not None
        assert created == updated

        async with sessions() as session, session.begin():
            loaded = await session.get_one(_Vessel, vessel.id)
            loaded.name = "MV Coral Star II"
        async with sessions() as session:
            reloaded = await session.get_one(_Vessel, vessel.id)
            database_now = await session.scalar(select(func.now()))
        assert reloaded.version == 2
        assert reloaded.updated_at > reloaded.created_at
        assert database_now is not None

        # A concurrent writer changes the row: the stale update must fail.
        async with sessions() as session:
            stale = await session.get_one(_Vessel, vessel.id)
            await session.execute(
                text("UPDATE probe_vessels SET version = version + 1 WHERE id = :id"),
                {"id": vessel.id},
            )
            stale.name = "lost update"
            with pytest.raises(StaleDataError):
                await session.flush()
            await session.rollback()
    finally:
        await engine.dispose()
