"""Platform administration schema and Row-Level Security (T01-07; migration 0007).

Raw SQL through the real runtime roles and trusted ``SET LOCAL`` settings, so
only the database protects the rows. Each new key opens exactly its target:

* ``app.provisioning_tenant_id`` (with the same ``app.tenant_id``): the new
  tenant's system roles and an ``INVITED`` owner identity — never another
  tenant's rows, never without both settings (D7-1);
* ``app.platform_target_tenant_id``: that tenant's sessions only (D7-6);
* ``app.platform_owner_membership_id``: one membership, its invitations and
  its user (D7-8);
* ``app.platform_admin_target_user_id``: one platform user, for an
  authenticated platform principal (D7-2);
* ``app.platform_auth_token_hash``: one platform invitation and its user's
  first credential (D7-3).

Tenant contexts and the read-only role gain nothing.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import anyio
import pytest
from alembic import command
from conftest import DatabaseUnderTest
from identity_support import World, add_session, build_world
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


def _insert_role(tenant: uuid.UUID) -> tuple[str, dict[str, Any]]:
    return (
        "INSERT INTO roles (id, tenant_id, name, template_code, is_system, version) "
        "VALUES (:id, :t, :n, 'INSTITUTE_OWNER', true, 1)",
        {"id": uuid.uuid7(), "t": tenant, "n": f"Owner {uuid.uuid7().hex[-6:]}"},
    )


# --- Migration ------------------------------------------------------------------------------


async def test_the_administration_migration_downgrades_and_upgrades_cleanly(
    migrated_database: DatabaseUnderTest,
) -> None:
    config = migrated_database.alembic_config()
    objects = (
        "SELECT (SELECT count(*) FROM pg_class WHERE relname = 'platform_user_invitations') "
        "+ (SELECT count(*) FROM pg_policies WHERE tablename = 'platform_user_invitations') "
        "+ (SELECT count(*) FROM information_schema.columns "
        "   WHERE table_name = 'tenants' AND column_name = 'owner_membership_id') "
        "+ (SELECT count(*) FROM pg_constraint WHERE conname = 'fk_tenants_owner_membership') "
        "+ (SELECT count(*) FROM pg_policies WHERE qual LIKE '%platform_admin_target_user_id%' "
        "   OR with_check LIKE '%provisioning_tenant_id%')"
    )
    present = (await _owner(migrated_database, objects))[0][0]
    await anyio.to_thread.run_sync(command.downgrade, config, "0006")
    try:
        assert (await _owner(migrated_database, objects))[0][0] == 0
    finally:
        await anyio.to_thread.run_sync(command.upgrade, config, "head")
    assert (await _owner(migrated_database, objects))[0][0] == present
    # 1 table, 3 policies, 1 column, 1 foreign key; altered policies on 7 + 3 tables.
    assert present >= 1 + 3 + 1 + 1 + 4
    await anyio.to_thread.run_sync(command.check, config)


async def test_the_readonly_role_and_tenant_contexts_see_no_invitation(
    app_db: async_sessionmaker[AsyncSession],
    readonly_db: async_sessionmaker[AsyncSession],
    world: World,
) -> None:
    error = await _error(_run(readonly_db, "SELECT id FROM platform_user_invitations"))
    assert "permission denied" in error
    rows = await _run(
        app_db,
        "SELECT id FROM platform_user_invitations",
        realm=Realm.TENANT,
        principal=world.users["alice"],
        tenant=world.tenant_a,
    )
    assert rows == set()


# --- D7-1 provisioning -----------------------------------------------------------------------


async def test_the_provisioning_key_opens_only_the_new_tenants_system_roles(
    app_db: async_sessionmaker[AsyncSession],
    migrated_database: DatabaseUnderTest,
    world: World,
    pworld: PlatformWorld,
) -> None:
    nora = pworld.users["nora"]
    fresh = uuid.uuid7()  # a tenant without system roles yet, as during provisioning
    await _owner(
        migrated_database,
        "INSERT INTO tenants (id, name, status, version) VALUES (:id, :n, 'TRIAL', 1)",
        id=fresh,
        n=f"Malabar Seafarers Institute {fresh.hex[-6:]}",
    )
    sql, params = _insert_role(fresh)
    # A platform context with a tenant but without the provisioning key: refused.
    assert RLS_VIOLATION in await _error(_run(app_db, sql, principal=nora, tenant=fresh, **params))
    # The key must name the same tenant as app.tenant_id.
    assert RLS_VIOLATION in await _error(
        _run(
            app_db,
            sql,
            principal=nora,
            tenant=fresh,
            keys={"provisioning_tenant_id": world.tenant_a},
            **params,
        )
    )
    # A tenant-realm context with the key gains nothing.
    assert RLS_VIOLATION in await _error(
        _run(
            app_db,
            sql,
            realm=Realm.TENANT,
            principal=world.users["carol"],
            tenant=fresh,
            keys={"provisioning_tenant_id": fresh},
            **params,
        )
    )
    # Another tenant's roles stay closed even with a valid key for the new one.
    other, other_params = _insert_role(world.tenant_b)
    assert RLS_VIOLATION in await _error(
        _run(
            app_db,
            other,
            principal=nora,
            tenant=fresh,
            keys={"provisioning_tenant_id": fresh},
            **other_params,
        )
    )
    inserted = await _run(
        app_db,
        sql,
        principal=nora,
        tenant=fresh,
        keys={"provisioning_tenant_id": fresh},
        **params,
    )
    assert inserted == 1


async def test_the_provisioning_key_creates_only_invited_identities(
    app_db: async_sessionmaker[AsyncSession], world: World, pworld: PlatformWorld
) -> None:
    def insert(status: str) -> Any:
        return _run(
            app_db,
            "INSERT INTO users (id, email, display_name, status, version) "
            "VALUES (:id, :e, 'Owner', :s, 1)",
            principal=pworld.users["nora"],
            tenant=world.tenant_b,
            keys={"provisioning_tenant_id": world.tenant_b},
            id=uuid.uuid7(),
            e=f"owner.{uuid.uuid7().hex[-10:]}@coastalmaritime.example",
            s=status,
        )

    assert RLS_VIOLATION in await _error(insert("ACTIVE"))
    assert await insert("INVITED") == 1
    without = await _error(
        _run(
            app_db,
            "INSERT INTO users (id, email, display_name, status, version) "
            "VALUES (:id, :e, 'Owner', 'INVITED', 1)",
            principal=pworld.users["nora"],
            id=uuid.uuid7(),
            e=f"owner.{uuid.uuid7().hex[-10:]}@coastalmaritime.example",
        )
    )
    assert RLS_VIOLATION in without


# --- D7-6 suspension target -------------------------------------------------------------------


async def test_the_suspension_key_reaches_only_that_tenants_sessions(
    app_db: async_sessionmaker[AsyncSession], world: World, pworld: PlatformWorld
) -> None:
    a_session, _ = await add_session(app_db, world, "alice", tenant_id=world.tenant_a)
    b_session, _ = await add_session(app_db, world, "carol", tenant_id=world.tenant_b)
    nora = pworld.users["nora"]
    seen = await _run(
        app_db,
        "SELECT id FROM user_sessions WHERE id = ANY(:ids)",
        principal=nora,
        keys={"platform_target_tenant_id": world.tenant_a},
        ids=[a_session, b_session],
    )
    assert seen == {a_session}
    assert (
        await _run(
            app_db,
            "SELECT id FROM user_sessions WHERE id = ANY(:ids)",
            principal=nora,
            ids=[a_session],
        )
        == set()
    )
    updated = await _run(
        app_db,
        "UPDATE user_sessions SET revoked_at = now(), revoke_reason = 'tenant_suspended' "
        "WHERE id = ANY(:ids)",
        principal=nora,
        keys={"platform_target_tenant_id": world.tenant_a},
        ids=[a_session, b_session],
    )
    assert updated == 1


# --- D7-8 owner key ----------------------------------------------------------------------------


async def test_the_owner_key_reaches_one_membership_its_user_and_invitations(
    app_db: async_sessionmaker[AsyncSession], world: World, pworld: PlatformWorld
) -> None:
    membership = world.memberships["alice_a"]
    nora = pworld.users["nora"]
    keys = {"platform_owner_membership_id": membership}
    memberships = await _run(
        app_db,
        "SELECT id FROM tenant_memberships WHERE tenant_id = :t",
        principal=nora,
        keys=keys,
        t=world.tenant_a,
    )
    assert memberships == {membership}
    users = await _run(
        app_db,
        "SELECT id FROM users WHERE id = ANY(:ids)",
        principal=nora,
        keys=keys,
        ids=list(world.users.values()),
    )
    assert users == {world.users["alice"]}
    assert (
        await _run(
            app_db,
            "SELECT id FROM users WHERE id = ANY(:ids)",
            principal=nora,
            ids=list(world.users.values()),
        )
        == set()
    )
    other = await _error(
        _run(
            app_db,
            "INSERT INTO user_invitations (id, tenant_id, membership_id, token_hash, expires_at) "
            "VALUES (:id, :t, :m, :h, :e)",
            principal=nora,
            keys=keys,
            id=uuid.uuid7(),
            t=world.tenant_a,
            m=world.memberships["dave_a"],
            h=uuid.uuid7().hex + uuid.uuid7().hex,
            e=datetime.now(UTC) + timedelta(days=7),
        )
    )
    assert RLS_VIOLATION in other


# --- D7-2 administration target and D7-3 invitations -------------------------------------------


async def test_the_admin_key_opens_one_platform_user_for_a_principal(
    app_db: async_sessionmaker[AsyncSession], pworld: PlatformWorld
) -> None:
    nora, pia, omar = pworld.users["nora"], pworld.users["pia"], pworld.users["omar"]
    update = "UPDATE platform_users SET display_name = display_name WHERE id = ANY(:ids)"
    assert await _run(app_db, update, principal=nora, ids=[pia, omar]) == 0
    assert (
        await _run(
            app_db,
            update,
            principal=nora,
            keys={"platform_admin_target_user_id": pia},
            ids=[pia, omar],
        )
        == 1
    )
    # Without a principal the key opens nothing.
    assert await _run(app_db, update, keys={"platform_admin_target_user_id": pia}, ids=[pia]) == 0
    role = (
        "INSERT INTO platform_user_roles (id, platform_user_id, role_code) "
        "VALUES (:id, :u, 'SUPPORT_ADMIN')"
    )
    assert RLS_VIOLATION in await _error(
        _run(
            app_db,
            role,
            principal=nora,
            keys={"platform_admin_target_user_id": pia},
            id=uuid.uuid7(),
            u=omar,
        )
    )
    assert (
        await _run(
            app_db,
            role,
            principal=nora,
            keys={"platform_admin_target_user_id": pia},
            id=uuid.uuid7(),
            u=pia,
        )
        == 1
    )
    # A new platform user only as INVITED, only the target ID.
    new = uuid.uuid7()
    create = (
        "INSERT INTO platform_users (id, email, display_name, status, version) "
        "VALUES (:id, :e, 'New Admin', :s, 1)"
    )
    email = f"new.{new.hex[-10:]}@mti360-platform.example"
    keys = {"platform_admin_target_user_id": new}
    assert RLS_VIOLATION in await _error(
        _run(app_db, create, principal=nora, keys=keys, id=new, e=email, s="ACTIVE")
    )
    assert RLS_VIOLATION in await _error(
        _run(app_db, create, principal=nora, keys=keys, id=uuid.uuid7(), e=email, s="INVITED")
    )
    assert await _run(app_db, create, principal=nora, keys=keys, id=new, e=email, s="INVITED") == 1
    # Other users' sessions and credentials stay out of reach.
    assert (
        await _run(
            app_db,
            "SELECT id FROM platform_user_credentials WHERE platform_user_id = :u",
            principal=nora,
            keys={"platform_admin_target_user_id": pia},
            u=pia,
        )
        == set()
    )


async def test_an_invitation_token_opens_its_user_and_first_credential_only(
    app_db: async_sessionmaker[AsyncSession], pworld: PlatformWorld
) -> None:
    nora = pworld.users["nora"]
    invited = uuid.uuid7()
    token_hash = uuid.uuid7().hex + uuid.uuid7().hex
    keys = {"platform_admin_target_user_id": invited}
    await _run(
        app_db,
        "INSERT INTO platform_users (id, email, display_name, status, version) "
        "VALUES (:id, :e, 'Invitee', 'INVITED', 1)",
        principal=nora,
        keys=keys,
        id=invited,
        e=f"invitee.{invited.hex[-10:]}@mti360-platform.example",
    )
    await _run(
        app_db,
        "INSERT INTO platform_user_invitations (id, platform_user_id, token_hash, expires_at) "
        "VALUES (:id, :u, :h, now() + interval '7 days')",
        principal=nora,
        keys=keys,
        id=uuid.uuid7(),
        u=invited,
        h=token_hash,
    )
    token = {"platform_auth_token_hash": token_hash}
    users = await _run(app_db, "SELECT id FROM platform_users", keys=token)
    assert users == {invited}
    credential = (
        "INSERT INTO platform_user_credentials (id, platform_user_id, password_hash, "
        "password_changed_at) VALUES (:id, :u, :p, now())"
    )
    assert RLS_VIOLATION in await _error(
        _run(app_db, credential, keys=token, id=uuid.uuid7(), u=pworld.users["pia"], p=HASH)
    )
    assert await _run(app_db, credential, keys=token, id=uuid.uuid7(), u=invited, p=HASH) == 1
    # Without the token an anonymous platform context sees no invitation.
    assert await _run(app_db, "SELECT id FROM platform_user_invitations") == set()
