"""Platform identity and MFA schema with Row-Level Security (T01-06; migration 0006).

Raw SQL through the real runtime roles and trusted ``SET LOCAL`` settings, so
only the database protects the rows:

* platform tables are invisible to tenant contexts and to the read-only role;
* each platform pre-authentication key reaches exactly the row it names;
* credentials, MFA factors, recovery codes, sessions and reset tokens are
  visible only for the platform principal's own rows, or for the target of an
  authorized MFA reset;
* tenant MFA factors and recovery codes are visible only to their user.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import anyio
import pytest
from alembic import command
from conftest import DatabaseUnderTest
from identity_support import World, build_world
from platform_support import PlatformWorld, build_platform_world
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.context import Realm, RequestContext
from app.core.db import create_sessionmaker
from app.core.db.session import context_transaction

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

HASH = "$argon2id$v=19$m=8,t=1,p=1$c29tZXNhbHQ$aGFzaGhhc2hoYXNo"
PLATFORM_TABLES = (
    "platform_users",
    "platform_user_credentials",
    "platform_user_roles",
    "platform_sessions",
    "platform_mfa_factors",
    "platform_recovery_codes",
    "platform_password_reset_tokens",
)
TENANT_TABLES = ("user_mfa_factors", "user_recovery_codes")
PERMISSION_DENIED = "permission denied"
RLS_VIOLATION = "row-level security"


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
async def pworld(app_db: async_sessionmaker[AsyncSession]) -> PlatformWorld:
    return await build_platform_world(app_db, password_hash=HASH)


@pytest.fixture
async def world(app_db: async_sessionmaker[AsyncSession]) -> World:
    return await build_world(app_db)


async def _run(
    factory: async_sessionmaker[AsyncSession],
    sql: str,
    *,
    realm: Realm = Realm.PLATFORM,
    principal: uuid.UUID | None = None,
    tenant: uuid.UUID | None = None,
    keys: dict[str, str] | None = None,
    **params: Any,
) -> Any:
    """``sql`` with a trusted context (and optional lookup keys): rows or a row count."""
    context = RequestContext(
        realm=realm, request_id=uuid.uuid7(), principal_id=principal, tenant_id=tenant
    )
    async with context_transaction(factory, context) as db:
        for name, value in (keys or {}).items():
            await db.execute(
                text("SELECT set_config(:n, :v, true)"), {"n": f"app.{name}", "v": value}
            )
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


async def _session(factory: async_sessionmaker[AsyncSession], user: uuid.UUID) -> str:
    """A platform session row for ``user``; returns its token hash."""
    token_hash = uuid.uuid7().hex + uuid.uuid7().hex
    now = datetime.now(UTC)
    await _run(
        factory,
        "INSERT INTO platform_sessions (id, token_hash, platform_user_id, last_seen_at, "
        "idle_expires_at, absolute_expires_at) VALUES (:id, :h, :u, :now, :exp, :exp)",
        principal=user,
        id=uuid.uuid7(),
        h=token_hash,
        u=user,
        now=now,
        exp=now + timedelta(minutes=5),
    )
    return token_hash


async def _factor(factory: async_sessionmaker[AsyncSession], user: uuid.UUID) -> uuid.UUID:
    factor_id = uuid.uuid7()
    await _run(
        factory,
        "INSERT INTO platform_mfa_factors (id, platform_user_id, kind, secret_ciphertext) "
        "VALUES (:id, :u, 'totp', 'v1:k:x:y')",
        principal=user,
        id=factor_id,
        u=user,
    )
    return factor_id


# --- Migration, privileges, RLS presence ------------------------------------------------------


async def test_the_platform_migration_downgrades_and_upgrades_cleanly(
    migrated_database: DatabaseUnderTest,
) -> None:
    config = migrated_database.alembic_config()
    tables = [*PLATFORM_TABLES, *TENANT_TABLES]
    objects = (
        "SELECT (SELECT count(*) FROM pg_class WHERE relname = ANY(:tables) AND relkind = 'r') "
        "+ (SELECT count(*) FROM pg_policies WHERE tablename = ANY(:tables)) "
        "+ (SELECT count(*) FROM information_schema.columns WHERE table_name = 'user_sessions' "
        "   AND column_name IN ('mfa_pending', 'mfa_failed_attempts'))"
    )
    present = (await _owner(migrated_database, objects, tables=tables))[0][0]
    await anyio.to_thread.run_sync(command.downgrade, config, "0005")
    try:
        assert (await _owner(migrated_database, objects, tables=tables))[0][0] == 0
    finally:
        await anyio.to_thread.run_sync(command.upgrade, config, "head")
    # 9 tables, 27 policies (7 platform tables: 21; 2 tenant tables: 6), 2 columns.
    assert present == 9 + 27 + 2


async def test_privileges_and_rls_presence(migrated_database: DatabaseUnderTest) -> None:
    rows = await _owner(
        migrated_database,
        "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
        "has_table_privilege(:app, c.oid, 'DELETE'), "
        "has_table_privilege(:app, c.oid, 'UPDATE'), "
        "has_table_privilege(:ro, c.oid, 'SELECT') "
        "FROM pg_class c WHERE c.relname = ANY(:tables) AND c.relkind = 'r'",
        app=_user(migrated_database.app_url),
        ro=_user(migrated_database.readonly_url),
        tables=[*PLATFORM_TABLES, *TENANT_TABLES],
    )
    by_table = {row[0]: tuple(row[1:]) for row in rows}
    for table in (*PLATFORM_TABLES, *TENANT_TABLES):
        roles = table == "platform_user_roles"
        # RLS on, not forced; DELETE only for role assignments; UPDATE except roles;
        # nothing for the read-only role.
        assert by_table[table] == (True, False, roles, not roles, False), table


def _user(url: str) -> str:
    from sqlalchemy.engine import make_url

    name = make_url(url).username
    assert name
    return name


# --- Realm isolation ------------------------------------------------------------------------


async def test_tenant_contexts_and_the_readonly_role_see_no_platform_row(
    app_db: async_sessionmaker[AsyncSession],
    readonly_db: async_sessionmaker[AsyncSession],
    pworld: PlatformWorld,
    world: World,
) -> None:
    nora = pworld.users["nora"]
    await _session(app_db, nora)
    await _factor(app_db, nora)
    tenant: dict[str, Any] = {
        "realm": Realm.TENANT,
        "principal": world.users["alice"],
        "tenant": world.tenant_a,
    }
    for table in PLATFORM_TABLES:
        assert await _run(app_db, f"SELECT 1 FROM {table}", **tenant) == set()  # noqa: S608
        # Even with platform lookup keys published in a tenant context.
        keyed = await _run(
            app_db,
            f"SELECT 1 FROM {table}",  # noqa: S608
            keys={"platform_auth_email": pworld.email("nora"), "platform_user_id": str(nora)},
            **tenant,
        )
        assert keyed == set(), table
        assert PERMISSION_DENIED in await _error(
            _run(readonly_db, f"SELECT 1 FROM {table}")  # noqa: S608
        )


async def test_an_anonymous_platform_context_sees_nothing(
    app_db: async_sessionmaker[AsyncSession], pworld: PlatformWorld
) -> None:
    for table in PLATFORM_TABLES:
        assert await _run(app_db, f"SELECT 1 FROM {table}") == set()  # noqa: S608


async def test_platform_users_are_created_only_by_the_system_realm(
    app_db: async_sessionmaker[AsyncSession], pworld: PlatformWorld
) -> None:
    error = await _error(
        _run(
            app_db,
            "INSERT INTO platform_users (id, email, display_name, status, version) "
            "VALUES (:id, 'intruder@mti360-platform.example', 'Intruder', 'ACTIVE', 1)",
            principal=pworld.users["nora"],
            id=uuid.uuid7(),
        )
    )
    assert RLS_VIOLATION in error
    role = await _error(
        _run(
            app_db,
            "INSERT INTO platform_user_roles (id, platform_user_id, role_code) "
            "VALUES (:id, :u, 'SUPER_ADMIN')",
            principal=pworld.users["pia"],
            id=uuid.uuid7(),
            u=pworld.users["pia"],
        )
    )
    assert RLS_VIOLATION in role


# --- Pre-authentication lookup keys ---------------------------------------------------------


async def test_the_email_key_reaches_exactly_one_identity_and_credential(
    app_db: async_sessionmaker[AsyncSession], pworld: PlatformWorld
) -> None:
    keys = {"platform_auth_email": pworld.email("omar")}
    users = await _run(app_db, "SELECT id FROM platform_users", keys=keys)
    credentials = await _run(
        app_db, "SELECT platform_user_id FROM platform_user_credentials", keys=keys
    )
    assert users == credentials == {pworld.users["omar"]}
    # Nothing else is reachable with it.
    for table in ("platform_sessions", "platform_mfa_factors", "platform_user_roles"):
        assert await _run(app_db, f"SELECT 1 FROM {table}", keys=keys) == set()  # noqa: S608


async def test_the_session_and_reset_keys_reach_exactly_their_row(
    app_db: async_sessionmaker[AsyncSession], pworld: PlatformWorld
) -> None:
    nora_hash = await _session(app_db, pworld.users["nora"])
    await _session(app_db, pworld.users["omar"])
    sessions = await _run(
        app_db,
        "SELECT platform_user_id FROM platform_sessions",
        keys={"platform_session_token_hash": nora_hash},
    )
    assert sessions == {pworld.users["nora"]}
    reset_hash = uuid.uuid7().hex * 2
    await _run(
        app_db,
        "INSERT INTO platform_password_reset_tokens (id, platform_user_id, token_hash, "
        "expires_at) VALUES (:id, :u, :h, now() + interval '30 minutes')",
        principal=pworld.users["pia"],
        id=uuid.uuid7(),
        u=pworld.users["pia"],
        h=reset_hash,
    )
    tokens = await _run(
        app_db,
        "SELECT platform_user_id FROM platform_password_reset_tokens",
        keys={"platform_auth_token_hash": reset_hash},
    )
    assert tokens == {pworld.users["pia"]}


# --- platform_user_id isolation -------------------------------------------------------------


async def test_a_platform_principal_reaches_only_its_own_secrets(
    app_db: async_sessionmaker[AsyncSession], pworld: PlatformWorld
) -> None:
    nora, omar = pworld.users["nora"], pworld.users["omar"]
    await _session(app_db, nora)
    await _session(app_db, omar)
    nora_factor = await _factor(app_db, nora)
    omar_factor = await _factor(app_db, omar)
    as_nora: dict[str, Any] = {"principal": nora}
    # The directory (identities and role codes) is visible to any platform principal ...
    users = await _run(app_db, "SELECT id FROM platform_users", **as_nora)
    assert {nora, omar, pworld.users["pia"]} <= users
    roles = await _run(app_db, "SELECT platform_user_id FROM platform_user_roles", **as_nora)
    assert omar in roles
    # ... but credentials, sessions and factors only for the principal itself.
    for table in ("platform_user_credentials", "platform_sessions", "platform_mfa_factors"):
        owners = await _run(app_db, f"SELECT platform_user_id FROM {table}", **as_nora)  # noqa: S608
        assert owners == {nora}, table
    changed = await _run(
        app_db,
        "UPDATE platform_mfa_factors SET disabled_at = now(), disabled_reason = 'x' WHERE id = :f",
        f=omar_factor,
        **as_nora,
    )
    assert changed == 0
    # Inserting a factor or a session for someone else is refused.
    foreign = await _error(
        _run(
            app_db,
            "INSERT INTO platform_mfa_factors (id, platform_user_id, kind, secret_ciphertext) "
            "VALUES (:id, :u, 'totp', 'v1:k:x:y')",
            principal=nora,
            id=uuid.uuid7(),
            u=omar,
        )
    )
    assert RLS_VIOLATION in foreign
    assert await _run(app_db, "SELECT id FROM platform_mfa_factors", **as_nora) == {nora_factor}
    # A principal can update only its own identity row.
    renamed = await _run(
        app_db, "UPDATE platform_users SET display_name = 'X' WHERE id = :u", u=omar, **as_nora
    )
    assert renamed == 0


async def test_the_reset_target_key_opens_only_the_targets_mfa_and_sessions(
    app_db: async_sessionmaker[AsyncSession], pworld: PlatformWorld
) -> None:
    nora, omar, pia = pworld.users["nora"], pworld.users["omar"], pworld.users["pia"]
    omar_factor = await _factor(app_db, omar)
    await _factor(app_db, pia)
    await _session(app_db, omar)
    target: dict[str, Any] = {
        "principal": nora,
        "keys": {"platform_mfa_reset_user_id": str(omar)},
    }
    factors = await _run(app_db, "SELECT platform_user_id FROM platform_mfa_factors", **target)
    assert factors <= {nora, omar}
    assert omar in factors
    sessions = await _run(app_db, "SELECT platform_user_id FROM platform_sessions", **target)
    assert pia not in sessions
    credentials = await _run(
        app_db, "SELECT platform_user_id FROM platform_user_credentials", **target
    )
    assert omar not in credentials
    disabled = await _run(
        app_db,
        "UPDATE platform_mfa_factors SET disabled_at = now(), disabled_reason = 'admin_reset' "
        "WHERE id = :f",
        f=omar_factor,
        **target,
    )
    assert disabled == 1
    # Without a principal the target key opens nothing.
    anonymous = await _run(
        app_db,
        "SELECT 1 FROM platform_mfa_factors",
        keys={"platform_mfa_reset_user_id": str(omar)},
    )
    assert anonymous == set()


async def test_one_live_factor_per_platform_user(
    app_db: async_sessionmaker[AsyncSession], pworld: PlatformWorld
) -> None:
    await _factor(app_db, pworld.users["pia"])
    assert "duplicate key" in await _error(_factor(app_db, pworld.users["pia"]))


# --- Tenant MFA -----------------------------------------------------------------------------


async def test_tenant_mfa_rows_are_visible_only_to_their_user(
    app_db: async_sessionmaker[AsyncSession], world: World, pworld: PlatformWorld
) -> None:
    alice, bob = world.users["alice"], world.users["bob"]
    insert_factor = (
        "INSERT INTO user_mfa_factors (id, user_id, kind, secret_ciphertext) "
        "VALUES (:id, :u, 'totp', 'v1:k:x:y')"
    )
    tenant: dict[str, Any] = {"realm": Realm.TENANT, "tenant": world.tenant_a}
    await _run(app_db, insert_factor, principal=alice, id=uuid.uuid7(), u=alice, **tenant)
    assert RLS_VIOLATION in await _error(
        _run(app_db, insert_factor, principal=bob, id=uuid.uuid7(), u=alice, **tenant)
    )
    as_bob = await _run(
        app_db,
        "SELECT user_id FROM user_mfa_factors WHERE user_id = :u",
        principal=bob,
        u=alice,
        **tenant,
    )
    assert as_bob == set()
    as_alice = await _run(
        app_db,
        "SELECT user_id FROM user_mfa_factors WHERE user_id = :u",
        principal=alice,
        u=alice,
        **tenant,
    )
    assert as_alice == {alice}
    as_platform = await _run(
        app_db,
        "SELECT 1 FROM user_mfa_factors WHERE user_id = :u",
        principal=pworld.users["nora"],
        u=alice,
    )
    assert as_platform == set()


async def test_a_pending_tenant_session_has_no_tenant(
    migrated_database: DatabaseUnderTest, world: World
) -> None:
    now = datetime.now(UTC)
    error = await _error(
        _owner(
            migrated_database,
            "INSERT INTO user_sessions (id, token_hash, user_id, realm, active_tenant_id, "
            "mfa_pending, last_seen_at, idle_expires_at, absolute_expires_at) "
            "VALUES (:id, :h, :u, 'tenant', :t, true, :now, :now, :now)",
            id=uuid.uuid7(),
            h=uuid.uuid7().hex * 2,
            u=world.users["alice"],
            t=world.tenant_a,
            now=now,
        )
    )
    assert "check constraint" in error
