"""Audit foundation against real PostgreSQL (T01-02; ADR-0013).

Schema, privileges, append-only enforcement, Row-Level Security, the
migration, the transactional audit writer and the post-request security-event
flush. Every security guarantee is exercised through the real runtime roles
and the trusted ``SET LOCAL`` context — no mocks.

The test database is shared by the session and the application role cannot
delete audit rows, so every test identifies its own rows by a unique request
ID and never counts the whole table.
"""

import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

import anyio
import pytest
from alembic import command
from alembic.script import ScriptDirectory
from conftest import DatabaseUnderTest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, insert, select, text
from sqlalchemy.engine import Row
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.api.realms import REALM_PREFIXES, Access, realm_router
from app.core.audit import (
    AuditCategory,
    AuditEventType,
    AuditTarget,
    record_security_event,
    write_audit_event,
)
from app.core.audit.security import SecurityEventBuffer, flush_security_events
from app.core.audit.writer import AUDIT_TABLE, audit_row
from app.core.context import Realm, RequestContext
from app.core.db.session import DbSession, context_transaction
from app.core.db.settings import apply_transaction_settings
from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.logging import JsonFormatter
from app.main import create_app

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

DOMAIN_EVENT = AuditEventType("probe.row_created", AuditCategory.DOMAIN)
SECURITY_EVENT = AuditEventType("auth.probe_denied", AuditCategory.SECURITY)
SECRET = "hunter2-must-never-be-stored-or-logged"
TENANT_A, TENANT_B = uuid.uuid7(), uuid.uuid7()

RLS_VIOLATION = "row-level security"
PERMISSION_DENIED = "permission denied"
APPEND_ONLY = "append-only"


# --- Helpers -------------------------------------------------------------------------


@asynccontextmanager
async def _engine(url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@asynccontextmanager
async def _as(
    url: str, realm: Realm, tenant: uuid.UUID | None = None
) -> AsyncIterator[tuple[AsyncSession, RequestContext]]:
    """A transaction as the role of ``url`` with a trusted context (SET LOCAL)."""
    context = RequestContext(realm=realm, request_id=uuid.uuid7(), tenant_id=tenant)
    async with (
        _engine(url) as engine,
        context_transaction(async_sessionmaker(engine), context) as session,
    ):
        yield session, context


async def _error(coroutine: Any) -> str | None:
    """The database error message of ``coroutine``, or None when it succeeds."""
    try:
        await coroutine
    except DBAPIError as error:
        return str(error.orig).lower()
    return None


async def _insert_event(
    url: str,
    context_realm: Realm,
    context_tenant: uuid.UUID | None,
    **overrides: Any,
) -> uuid.UUID:
    """Insert one event in a trusted context; ``overrides`` replace row values."""
    async with _as(url, context_realm, context_tenant) as (session, context):
        row = audit_row(context, DOMAIN_EVENT) | overrides
        await session.execute(insert(AUDIT_TABLE).values(**row))
    return row["id"]  # type: ignore[no-any-return]


async def _visible(
    url: str, realm: Realm, tenant: uuid.UUID | None, ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    async with _as(url, realm, tenant) as (session, _):
        result = await session.execute(select(AUDIT_TABLE.c.id).where(AUDIT_TABLE.c.id.in_(ids)))
        return set(result.scalars())


async def _events(database: DatabaseUnderTest, request_id: str) -> list[Row[Any]]:
    """Rows of one request, read through the platform audit-read policy."""
    async with _as(database.app_url, Realm.PLATFORM) as (session, _):
        result = await session.execute(
            select(AUDIT_TABLE)
            .where(AUDIT_TABLE.c.request_id == uuid.UUID(request_id))
            .order_by(AUDIT_TABLE.c.id)
        )
        return list(result.all())


async def _owner_scalar(database: DatabaseUnderTest, sql: str) -> Any:
    async with _engine(database.owner_url) as engine, engine.connect() as connection:
        return (await connection.execute(text(sql))).scalar()


# --- Schema ---------------------------------------------------------------------------


async def test_audit_events_schema_constraints_and_indexes(
    migrated_database: DatabaseUnderTest,
) -> None:
    nullable = await _owner_scalar(
        migrated_database,
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_name = 'audit_events' AND column_name = 'tenant_id'",
    )
    foreign_keys = await _owner_scalar(
        migrated_database,
        "SELECT count(*) FROM pg_constraint "
        "WHERE conrelid = 'audit_events'::regclass AND contype = 'f'",
    )
    indexes = await _owner_scalar(
        migrated_database,
        "SELECT string_agg(indexname, ',' ORDER BY indexname) FROM pg_indexes "
        "WHERE tablename = 'audit_events'",
    )
    table_owner = await _owner_scalar(
        migrated_database, "SELECT tableowner FROM pg_tables WHERE tablename = 'audit_events'"
    )

    assert nullable == "YES"
    assert foreign_keys == 0  # deliberate: no tenants table yet, history outlives tenants
    assert indexes.split(",") == [
        "ix_audit_events_category_created_at",
        "ix_audit_events_request_id",
        "ix_audit_events_tenant_id_created_at",
        "pk_audit_events",
    ]
    assert table_owner == urlsplit(migrated_database.owner_url).username


@pytest.mark.parametrize(
    "overrides",
    [
        {"category": "audit"},
        {"category": "other"},
        {"realm": "anonymous"},
        {"event_type": "NotStructured"},
        {"target_type": "Bad Type"},
        {"target_id": uuid.uuid7()},  # an ID without a type
        {"metadata": ["not", "an", "object"]},
        {"metadata": {"blob": "x" * 9000}},
    ],
)
async def test_the_database_rejects_rows_outside_the_contract(
    migrated_database: DatabaseUnderTest, overrides: dict[str, Any]
) -> None:
    # The owner bypasses RLS, so only the check constraints are exercised.
    async with _engine(migrated_database.owner_url) as engine:
        context = RequestContext(realm=Realm.SYSTEM, request_id=uuid.uuid7())
        row = audit_row(context, DOMAIN_EVENT) | overrides
        message = await _error(_owner_insert(engine, row))

    assert message is not None
    assert "check constraint" in message


async def _owner_insert(engine: AsyncEngine, row: dict[str, Any]) -> None:
    async with engine.begin() as connection:
        await connection.execute(insert(AUDIT_TABLE).values(**row))


# --- Privileges and append-only ---------------------------------------------------------


async def test_runtime_privileges_are_select_insert_only_and_none_for_readonly(
    migrated_database: DatabaseUnderTest,
) -> None:
    roles = migrated_database.roles
    privileges = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
    granted: dict[str, set[str]] = {}
    for key in ("app", "readonly"):
        granted[key] = {
            privilege
            for privilege in privileges
            if await _owner_scalar(
                migrated_database,
                f"SELECT has_table_privilege('{roles[key]}', 'audit_events', '{privilege}')",
            )
        }

    assert granted == {"app": {"SELECT", "INSERT"}, "readonly": set()}
    for url in (migrated_database.app_url, migrated_database.readonly_url):
        async with _engine(url) as engine, engine.connect() as connection:
            bypass = (
                await connection.execute(
                    text("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
                )
            ).scalar()
        assert bypass is False


async def test_the_application_role_can_insert_but_never_update_delete_or_truncate(
    migrated_database: DatabaseUnderTest,
) -> None:
    url = migrated_database.app_url
    event_id = await _insert_event(url, Realm.PLATFORM, None, realm="platform")

    async def run(sql: str) -> None:
        async with _as(url, Realm.PLATFORM) as (session, _):
            await session.execute(text(sql), {"id": event_id})

    assert await _visible(url, Realm.PLATFORM, None, [event_id]) == {event_id}
    for sql in (
        "UPDATE audit_events SET event_type = 'probe.forged' WHERE id = :id",
        "DELETE FROM audit_events WHERE id = :id",
        "TRUNCATE audit_events",
    ):
        message = await _error(run(sql))
        assert message is not None
        assert PERMISSION_DENIED in message, sql
    assert await _visible(url, Realm.PLATFORM, None, [event_id]) == {event_id}


async def test_triggers_keep_the_table_append_only_even_for_the_owner(
    migrated_database: DatabaseUnderTest,
) -> None:
    event_id = await _insert_event(migrated_database.app_url, Realm.SYSTEM, None, realm="system")

    async def run(sql: str) -> None:
        async with _engine(migrated_database.owner_url) as engine, engine.begin() as connection:
            await connection.execute(text(sql), {"id": event_id})

    for sql in (
        "UPDATE audit_events SET event_type = 'probe.forged' WHERE id = :id",
        "DELETE FROM audit_events WHERE id = :id",
        "TRUNCATE audit_events",
    ):
        message = await _error(run(sql))
        assert message is not None
        assert APPEND_ONLY in message, sql
    assert await _visible(migrated_database.app_url, Realm.PLATFORM, None, [event_id]) == {event_id}


async def test_the_readonly_role_cannot_read_or_write_audit_events(
    migrated_database: DatabaseUnderTest,
) -> None:
    url = migrated_database.readonly_url

    async def read() -> None:
        async with _engine(url) as engine, engine.connect() as connection:
            await connection.execute(text("SELECT count(*) FROM audit_events"))

    assert PERMISSION_DENIED in (await _error(read()) or "")
    assert PERMISSION_DENIED in (
        await _error(_insert_event(url, Realm.SYSTEM, None, realm="system")) or ""
    )


# --- Row-Level Security ------------------------------------------------------------------


@pytest.fixture
async def tenant_events(migrated_database: DatabaseUnderTest) -> dict[str, uuid.UUID]:
    """One event of tenant A, one of tenant B and one without tenant, each in its own context."""
    url = migrated_database.app_url
    return {
        "a": await _insert_event(url, Realm.TENANT, TENANT_A, tenant_id=TENANT_A),
        "b": await _insert_event(url, Realm.TENANT, TENANT_B, tenant_id=TENANT_B),
        "none": await _insert_event(url, Realm.SYSTEM, None, realm="system"),
    }


async def test_rls_is_enabled_with_the_three_policies(
    migrated_database: DatabaseUnderTest,
) -> None:
    enabled = await _owner_scalar(
        migrated_database,
        "SELECT relrowsecurity FROM pg_class WHERE oid = 'audit_events'::regclass",
    )
    policies = await _owner_scalar(
        migrated_database,
        "SELECT string_agg(policyname || ':' || cmd, ',' ORDER BY policyname) "
        "FROM pg_policies WHERE tablename = 'audit_events'",
    )

    assert enabled is True
    assert policies == (
        "audit_events_insert:INSERT,audit_events_platform_read:SELECT,"
        "audit_events_tenant_read:SELECT"
    )


async def test_a_tenant_reads_only_its_own_audit_events(
    migrated_database: DatabaseUnderTest, tenant_events: dict[str, uuid.UUID]
) -> None:
    ids = list(tenant_events.values())
    url = migrated_database.app_url

    assert await _visible(url, Realm.TENANT, TENANT_A, ids) == {tenant_events["a"]}
    assert await _visible(url, Realm.TENANT, TENANT_B, ids) == {tenant_events["b"]}
    # A tenant realm without a tenant context sees nothing (not the NULL rows).
    assert await _visible(url, Realm.TENANT, None, ids) == set()


async def test_the_platform_reads_every_tenant_and_the_platform_events(
    migrated_database: DatabaseUnderTest, tenant_events: dict[str, uuid.UUID]
) -> None:
    ids = list(tenant_events.values())

    assert await _visible(migrated_database.app_url, Realm.PLATFORM, None, ids) == set(ids)


@pytest.mark.parametrize("realm", [Realm.STUDENT, Realm.PUBLIC, Realm.WEBHOOK, Realm.SYSTEM])
async def test_other_realms_read_no_audit_events(
    migrated_database: DatabaseUnderTest, tenant_events: dict[str, uuid.UUID], realm: Realm
) -> None:
    ids = list(tenant_events.values())

    for tenant in (TENANT_A, None):
        assert await _visible(migrated_database.app_url, realm, tenant, ids) == set()


async def test_without_any_context_nothing_is_visible(
    migrated_database: DatabaseUnderTest, tenant_events: dict[str, uuid.UUID]
) -> None:
    async with _engine(migrated_database.app_url) as engine, engine.connect() as connection:
        visible = (
            await connection.execute(
                select(AUDIT_TABLE.c.id).where(AUDIT_TABLE.c.id.in_(tenant_events.values()))
            )
        ).all()

    assert visible == []


@pytest.mark.parametrize(
    ("context_tenant", "row_tenant", "allowed"),
    [
        (TENANT_A, TENANT_A, True),
        (TENANT_A, TENANT_B, False),
        (TENANT_A, None, False),
        (None, None, True),
        (None, TENANT_A, False),
    ],
    ids=["A->A", "A->B", "A->NULL", "NULL->NULL", "NULL->A"],
)
async def test_inserted_tenant_must_match_the_trusted_tenant_context(
    migrated_database: DatabaseUnderTest,
    context_tenant: uuid.UUID | None,
    row_tenant: uuid.UUID | None,
    allowed: bool,
) -> None:
    realm = Realm.TENANT if context_tenant else Realm.SYSTEM
    message = await _error(
        _insert_event(
            migrated_database.app_url,
            realm,
            context_tenant,
            tenant_id=row_tenant,
            realm=realm.value,
        )
    )

    if allowed:
        assert message is None
    else:
        assert message is not None
        assert RLS_VIOLATION in message


async def test_inserted_realm_must_match_the_trusted_realm(
    migrated_database: DatabaseUnderTest,
) -> None:
    message = await _error(
        _insert_event(migrated_database.app_url, Realm.PUBLIC, None, realm="platform")
    )

    assert message is not None
    assert RLS_VIOLATION in message


# --- Migration --------------------------------------------------------------------------


async def test_the_audit_migration_downgrades_and_upgrades_cleanly(
    migrated_database: DatabaseUnderTest,
) -> None:
    config = migrated_database.alembic_config()
    scripts = ScriptDirectory.from_config(config)
    audit_revision = scripts.get_revision("0002")
    assert audit_revision is not None
    head = scripts.get_current_head()
    objects = (
        "SELECT (SELECT count(*) FROM pg_class WHERE relname LIKE '%audit_events%') "
        "+ (SELECT count(*) FROM pg_proc WHERE proname = 'audit_events_reject_modification') "
        "+ (SELECT count(*) FROM pg_policies WHERE tablename = 'audit_events') "
        "+ (SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'audit_events_%')"
    )
    # table, pk, 3 indexes; function; 3 policies; 2 triggers
    expected = 1 + 1 + 3 + 1 + 3 + 2

    assert await _owner_scalar(migrated_database, objects) == expected
    await anyio.to_thread.run_sync(command.downgrade, config, str(audit_revision.down_revision))
    try:
        assert await _owner_scalar(migrated_database, objects) == 0
    finally:
        await anyio.to_thread.run_sync(command.upgrade, config, "head")

    assert await _owner_scalar(migrated_database, objects) == expected
    assert await _owner_scalar(migrated_database, "SELECT version_num FROM alembic_version") == head
    assert await _owner_scalar(
        migrated_database,
        "SELECT relrowsecurity FROM pg_class WHERE oid = 'audit_events'::regclass",
    )
    await anyio.to_thread.run_sync(command.check, config)


# --- The application: transactional writer and security events --------------------------


class ConnectionMonitor:
    """Counts pool checkouts and the highest number held at the same time."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.checkouts = 0
        self.held = 0
        self.max_held = 0
        event.listen(engine.sync_engine, "checkout", self._checkout)
        event.listen(engine.sync_engine, "checkin", self._checkin)

    def _checkout(self, *_: object) -> None:
        self.checkouts += 1
        self.held += 1
        self.max_held = max(self.max_held, self.held)

    def _checkin(self, *_: object) -> None:
        self.held -= 1


def _probe_app(url: str, database: DatabaseUnderTest) -> tuple[FastAPI, AsyncEngine]:
    """App whose pool holds ONE connection and fails fast instead of waiting for a second."""
    app = create_app(database.settings())
    engine = create_async_engine(url, pool_size=1, max_overflow=0, pool_timeout=3)
    app.state.engine = engine
    app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    router = realm_router(Realm.PUBLIC, access=Access.ANONYMOUS)

    @router.post("/probe/audit/{outcome}")
    async def audited(outcome: str, session: DbSession) -> dict[str, str]:
        await session.execute(text("INSERT INTO probe_audit_rows VALUES (:o)"), {"o": outcome})
        await write_audit_event(
            session,
            DOMAIN_EVENT,
            target=AuditTarget("probe_row"),
            metadata={"outcome": outcome, "password": SECRET},
        )
        if outcome == "fail":
            raise NotFoundError()
        if outcome == "forged-context":
            # The trusted tenant changes under the writer: RLS must refuse the
            # row, and the request must not report success.
            await apply_transaction_settings(session, realm="public", tenant_id=TENANT_A)
            await write_audit_event(session, DOMAIN_EVENT)
        return {"status": "ok"}

    @router.post("/probe/security/{outcome}")
    async def security(outcome: str, session: DbSession) -> dict[str, str]:
        await session.execute(text("INSERT INTO probe_audit_rows VALUES (:o)"), {"o": outcome})
        record_security_event(SECURITY_EVENT, metadata={"outcome": outcome, "access_token": SECRET})
        if outcome == "denied":
            raise PermissionDeniedError()
        return {"status": "ok"}

    @router.post("/probe/security-only")
    async def security_only() -> dict[str, str]:
        record_security_event(SECURITY_EVENT, metadata={"password": SECRET})
        return {"status": "ok"}

    @router.post("/probe/security-many/{count}")
    async def security_many(count: int) -> dict[str, str]:
        for _ in range(count):
            record_security_event(SECURITY_EVENT)
        return {"status": "ok"}

    @router.get("/probe/audit-rows")
    async def rows(session: DbSession) -> list[str]:
        result = await session.execute(text("SELECT name FROM probe_audit_rows ORDER BY name"))
        return list(result.scalars())

    app.include_router(router, prefix=REALM_PREFIXES[Realm.PUBLIC])

    tenant = realm_router(Realm.TENANT)

    @tenant.get("/probe/protected")
    async def protected() -> None:  # pragma: no cover - denied by the guard
        raise AssertionError("a guarded handler must not run")

    app.include_router(tenant, prefix=REALM_PREFIXES[Realm.TENANT])
    return app, engine


@pytest.fixture
async def audit_client(
    migrated_database: DatabaseUnderTest,
) -> AsyncIterator[tuple[AsyncClient, ConnectionMonitor]]:
    app, engine = _probe_app(migrated_database.app_url, migrated_database)
    # A temporary table lives on the pool's only connection.
    async with engine.begin() as connection:
        await connection.execute(text("CREATE TEMPORARY TABLE probe_audit_rows (name text)"))
    monitor = ConnectionMonitor(engine)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            yield client, monitor
    finally:
        await engine.dispose()


BASE = "/api/v1/public/probe"


async def test_the_audit_event_commits_with_the_mutation_in_the_same_transaction(
    migrated_database: DatabaseUnderTest, audit_client: tuple[AsyncClient, ConnectionMonitor]
) -> None:
    client, monitor = audit_client

    response = await client.post(f"{BASE}/audit/kept")

    assert response.status_code == 200
    assert monitor.checkouts == 1  # no second connection for the audit event
    [row] = await _events(migrated_database, response.headers["X-Request-ID"])
    assert (row.realm, row.tenant_id, row.principal_id) == ("public", None, None)
    assert (row.category, row.event_type, row.target_type) == (
        "domain",
        "probe.row_created",
        "probe_row",
    )
    assert row.metadata == {"outcome": "kept", "password": "[REDACTED]"}
    assert SECRET not in json.dumps(row.metadata)
    assert (await client.get(f"{BASE}/audit-rows")).json() == ["kept"]


async def test_a_rolled_back_request_keeps_neither_the_mutation_nor_its_audit_event(
    migrated_database: DatabaseUnderTest, audit_client: tuple[AsyncClient, ConnectionMonitor]
) -> None:
    client, _ = audit_client

    response = await client.post(f"{BASE}/audit/fail")

    assert response.status_code == 404
    assert await _events(migrated_database, response.headers["X-Request-ID"]) == []
    assert (await client.get(f"{BASE}/audit-rows")).json() == []


async def test_a_failed_audit_insert_fails_the_request_and_rolls_back_the_mutation(
    migrated_database: DatabaseUnderTest, audit_client: tuple[AsyncClient, ConnectionMonitor]
) -> None:
    client, _ = audit_client

    response = await client.post(f"{BASE}/audit/forged-context")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert await _events(migrated_database, response.headers["X-Request-ID"]) == []
    assert (await client.get(f"{BASE}/audit-rows")).json() == []


async def test_security_events_survive_the_rollback_and_flush_after_the_connection_is_released(
    migrated_database: DatabaseUnderTest, audit_client: tuple[AsyncClient, ConnectionMonitor]
) -> None:
    client, monitor = audit_client

    response = await client.post(f"{BASE}/security/denied")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"
    # One connection for the request transaction, then one for the flush —
    # never two at once (the pool has one connection and a 3 s timeout).
    assert (monitor.checkouts, monitor.max_held, monitor.held) == (2, 1, 0)
    assert (await client.get(f"{BASE}/audit-rows")).json() == []  # business change rolled back
    [row] = await _events(migrated_database, response.headers["X-Request-ID"])
    assert (row.category, row.event_type, row.realm, row.tenant_id) == (
        "security",
        "auth.probe_denied",
        "public",
        None,
    )
    assert row.metadata == {"outcome": "denied", "access_token": "[REDACTED]"}


async def test_security_events_of_a_successful_request_are_committed_separately(
    migrated_database: DatabaseUnderTest, audit_client: tuple[AsyncClient, ConnectionMonitor]
) -> None:
    client, monitor = audit_client

    response = await client.post(f"{BASE}/security/allowed")

    assert response.status_code == 200
    assert (monitor.checkouts, monitor.max_held) == (2, 1)
    assert len(await _events(migrated_database, response.headers["X-Request-ID"])) == 1
    assert (await client.get(f"{BASE}/audit-rows")).json() == ["allowed"]


async def test_requests_without_security_events_never_open_a_flush_transaction(
    audit_client: tuple[AsyncClient, ConnectionMonitor],
) -> None:
    client, monitor = audit_client

    denied = await client.get("/api/v1/probe/protected")

    assert denied.status_code == 401
    assert monitor.checkouts == 0  # the guard denied; its scope had nothing to flush

    public = await client.get(f"{BASE}/audit-rows")

    assert public.status_code == 200
    assert monitor.checkouts == 1  # the DbSession only


async def test_the_security_buffer_is_bounded_per_request(
    migrated_database: DatabaseUnderTest,
    audit_client: tuple[AsyncClient, ConnectionMonitor],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, _ = audit_client

    response = await client.post(f"{BASE}/security-many/40")

    assert response.status_code == 200
    assert len(await _events(migrated_database, response.headers["X-Request-ID"])) == 32
    [dropped] = [r for r in caplog.records if r.getMessage() == "audit.security_events_dropped"]
    assert dropped.__dict__["event_count"] == 8


async def test_the_flush_re_establishes_the_trusted_tenant_context(
    migrated_database: DatabaseUnderTest,
) -> None:
    context = RequestContext(realm=Realm.TENANT, request_id=uuid.uuid7(), tenant_id=TENANT_A)
    buffer = SecurityEventBuffer(context=context)
    buffer.rows.append(audit_row(context, SECURITY_EVENT))
    async with _engine(migrated_database.app_url) as engine:
        await flush_security_events(async_sessionmaker(engine), buffer)

    [row] = await _events(migrated_database, str(context.request_id))
    assert (row.realm, row.tenant_id) == ("tenant", TENANT_A)
    assert await _visible(migrated_database.app_url, Realm.TENANT, TENANT_A, [row.id]) == {row.id}
    assert await _visible(migrated_database.app_url, Realm.TENANT, TENANT_B, [row.id]) == set()


async def test_a_client_supplied_tenant_cannot_override_the_trusted_context(
    migrated_database: DatabaseUnderTest,
) -> None:
    # A buffered row claiming another tenant than its trusted context is refused
    # by RLS at flush time (and the flush failure is swallowed).
    context = RequestContext(realm=Realm.TENANT, request_id=uuid.uuid7(), tenant_id=TENANT_A)
    buffer = SecurityEventBuffer(context=context)
    buffer.rows.append(audit_row(context, SECURITY_EVENT) | {"tenant_id": TENANT_B})
    async with _engine(migrated_database.app_url) as engine:
        await flush_security_events(async_sessionmaker(engine), buffer)

    assert await _events(migrated_database, str(context.request_id)) == []


async def test_a_failed_flush_is_logged_safely_and_does_not_change_the_response(
    migrated_database: DatabaseUnderTest,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The read-only role cannot insert audit events: the flush fails for real.
    # Built inside the test so that its log handler writes to the captured stdout.
    app, engine = _probe_app(migrated_database.readonly_url, migrated_database)
    caplog.set_level(logging.INFO)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            response = await client.post(f"{BASE}/security-only")
    finally:
        await engine.dispose()

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert await _events(migrated_database, response.headers["X-Request-ID"]) == []
    [failure] = [r for r in caplog.records if r.getMessage() == "audit.security_flush_failed"]
    assert failure.levelno == logging.ERROR
    assert failure.__dict__["event_count"] == 1
    assert failure.__dict__["error_type"]
    assert failure.exc_info is None
    # The JSON lines the application actually wrote (stdout handler).
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line]
    [logged] = [line for line in lines if line["message"] == "audit.security_flush_failed"]
    assert logged["request_id"] == response.headers["X-Request-ID"]
    assert logged["realm"] == "public"
    assert set(logged) == {
        "timestamp",
        "level",
        "logger",
        "message",
        "request_id",
        "realm",
        "event_count",
        "error_type",
    }
    for line in lines:
        assert SECRET not in json.dumps(line)
        assert "INSERT" not in json.dumps(line)
    for record in caplog.records:
        assert SECRET not in JsonFormatter().format(record)
