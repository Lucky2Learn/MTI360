"""RBAC schema and Row-Level Security against real PostgreSQL (T01-05; migration 0005).

Raw SQL through the real runtime roles and the trusted ``SET LOCAL`` context,
so that only the database protects the rows:

* the catalogue is read-only at runtime (D-B4) and holds no wildcard (D-B3);
* system roles cannot be renamed, deleted or have their permissions changed
  — refused by RLS for tenant contexts and by trigger for everyone, the
  system realm and the table owner included (D-B2);
* a tenant role can never hold a platform permission (ADR-0011 §2);
* roles, role permissions and assignments are isolated per tenant;
* migration 0005 clones the system roles for existing tenants and assigns
  nobody.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import anyio
import pytest
from alembic import command
from alembic.script import ScriptDirectory
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

RBAC_REVISION = "0005"
TABLES = ("permissions", "roles", "role_permissions", "membership_roles")
POLICIES = (
    "permissions_read",
    "roles_select",
    "roles_insert",
    "roles_update",
    "roles_delete",
    "role_permissions_select",
    "role_permissions_insert",
    "role_permissions_delete",
    "membership_roles_select",
    "membership_roles_insert",
    "membership_roles_delete",
)
TRIGGERS = ("roles_protect_system", "role_permissions_protect_system")
TENANT_CODES = {
    "audit.read",
    "campus.create",
    "campus.read",
    "campus.update",
    "member.invite",
    "member.read",
    "member.revoke",
    "member.suspend",
    "member.update",
    "role.assign",
    "role.create",
    "role.delete",
    "role.read",
    "role.update",
    "tenant.profile.read",
}
PHASE_02_1_CODES = {
    "course.manage",
    "course.read",
    "lead.assign",
    "lead.create",
    "lead.read",
    "lead.update",
}
PHASE_02_2_CODES = {
    "admission.approve",
    "application.create",
    "application.read",
    "application.review",
    "application.update",
    "document.read",
    "document.upload",
    "document.verify",
    "student.read",
}
COUNSELLOR_02_2 = PHASE_02_2_CODES - {"application.review", "document.verify", "admission.approve"}
PLATFORM_CODES = {
    "audit.read",
    "platform_user.create",
    "platform_user.reactivate",
    "platform_user.read",
    "platform_user.suspend",
    "platform_user.update",
    "tenant.create",
    "tenant.reactivate",
    "tenant.read",
    "tenant.suspend",
}
SYSTEM_ROLE_ERROR = "system role"
PERMISSION_DENIED = "permission denied"
RLS_VIOLATION = "row-level security"
FK_VIOLATION = "foreign key"


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
async def readonly_db(
    migrated_database: DatabaseUnderTest,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with _factory(migrated_database.readonly_url) as factory:
        yield factory


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
    factory: async_sessionmaker[AsyncSession],
    sql: str,
    *,
    tenant: uuid.UUID | None = None,
    realm: Realm = Realm.TENANT,
    **params: Any,
) -> Any:
    """Run ``sql`` with a trusted context; rows for a query, else the row count.

    ``tenant`` is both the context's tenant and the ``:tenant`` bind parameter.
    """
    params.setdefault("tenant", tenant)
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


async def _role(
    factory: async_sessionmaker[AsyncSession],
    tenant: uuid.UUID,
    name: str,
    *,
    codes: tuple[str, ...] = ("campus.read",),
) -> uuid.UUID:
    """A custom role with permissions, created by the system realm."""
    role_id = uuid.uuid7()
    context = RequestContext(realm=Realm.SYSTEM, request_id=uuid.uuid7(), tenant_id=tenant)
    async with context_transaction(factory, context) as db:
        await db.execute(
            text(
                "INSERT INTO roles (id, tenant_id, name, is_system, version) "
                "VALUES (:id, :tenant, :name, false, 1)"
            ),
            {"id": role_id, "tenant": tenant, "name": name},
        )
        for code in codes:
            await db.execute(
                text(
                    "INSERT INTO role_permissions (id, tenant_id, role_id, permission_code) "
                    "VALUES (:id, :tenant, :role, :code)"
                ),
                {"id": uuid.uuid7(), "tenant": tenant, "role": role_id, "code": code},
            )
    return role_id


async def _assign(
    factory: async_sessionmaker[AsyncSession],
    tenant: uuid.UUID,
    membership: uuid.UUID,
    role: uuid.UUID,
    *,
    realm: Realm = Realm.SYSTEM,
) -> Any:
    return await _run(
        factory,
        "INSERT INTO membership_roles (id, tenant_id, membership_id, role_id) "
        "VALUES (:id, :tenant, :membership, :role)",
        tenant=tenant,
        realm=realm,
        id=uuid.uuid7(),
        membership=membership,
        role=role,
    )


# --- Migration, catalogue, privileges, RLS presence --------------------------------------


async def test_the_rbac_migration_clones_system_roles_and_assigns_nobody(
    migrated_database: DatabaseUnderTest, world: World
) -> None:
    config = migrated_database.alembic_config()
    revision = ScriptDirectory.from_config(config).get_revision(RBAC_REVISION)
    assert revision is not None
    objects = (
        "SELECT (SELECT count(*) FROM pg_class WHERE relname = ANY(:tables) AND relkind = 'r') "
        "+ (SELECT count(*) FROM pg_policies WHERE policyname = ANY(:policies)) "
        "+ (SELECT count(*) FROM pg_trigger WHERE tgname = ANY(:triggers)) "
        "+ (SELECT count(*) FROM pg_proc WHERE proname = ANY(:triggers))"
    )
    names = {"tables": list(TABLES), "policies": list(POLICIES), "triggers": list(TRIGGERS)}
    present = (await _owner(migrated_database, objects, **names))[0][0]

    await anyio.to_thread.run_sync(command.downgrade, config, str(revision.down_revision))
    try:
        assert (await _owner(migrated_database, objects, **names))[0][0] == 0
    finally:
        await anyio.to_thread.run_sync(command.upgrade, config, "head")

    assert present == len(TABLES) + len(POLICIES) + 2 * len(TRIGGERS)
    # World A existed before the upgrade: 0005 cloned the two T01 system roles; 0009
    # (Phase 02-1) added Admissions manager and Counsellor and extended the first two;
    # 0010 (Phase 02-2) extended all four.
    roles = await _owner(
        migrated_database,
        "SELECT r.template_code, r.name, array_agg(rp.permission_code ORDER BY 1) "
        "FROM roles r JOIN role_permissions rp ON rp.role_id = r.id "
        "WHERE r.tenant_id = :tenant GROUP BY r.id",
        tenant=world.tenant_a,
    )
    by_template = {row[0]: (row[1], set(row[2])) for row in roles}
    head = TENANT_CODES | PHASE_02_1_CODES | PHASE_02_2_CODES
    assert by_template == {
        "INSTITUTE_OWNER": ("Institute owner", head),
        "ADMIN": ("Administrator", head - {"role.delete"}),
        "ADMISSIONS_MANAGER": ("Admissions manager", PHASE_02_1_CODES | PHASE_02_2_CODES),
        "COUNSELLOR": (
            "Counsellor",
            (PHASE_02_1_CODES - {"course.manage", "lead.assign"}) | COUNSELLOR_02_2,
        ),
    }
    # ... and no member was given a role.
    assigned = await _owner(
        migrated_database,
        "SELECT count(*) FROM membership_roles WHERE tenant_id = ANY(:tenants)",
        tenants=[world.tenant_a, world.tenant_b],
    )
    assert assigned[0][0] == 0


async def test_the_catalogue_holds_the_t01_baseline_without_wildcards(
    app_db: async_sessionmaker[AsyncSession], readonly_db: async_sessionmaker[AsyncSession]
) -> None:
    for factory in (app_db, readonly_db):
        tenant = await _run(factory, "SELECT code FROM permissions WHERE realm = 'tenant'")
        platform = await _run(factory, "SELECT code FROM permissions WHERE realm = 'platform'")
        assert tenant >= TENANT_CODES
        assert platform >= PLATFORM_CODES
        assert not {code for code in tenant | platform if "*" in code}
    scopes = await _run(
        app_db,
        "SELECT code || ':' || coalesce(scope, '-') FROM permissions WHERE code = ANY(:codes)",
        codes=["campus.read", "campus.update", "campus.create", "tenant.read"],
    )
    assert scopes == {
        "campus.read:campus",
        "campus.update:campus",
        "campus.create:tenant",
        "tenant.read:-",
    }


async def test_the_catalogue_is_read_only_at_runtime(
    app_db: async_sessionmaker[AsyncSession], readonly_db: async_sessionmaker[AsyncSession]
) -> None:
    writes = (
        "INSERT INTO permissions (realm, code, scope, module, description) "
        "VALUES ('tenant', 'campus.archive', 'campus', 'institute', 'x')",
        "UPDATE permissions SET description = 'x' WHERE code = 'campus.read'",
        "DELETE FROM permissions WHERE code = 'campus.read'",
    )
    for factory in (app_db, readonly_db):
        for realm in (Realm.TENANT, Realm.SYSTEM):
            for sql in writes:
                assert PERMISSION_DENIED in await _error(_run(factory, sql, realm=realm))


async def test_runtime_privileges(migrated_database: DatabaseUnderTest) -> None:
    expected = {
        "permissions": {"SELECT"},
        "roles": {"SELECT", "INSERT", "UPDATE", "DELETE"},
        "role_permissions": {"SELECT", "INSERT", "DELETE"},
        "membership_roles": {"SELECT", "INSERT", "DELETE"},
    }
    kinds = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
    for table, privileges in expected.items():
        for kind in kinds:
            app_has, readonly_has = (
                await _owner(
                    migrated_database,
                    "SELECT bool_or(has_table_privilege(r.rolname, :table, :kind)) "
                    "FILTER (WHERE r.rolname = :app), "
                    "bool_or(has_table_privilege(r.rolname, :table, :kind)) "
                    "FILTER (WHERE r.rolname = :readonly) FROM pg_roles r",
                    table=table,
                    kind=kind,
                    app=_role_name(migrated_database.app_url),
                    readonly=_role_name(migrated_database.readonly_url),
                )
            )[0]
            assert app_has is (kind in privileges), (table, kind)
            assert readonly_has is (table == "permissions" and kind == "SELECT"), (table, kind)


def _role_name(url: str) -> str:
    from sqlalchemy.engine import make_url

    username = make_url(url).username
    assert username
    return username


async def test_rls_is_enabled_and_not_forced(migrated_database: DatabaseUnderTest) -> None:
    rows = await _owner(
        migrated_database,
        "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
        "WHERE relname = ANY(:tables) AND relkind = 'r'",
        tables=list(TABLES),
    )
    assert {row[0]: (row[1], row[2]) for row in rows} == dict.fromkeys(TABLES, (True, False))


async def test_no_security_definer_function_was_introduced(
    migrated_database: DatabaseUnderTest,
) -> None:
    rows = await _owner(
        migrated_database,
        "SELECT proname, prosecdef FROM pg_proc WHERE proname = ANY(:names)",
        names=list(TRIGGERS),
    )
    assert {row[0]: row[1] for row in rows} == dict.fromkeys(TRIGGERS, False)


# --- D-B2: system roles are immutable ------------------------------------------------------


async def test_a_tenant_context_cannot_touch_system_roles(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    tenant = world.tenant_a
    owner = world.roles["owner_a"]  # cloned from the template by the test world
    params: dict[str, Any] = {"tenant": tenant, "realm": Realm.TENANT, "role": owner}
    # Hidden from UPDATE and DELETE by the policies: nothing changes.
    assert await _run(app_db, "UPDATE roles SET name = 'Captain' WHERE id = :role", **params) == 0
    assert await _run(app_db, "DELETE FROM roles WHERE id = :role", **params) == 0
    assert await _run(app_db, "DELETE FROM role_permissions WHERE role_id = :role", **params) == 0
    # Inserting permissions into a system role, or creating one, is refused.
    add_permission = (
        "INSERT INTO role_permissions (id, tenant_id, role_id, permission_code) "
        "VALUES (:id, :tenant, :role, 'member.read')"
    )
    assert RLS_VIOLATION in await _error(_run(app_db, add_permission, id=uuid.uuid7(), **params))
    create_system = (
        "INSERT INTO roles (id, tenant_id, name, template_code, is_system, version) "
        "VALUES (:id, :tenant, 'Owner bis', 'ADMIN', true, 1)"
    )
    assert RLS_VIOLATION in await _error(
        _run(app_db, create_system, id=uuid.uuid7(), tenant=tenant)
    )
    names = await _run(app_db, "SELECT name FROM roles WHERE id = :role", **params)
    assert names == {"Institute owner"}


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE roles SET name = 'Captain' WHERE id = :role",
        "UPDATE roles SET description = 'x' WHERE id = :role",
        "DELETE FROM roles WHERE id = :role",
        "DELETE FROM role_permissions WHERE role_id = :role",
        "UPDATE role_permissions SET permission_code = 'member.read' WHERE role_id = :role",
    ],
)
async def test_the_database_rejects_system_role_changes_for_everyone(
    app_db: async_sessionmaker[AsyncSession],
    migrated_database: DatabaseUnderTest,
    world: World,
    sql: str,
) -> None:
    role = world.roles["admin_a"]
    # The system realm passes RLS but the trigger refuses ...
    system_error = await _error(_run(app_db, sql, realm=Realm.SYSTEM, role=role))
    # ... and so it does for the table owner, who bypasses RLS.
    owner_error = await _error(_owner(migrated_database, sql, role=role))
    if sql.startswith("UPDATE role_permissions"):
        assert PERMISSION_DENIED in system_error  # no UPDATE privilege at all
    else:
        assert SYSTEM_ROLE_ERROR in system_error
    assert SYSTEM_ROLE_ERROR in owner_error


async def test_a_custom_role_cannot_become_a_system_role(
    app_db: async_sessionmaker[AsyncSession], migrated_database: DatabaseUnderTest, world: World
) -> None:
    role = await _role(app_db, world.tenant_a, f"Deck officer {world.suffix}")
    promote = "UPDATE roles SET is_system = true, template_code = 'ADMIN' WHERE id = :role"
    # The BEFORE UPDATE trigger refuses before the policy's WITH CHECK is evaluated.
    assert SYSTEM_ROLE_ERROR in await _error(
        _run(app_db, promote, tenant=world.tenant_a, role=role)
    )
    assert SYSTEM_ROLE_ERROR in await _error(_run(app_db, promote, realm=Realm.SYSTEM, role=role))
    assert SYSTEM_ROLE_ERROR in await _error(_owner(migrated_database, promote, role=role))
    # A system flag always comes with a template (CHECK), whoever inserts the row.
    half = (
        "INSERT INTO roles (id, tenant_id, name, is_system, version) "
        "VALUES (:id, :tenant, 'Half system', true, 1)"
    )
    assert "check constraint" in await _error(
        _owner(migrated_database, half, id=uuid.uuid7(), tenant=world.tenant_a)
    )


# --- ADR-0011: tenant roles hold tenant permissions only -----------------------------------


@pytest.mark.parametrize("code", ["tenant.read", "platform_user.create", "campus.*", "*"])
async def test_a_tenant_role_cannot_hold_platform_or_wildcard_permissions(
    app_db: async_sessionmaker[AsyncSession], world: World, code: str
) -> None:
    role = await _role(app_db, world.tenant_a, f"Purser {uuid.uuid7().hex}")
    error = await _error(
        _run(
            app_db,
            "INSERT INTO role_permissions (id, tenant_id, role_id, permission_code) "
            "VALUES (:id, :tenant, :role, :code)",
            tenant=world.tenant_a,
            id=uuid.uuid7(),
            role=role,
            code=code,
        )
    )
    assert FK_VIOLATION in error


async def test_the_permission_realm_column_cannot_be_written(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    role = await _role(app_db, world.tenant_a, f"Bosun {world.suffix}")
    error = await _error(
        _run(
            app_db,
            "INSERT INTO role_permissions "
            "(id, tenant_id, role_id, permission_realm, permission_code) "
            "VALUES (:id, :tenant, :role, 'platform', 'tenant.read')",
            realm=Realm.SYSTEM,
            id=uuid.uuid7(),
            tenant=world.tenant_a,
            role=role,
        )
    )
    assert "generated column" in error


# --- Tenant isolation ----------------------------------------------------------------------


async def test_roles_permissions_and_assignments_are_isolated_per_tenant(
    app_db: async_sessionmaker[AsyncSession],
    readonly_db: async_sessionmaker[AsyncSession],
    world: World,
) -> None:
    role_a = await _role(app_db, world.tenant_a, f"Training officer {world.suffix}")
    role_b = await _role(app_db, world.tenant_b, f"Training officer {world.suffix}")
    await _assign(app_db, world.tenant_a, world.memberships["alice_a"], role_a)
    await _assign(app_db, world.tenant_b, world.memberships["carol_b"], role_b)

    for tenant, own, other in (
        (world.tenant_a, role_a, role_b),
        (world.tenant_b, role_b, role_a),
    ):
        ids: dict[str, Any] = {"own": own, "other": other}
        roles = await _run(
            app_db, "SELECT id FROM roles WHERE id IN (:own, :other)", tenant=tenant, **ids
        )
        assert roles == {own}
        permissions = await _run(
            app_db,
            "SELECT role_id FROM role_permissions WHERE role_id IN (:own, :other)",
            tenant=tenant,
            **ids,
        )
        assert permissions == {own}
        assignments = await _run(
            app_db,
            "SELECT role_id FROM membership_roles WHERE role_id IN (:own, :other)",
            tenant=tenant,
            **ids,
        )
        assert assignments == {own}
        # Another tenant's rows cannot be changed or removed.
        changed = await _run(
            app_db, "UPDATE roles SET name = 'x' WHERE id = :other", tenant=tenant, other=other
        )
        removed = await _run(
            app_db,
            "DELETE FROM membership_roles WHERE role_id = :other",
            tenant=tenant,
            other=other,
        )
        assert (changed, removed) == (0, 0)

    # No tenant context: nothing at all.
    nothing = await _run(
        app_db, "SELECT id FROM roles WHERE id IN (:a, :b)", realm=Realm.TENANT, a=role_a, b=role_b
    )
    assert nothing == set()
    # The read-only role cannot read roles, permissions of roles or assignments.
    for table in ("roles", "role_permissions", "membership_roles"):
        assert PERMISSION_DENIED in await _error(
            _run(readonly_db, f"SELECT 1 FROM {table}", tenant=world.tenant_a)  # noqa: S608
        )


async def test_a_tenant_cannot_write_into_another_tenant(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    role_b = await _role(app_db, world.tenant_b, f"Chief engineer {world.suffix}")
    role_a = await _role(app_db, world.tenant_a, f"Chief engineer {world.suffix}")
    # A role in tenant B, written from tenant A.
    create = (
        "INSERT INTO roles (id, tenant_id, name, is_system, version) "
        "VALUES (:id, :other, 'Intruder', false, 1)"
    )
    assert RLS_VIOLATION in await _error(
        _run(app_db, create, tenant=world.tenant_a, id=uuid.uuid7(), other=world.tenant_b)
    )
    # Tenant B's role on tenant A's membership: the composite foreign key refuses ...
    assert FK_VIOLATION in await _error(
        _assign(
            app_db,
            world.tenant_b,
            world.memberships["alice_a"],
            role_b,
            realm=Realm.TENANT,
        )
    )
    # ... and, labelled as tenant A, the composite foreign key.
    assert FK_VIOLATION in await _error(
        _assign(app_db, world.tenant_a, world.memberships["alice_a"], role_b, realm=Realm.TENANT)
    )
    # Even the system realm cannot mix tenants.
    assert FK_VIOLATION in await _error(
        _assign(app_db, world.tenant_a, world.memberships["carol_b"], role_a)
    )


async def test_a_tenant_manages_its_custom_roles(
    app_db: async_sessionmaker[AsyncSession], world: World
) -> None:
    tenant = world.tenant_a
    role = uuid.uuid7()
    name = f"Placement officer {world.suffix}"
    created = await _run(
        app_db,
        "INSERT INTO roles (id, tenant_id, name, is_system, version) "
        "VALUES (:id, :tenant, :name, false, 1)",
        tenant=tenant,
        id=role,
        name=name,
    )
    assert created == 1
    add = (
        "INSERT INTO role_permissions (id, tenant_id, role_id, permission_code) "
        "VALUES (:id, :tenant, :role, :code)"
    )
    for code in ("member.read", "campus.read"):
        await _run(app_db, add, tenant=tenant, id=uuid.uuid7(), role=role, code=code)
    duplicate = (
        "INSERT INTO roles (id, tenant_id, name, is_system, version) "
        "VALUES (:id, :tenant, upper(:name), false, 1)"
    )
    assert "duplicate key" in await _error(
        _run(app_db, duplicate, tenant=tenant, id=uuid.uuid7(), name=name)
    )
    assert (
        await _run(
            app_db,
            "UPDATE roles SET name = :new, version = version + 1 WHERE id = :role",
            tenant=tenant,
            new=f"{name} (sea)",
            role=role,
        )
        == 1
    )
    await _assign(app_db, tenant, world.memberships["alice_a"], role, realm=Realm.TENANT)
    # An assigned role cannot be deleted (RESTRICT) ...
    assert FK_VIOLATION in await _error(
        _run(app_db, "DELETE FROM roles WHERE id = :role", tenant=tenant, role=role)
    )
    removed = await _run(
        app_db, "DELETE FROM membership_roles WHERE role_id = :role", tenant=tenant, role=role
    )
    permissions = await _run(
        app_db, "DELETE FROM role_permissions WHERE role_id = :role", tenant=tenant, role=role
    )
    deleted = await _run(app_db, "DELETE FROM roles WHERE id = :role", tenant=tenant, role=role)
    assert (removed, permissions, deleted) == (1, 2, 1)
