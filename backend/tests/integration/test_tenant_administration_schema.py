"""Tenant administration schema and Row-Level Security (T01-08; migration 0008).

Raw SQL through the real runtime roles and trusted ``SET LOCAL`` settings, so
only the database protects the rows:

* D8-1: a tenant transaction inserts a ``users`` row only for the one
  ``INVITED`` identity named by ``app.tenant_invitee_user_id`` — never another
  ID, another status, without a principal or from another realm;
* D8-2: tenant readers see only tenant-realm events of their tenant, never a
  platform-written event carrying their tenant's ID;
* campus scope: ``membership_campuses`` rows are updated (``removed_at``)
  within the tenant and never deleted (T01-04 D16).
"""

import json
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

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

RLS_VIOLATION = "row-level security"
INSERT_USER = (
    "INSERT INTO users (id, email, display_name, status, version) VALUES (:id, :e, 'Cadet', :s, 1)"
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
async def world(app_db: async_sessionmaker[AsyncSession]) -> World:
    return await build_world(app_db)


async def _run(
    factory: async_sessionmaker[AsyncSession],
    sql: str,
    *,
    realm: Realm = Realm.TENANT,
    principal: uuid.UUID | None = None,
    tenant: uuid.UUID | None = None,
    keys: dict[str, Any] | None = None,
    **params: Any,
) -> Any:
    context = RequestContext(
        realm=realm, request_id=uuid.uuid7(), principal_id=principal, tenant_id=tenant
    )
    async with context_transaction(factory, context) as db:
        for name, value in (keys or {}).items():
            await db.execute(
                text("SELECT set_config(:n, :v, true)"), {"n": f"app.{name}", "v": str(value)}
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


def _email() -> str:
    return f"cadet.{uuid.uuid7().hex[-10:]}@westernmaritime.example"


# --- Migration ------------------------------------------------------------------------------


async def test_the_tenant_administration_migration_round_trips(
    migrated_database: DatabaseUnderTest, world: World
) -> None:
    config = migrated_database.alembic_config()
    objects = (
        "SELECT (SELECT count(*) FROM information_schema.columns "
        "   WHERE table_name = 'membership_campuses' AND column_name = 'removed_at') "
        "+ (SELECT count(*) FROM pg_policies WHERE policyname = 'membership_campuses_update') "
        "+ (SELECT count(*) FROM pg_policies WHERE policyname = 'users_insert' "
        "   AND with_check LIKE '%tenant_invitee_user_id%') "
        "+ (SELECT count(*) FROM pg_policies WHERE policyname = 'audit_events_tenant_read' "
        "   AND qual LIKE '%(realm)::text = ''tenant''%')"
    )
    assert (await _owner(migrated_database, objects))[0][0] == 4
    # A campus taken out of a selection must not come back after a downgrade.
    membership = world.memberships["dave_a"]
    await _owner(
        migrated_database,
        "UPDATE membership_campuses SET removed_at = now() "
        "WHERE membership_id = :m AND campus_id = :c",
        m=membership,
        c=world.campus_a2,
    )
    await anyio.to_thread.run_sync(command.downgrade, config, "0007")
    try:
        assert (await _owner(migrated_database, objects))[0][0] == 0
        left = await _owner(
            migrated_database,
            "SELECT campus_id FROM membership_campuses WHERE membership_id = :m",
            m=membership,
        )
        assert [row[0] for row in left] == [world.campus_a1]
        grants = await _owner(
            migrated_database,
            "SELECT has_table_privilege(:r, 'membership_campuses', 'UPDATE')",
            r=migrated_database.roles["app"],
        )
        assert grants[0][0] is False
    finally:
        await anyio.to_thread.run_sync(command.upgrade, config, "head")
    assert (await _owner(migrated_database, objects))[0][0] == 4
    await anyio.to_thread.run_sync(command.check, config)


# --- D8-1: the invitee key ------------------------------------------------------------------


async def test_the_invitee_key_admits_exactly_one_invited_identity(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    alice, tenant = world.users["alice"], world.tenant_a
    invitee = uuid.uuid7()
    key = {"tenant_invitee_user_id": invitee}

    def insert(user_id: uuid.UUID, status: str = "INVITED", **context: Any) -> Any:
        return _run(app_db, INSERT_USER, id=user_id, e=_email(), s=status, **context)

    # Without the key, a tenant transaction cannot create identities at all.
    assert RLS_VIOLATION in await _error(insert(invitee, principal=alice, tenant=tenant))
    # Only the named ID, only INVITED.
    assert RLS_VIOLATION in await _error(
        insert(uuid.uuid7(), principal=alice, tenant=tenant, keys=key)
    )
    assert RLS_VIOLATION in await _error(
        insert(invitee, "ACTIVE", principal=alice, tenant=tenant, keys=key)
    )
    # Not without a signed-in principal and an active tenant, not from another realm.
    assert RLS_VIOLATION in await _error(insert(invitee, tenant=tenant, keys=key))
    assert RLS_VIOLATION in await _error(insert(invitee, principal=alice, keys=key))
    assert RLS_VIOLATION in await _error(
        insert(invitee, realm=Realm.PLATFORM, principal=uuid.uuid7(), keys=key)
    )
    assert await insert(invitee, principal=alice, tenant=tenant, keys=key) == 1


# --- D8-2: tenant audit visibility ----------------------------------------------------------


async def test_tenant_readers_see_only_tenant_realm_events_of_their_tenant(
    migrated_database: DatabaseUnderTest, app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    ids = {name: uuid.uuid7() for name in ("tenant_a", "platform_a", "tenant_b")}
    for name, realm, tenant in (
        ("tenant_a", "tenant", world.tenant_a),
        ("platform_a", "platform", world.tenant_a),
        ("tenant_b", "tenant", world.tenant_b),
    ):
        await _owner(
            migrated_database,
            "INSERT INTO audit_events (id, request_id, realm, tenant_id, category, event_type, "
            "metadata) VALUES (:id, :r, :realm, :t, 'admin', 'member.suspended', "
            "CAST(:m AS jsonb))",
            id=ids[name],
            r=uuid.uuid7(),
            realm=realm,
            t=tenant,
            m=json.dumps({}),
        )
    select = "SELECT id FROM audit_events WHERE id = ANY(:ids)"
    tenant_view = await _run(
        app_db,
        select,
        principal=world.users["alice"],
        tenant=world.tenant_a,
        ids=list(ids.values()),
    )
    assert tenant_view == {ids["tenant_a"]}
    platform_view = await _run(
        app_db, select, realm=Realm.PLATFORM, principal=uuid.uuid7(), ids=list(ids.values())
    )
    assert platform_view == set(ids.values())


# --- Campus scope rows ---------------------------------------------------------------------


async def test_membership_campuses_are_updated_in_the_tenant_and_never_deleted(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    alice = world.users["alice"]
    update = "UPDATE membership_campuses SET removed_at = now() WHERE membership_id = ANY(:m)"
    changed = await _run(
        app_db,
        update,
        principal=alice,
        tenant=world.tenant_a,
        m=[world.memberships["dave_a"], world.memberships["bob_b"]],
    )
    assert changed == 2  # dave's two A campuses
    from_b = await _run(
        app_db,
        update,
        principal=world.users["carol"],
        tenant=world.tenant_b,
        m=[world.memberships["dave_a"]],
    )
    assert from_b == 0  # another tenant's rows are not reachable
    delete = await _error(
        _run(
            app_db,
            "DELETE FROM membership_campuses WHERE membership_id = :m",
            principal=alice,
            tenant=world.tenant_a,
            m=world.memberships["dave_a"],
        )
    )
    assert "permission denied" in delete
