"""Identity schema and Row-Level Security against real PostgreSQL (T01-04; migration 0004).

Constraints, privileges and the RLS matrix of every identity table, through
the real runtime roles and the trusted ``SET LOCAL`` context, with raw SQL so
only the database protects the rows. The pre-authentication lookup keys
(decision D01) are proven to reach exactly one row each and nothing else.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import anyio
import pytest
from alembic import command
from alembic.script import ScriptDirectory
from conftest import DatabaseUnderTest
from identity_support import (
    World,
    add_invitation,
    add_reset_token,
    add_session,
    build_world,
)
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.context import Realm, RequestContext
from app.core.db import create_sessionmaker
from app.core.db.session import context_transaction
from app.modules.identity.lookup import LookupKey, lookup_transaction
from app.modules.identity.tokens import TokenPurpose, token_hash

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

IDENTITY_REVISION = "0004"
TABLES = (
    "users",
    "user_credentials",
    "tenant_memberships",
    "membership_campuses",
    "user_sessions",
    "password_reset_tokens",
    "user_invitations",
)
SECRET = "mti360-test-session-secret-0123456789abcdef"
PERMISSION_DENIED = "permission denied"
RLS_VIOLATION = "row-level security"


@asynccontextmanager
async def _factory(url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(url, poolclass=NullPool)
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
async def world(app_db: async_sessionmaker[AsyncSession]) -> World:
    return await build_world(app_db)


async def _owner_scalar(database: DatabaseUnderTest, sql: str, **params: Any) -> Any:
    engine = create_async_engine(database.owner_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return (await connection.execute(text(sql), params)).scalar()
    finally:
        await engine.dispose()


async def _rows(
    factory: async_sessionmaker[AsyncSession],
    sql: str,
    *,
    user: uuid.UUID | None = None,
    tenant: uuid.UUID | None = None,
    realm: Realm = Realm.TENANT,
    **params: Any,
) -> set[Any]:
    """First column of ``sql`` as the role of ``factory`` with a trusted context."""
    context = RequestContext(
        realm=realm, request_id=uuid.uuid7(), principal_id=user, tenant_id=tenant
    )
    async with context_transaction(factory, context) as db:
        return set((await db.execute(text(sql), params)).scalars())


async def _lookup_rows(
    factory: async_sessionmaker[AsyncSession], key: LookupKey, sql: str, **params: Any
) -> set[Any]:
    async with lookup_transaction(factory, request_id=uuid.uuid7(), key=key) as db:
        return set((await db.execute(text(sql), params)).scalars())


async def _error(coroutine: Any) -> str:
    try:
        await coroutine
    except DBAPIError as error:
        return str(error.orig).lower()
    return ""


# --- Migration, privileges, RLS presence ---------------------------------------------------


async def test_the_identity_migration_downgrades_and_upgrades_cleanly(
    migrated_database: DatabaseUnderTest,
) -> None:
    config = migrated_database.alembic_config()
    scripts = ScriptDirectory.from_config(config)
    revision = scripts.get_revision(IDENTITY_REVISION)
    assert revision is not None
    objects = (
        "SELECT (SELECT count(*) FROM pg_class WHERE relname = ANY(:tables)) "
        "+ (SELECT count(*) FROM pg_policies WHERE tablename = ANY(:tables) "
        "   OR policyname = 'tenants_member_read')"
    )
    present = await _owner_scalar(migrated_database, objects, tables=list(TABLES))

    await anyio.to_thread.run_sync(command.downgrade, config, str(revision.down_revision))
    try:
        assert await _owner_scalar(migrated_database, objects, tables=list(TABLES)) == 0
    finally:
        await anyio.to_thread.run_sync(command.upgrade, config, "head")

    assert present == len(TABLES) + 21
    assert await _owner_scalar(migrated_database, objects, tables=list(TABLES)) == present
    assert (
        await _owner_scalar(migrated_database, "SELECT version_num FROM alembic_version")
        == scripts.get_current_head()
    )
    await anyio.to_thread.run_sync(command.check, config)


async def test_runtime_privileges_have_no_delete_and_readonly_has_nothing(
    migrated_database: DatabaseUnderTest,
) -> None:
    roles = migrated_database.roles
    for table in TABLES:
        granted = {
            key: {
                privilege
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE")
                if await _owner_scalar(
                    migrated_database,
                    "SELECT has_table_privilege(:role, :table, :privilege)",
                    role=roles[key],
                    table=table,
                    privilege=privilege,
                )
            }
            for key in ("app", "readonly")
        }
        expected = (
            {"SELECT", "INSERT"}
            if table == "membership_campuses"
            else {"SELECT", "INSERT", "UPDATE"}
        )
        assert granted == {"app": expected, "readonly": set()}, table


async def test_rls_is_enabled_and_not_forced_on_every_identity_table(
    migrated_database: DatabaseUnderTest,
) -> None:
    flags = await _owner_scalar(
        migrated_database,
        "SELECT bool_and(relrowsecurity) AND NOT bool_or(relforcerowsecurity) FROM pg_class "
        "WHERE relname = ANY(:tables)",
        tables=list(TABLES),
    )
    definer = await _owner_scalar(
        migrated_database,
        "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = 'public' AND p.prosecdef",
    )

    assert flags is True
    assert definer == 0  # no SECURITY DEFINER shortcut (D01)


# --- Constraints ---------------------------------------------------------------------------


async def test_identity_constraints(app_db: async_sessionmaker[AsyncSession], world: World) -> None:
    async def system(sql: str, **params: Any) -> str:
        async def run() -> None:
            context = RequestContext(realm=Realm.SYSTEM, request_id=uuid.uuid7())
            async with context_transaction(app_db, context) as db:
                await db.execute(text(sql), params)

        return await _error(run())

    insert_user = (
        "INSERT INTO users (id, email, display_name, status, version) "
        "VALUES (:id, :email, 'Probe', :status, 1)"
    )
    assert "check constraint" in await system(
        insert_user, id=uuid.uuid7(), email="Mixed.Case@x.example", status="ACTIVE"
    )
    assert "check constraint" in await system(
        insert_user, id=uuid.uuid7(), email=f"probe.{world.suffix}@x.example", status="LOCKED"
    )
    assert "duplicate key" in await system(
        insert_user, id=uuid.uuid7(), email=world.email("alice"), status="ACTIVE"
    )
    # One credential per user.
    assert "duplicate key" in await system(
        "INSERT INTO user_credentials (id, user_id, password_hash, password_changed_at) "
        "VALUES (:id, :user, 'x', now())",
        id=uuid.uuid7(),
        user=world.users["alice"],
    )
    # One membership per user and tenant.
    assert "duplicate key" in await system(
        "INSERT INTO tenant_memberships (id, tenant_id, user_id, status, campus_scope, version) "
        "VALUES (:id, :tenant, :user, 'ACTIVE', 'ALL', 1)",
        id=uuid.uuid7(),
        tenant=world.tenant_a,
        user=world.users["alice"],
    )
    # A membership campus must be a campus of the membership's tenant.
    assert "foreign key" in await system(
        "INSERT INTO membership_campuses (id, tenant_id, membership_id, campus_id) "
        "VALUES (:id, :tenant, :membership, :campus)",
        id=uuid.uuid7(),
        tenant=world.tenant_a,
        membership=world.memberships["alice_a"],
        campus=world.campus_b1,
    )
    session_sql = (
        "INSERT INTO user_sessions (id, token_hash, user_id, realm, active_tenant_id, "
        "active_campus_id, last_seen_at, idle_expires_at, absolute_expires_at) VALUES "
        "(:id, :hash, :user, 'tenant', :tenant, :campus, now(), now(), now() + interval '1 hour')"
    )
    # The active tenant must be one of the user's memberships ...
    assert "foreign key" in await system(
        session_sql,
        id=uuid.uuid7(),
        hash="a" * 64,
        user=world.users["carol"],
        tenant=world.tenant_a,
        campus=None,
    )
    # ... and the active campus a campus of the active tenant.
    assert "foreign key" in await system(
        session_sql,
        id=uuid.uuid7(),
        hash="b" * 64,
        user=world.users["alice"],
        tenant=world.tenant_a,
        campus=world.campus_b1,
    )
    # Only the server's hash format is stored.
    assert "check constraint" in await system(
        session_sql,
        id=uuid.uuid7(),
        hash="raw-token-value",
        user=world.users["alice"],
        tenant=None,
        campus=None,
    )


# --- Row-Level Security matrix -------------------------------------------------------------

USERS_SQL = "SELECT id FROM users WHERE id = ANY(:ids)"
CREDENTIALS_SQL = "SELECT user_id FROM user_credentials WHERE user_id = ANY(:ids)"
MEMBERSHIPS_SQL = "SELECT id FROM tenant_memberships WHERE id = ANY(:ids)"


async def test_users_are_visible_only_to_themselves_their_active_tenant_and_system(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    ids = list(world.users.values())
    u = world.users

    assert await _rows(app_db, USERS_SQL, ids=ids) == set()
    assert await _rows(app_db, USERS_SQL, user=u["erin"], ids=ids) == {u["erin"]}
    assert await _rows(app_db, USERS_SQL, tenant=world.tenant_a, ids=ids) == {
        u["alice"],
        u["bob"],
        u["dave"],
    }
    assert await _rows(app_db, USERS_SQL, tenant=world.tenant_b, ids=ids) == {u["bob"], u["carol"]}
    assert await _rows(app_db, USERS_SQL, realm=Realm.SYSTEM, ids=ids) == set(ids)
    assert await _rows(app_db, USERS_SQL, realm=Realm.PLATFORM, ids=ids) == set()


async def test_credentials_are_never_visible_to_a_tenant_context(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    ids = list(world.users.values())
    u = world.users

    for tenant in (world.tenant_a, world.tenant_b):
        assert await _rows(app_db, CREDENTIALS_SQL, tenant=tenant, ids=ids) == set()
    assert await _rows(app_db, CREDENTIALS_SQL, user=u["bob"], tenant=world.tenant_a, ids=ids) == {
        u["bob"]
    }
    # A user cannot change someone else's credential, even inside their tenant.
    async with context_transaction(
        app_db,
        RequestContext(
            realm=Realm.TENANT,
            request_id=uuid.uuid7(),
            principal_id=u["bob"],
            tenant_id=world.tenant_a,
        ),
    ) as db:
        changed = await db.execute(
            text("UPDATE user_credentials SET password_hash = 'x' WHERE user_id = :id"),
            {"id": u["alice"]},
        )
    assert changed.rowcount == 0  # type: ignore[attr-defined]


async def test_the_email_lookup_key_reaches_exactly_one_identity(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    ids = list(world.users.values())
    key = LookupKey.email(world.email("alice"))

    assert await _lookup_rows(app_db, key, USERS_SQL, ids=ids) == {world.users["alice"]}
    assert await _lookup_rows(app_db, key, CREDENTIALS_SQL, ids=ids) == {world.users["alice"]}
    # Nothing else: no memberships, sessions or tenants through the email key.
    assert (
        await _lookup_rows(app_db, key, MEMBERSHIPS_SQL, ids=list(world.memberships.values()))
        == set()
    )
    assert (
        await _lookup_rows(
            app_db,
            key,
            "SELECT id FROM tenants WHERE id = ANY(:ids)",
            ids=[world.tenant_a, world.tenant_b],
        )
        == set()
    )
    with pytest.raises(ValueError, match="canonical"):
        LookupKey.email("Alice@Example.com")  # must already be canonical
    with pytest.raises(ValueError, match="server-computed"):
        LookupKey.token_hash("' OR true --")


async def test_memberships_are_visible_by_active_tenant_or_own_user(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    m = world.memberships
    ids = list(m.values())

    assert await _rows(app_db, MEMBERSHIPS_SQL, ids=ids) == set()
    assert await _rows(app_db, MEMBERSHIPS_SQL, tenant=world.tenant_b, ids=ids) == {
        m["bob_b"],
        m["carol_b"],
    }
    # Before a tenant is active, a user discovers only their own memberships.
    assert await _rows(app_db, MEMBERSHIPS_SQL, user=world.users["bob"], ids=ids) == {
        m["bob_a"],
        m["bob_b"],
    }
    # The member-read policy on tenants follows the same rule.
    tenants = await _rows(
        app_db,
        "SELECT id FROM tenants WHERE id = ANY(:ids)",
        user=world.users["carol"],
        ids=[world.tenant_a, world.tenant_b],
    )
    assert tenants == {world.tenant_b}


async def test_membership_campuses_follow_tenant_and_own_membership(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    sql = "SELECT membership_id FROM membership_campuses WHERE membership_id = ANY(:ids)"
    ids = [world.memberships["bob_a"], world.memberships["dave_a"]]

    assert await _rows(app_db, sql, tenant=world.tenant_b, ids=ids) == set()
    assert await _rows(app_db, sql, tenant=world.tenant_a, ids=ids) == set(ids)
    assert await _rows(app_db, sql, user=world.users["bob"], ids=ids) == {
        world.memberships["bob_a"]
    }


async def test_sessions_are_visible_to_their_user_or_their_token_only(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    session_a, token_a = await add_session(app_db, world, "alice", tenant_id=world.tenant_a)
    session_c, _ = await add_session(app_db, world, "carol", tenant_id=world.tenant_b)
    sql = "SELECT id FROM user_sessions WHERE id = ANY(:ids)"
    ids = [session_a, session_c]

    assert await _rows(app_db, sql, tenant=world.tenant_a, ids=ids) == set()
    assert await _rows(app_db, sql, user=world.users["alice"], ids=ids) == {session_a}
    key = LookupKey.session_token_hash(token_hash(SECRET, TokenPurpose.SESSION, token_a))
    assert await _lookup_rows(app_db, key, sql, ids=ids) == {session_a}


async def test_reset_tokens_and_invitations_are_reachable_only_by_their_hash(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    reset_id, reset_token = await add_reset_token(app_db, world, "alice")
    invitation_id, invitation_token = await add_invitation(
        app_db, world, "frank", tenant_id=world.tenant_a, new_account=True
    )
    reset_sql = "SELECT id FROM password_reset_tokens WHERE id = :id"
    invitation_sql = "SELECT id FROM user_invitations WHERE id = :id"
    reset_key = LookupKey.token_hash(token_hash(SECRET, TokenPurpose.PASSWORD_RESET, reset_token))
    invitation_key = LookupKey.token_hash(
        token_hash(SECRET, TokenPurpose.INVITATION, invitation_token)
    )

    assert await _rows(app_db, reset_sql, tenant=world.tenant_a, id=reset_id) == set()
    assert await _lookup_rows(app_db, reset_key, reset_sql, id=reset_id) == {reset_id}
    assert await _rows(app_db, invitation_sql, tenant=world.tenant_b, id=invitation_id) == set()
    assert await _rows(app_db, invitation_sql, tenant=world.tenant_a, id=invitation_id) == {
        invitation_id
    }
    assert await _lookup_rows(app_db, invitation_key, invitation_sql, id=invitation_id) == {
        invitation_id
    }
    # The invitation key reveals its membership and tenant name, nothing more.
    membership = world.memberships[f"frank_invited_{world.tenant_a.hex[-4:]}"]
    assert await _lookup_rows(
        app_db, invitation_key, MEMBERSHIPS_SQL, ids=list(world.memberships.values())
    ) == {membership}
    assert await _lookup_rows(
        app_db,
        invitation_key,
        "SELECT id FROM tenants WHERE id = ANY(:ids)",
        ids=[world.tenant_a, world.tenant_b],
    ) == {world.tenant_a}


async def test_identities_are_created_only_by_the_system_realm(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    async def insert_as(user: uuid.UUID | None, tenant: uuid.UUID | None) -> None:
        context = RequestContext(
            realm=Realm.TENANT, request_id=uuid.uuid7(), principal_id=user, tenant_id=tenant
        )
        async with context_transaction(app_db, context) as db:
            await db.execute(
                text(
                    "INSERT INTO users (id, email, display_name, status, version) "
                    "VALUES (:id, :email, 'Rogue', 'ACTIVE', 1)"
                ),
                {"id": uuid.uuid7(), "email": f"rogue.{uuid.uuid7().hex[-6:]}@x.example"},
            )

    assert RLS_VIOLATION in await _error(insert_as(world.users["alice"], world.tenant_a))
    assert RLS_VIOLATION in await _error(insert_as(None, None))


async def test_the_readonly_role_cannot_read_identity_tables(
    migrated_database: DatabaseUnderTest,
) -> None:
    async with _factory(migrated_database.readonly_url) as factory:
        for table in TABLES:
            message = await _error(
                _rows(factory, f"SELECT count(*) FROM {table}", realm=Realm.SYSTEM)  # noqa: S608
            )
            assert PERMISSION_DENIED in message, table
