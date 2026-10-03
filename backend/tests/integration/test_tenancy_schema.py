"""Tenancy schema against real PostgreSQL (T01-03; ADR-0014): migration ``0003``.

Constraints, foreign keys, privileges and the presence of Row-Level Security.
Constraint tests write as the owner, which bypasses RLS (not forced), so only
the constraint under test can reject a row. Cross-tenant behaviour through
the runtime roles is in ``test_tenancy_isolation.py``.

Tenants and campuses cannot be deleted by the runtime roles, and the test
database is shared, so every test creates its own rows with unique values and
never counts a whole table.
"""

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
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.context import Realm, RequestContext
from app.core.db.session import context_transaction
from app.modules.institute.models import Campus
from app.modules.tenants.domain import TenantStatus
from app.modules.tenants.models import Tenant

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

TENANCY_REVISION = "0003"
CHECK_VIOLATION = "check constraint"
UNIQUE_VIOLATION = "duplicate key value"
FK_VIOLATION = "foreign key constraint"
NOT_NULL_VIOLATION = "null value"


# --- Helpers -------------------------------------------------------------------------


@asynccontextmanager
async def _engine(url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


async def _owner_scalar(database: DatabaseUnderTest, sql: str, **params: Any) -> Any:
    async with _engine(database.owner_url) as engine, engine.connect() as connection:
        return (await connection.execute(text(sql), params)).scalar()


async def _owner_execute(database: DatabaseUnderTest, sql: str, **params: Any) -> str | None:
    """Run ``sql`` as the owner in its own transaction; the database error, or None."""
    try:
        async with _engine(database.owner_url) as engine, engine.begin() as connection:
            await connection.execute(text(sql), params)
    except DBAPIError as error:
        return str(error.orig).lower()
    return None


async def _new_tenant(database: DatabaseUnderTest, status: str = "TRIAL") -> uuid.UUID:
    tenant_id = uuid.uuid7()
    error = await _owner_execute(
        database,
        "INSERT INTO tenants (id, name, status, version) VALUES (:id, :name, :status, 1)",
        id=tenant_id,
        name=f"Western Maritime Academy {tenant_id.hex[-6:]}",
        status=status,
    )
    assert error is None
    return tenant_id


def _insert_campus_sql() -> str:
    return (
        "INSERT INTO campuses (id, tenant_id, name, code, version) "
        "VALUES (:id, :tenant_id, :name, :code, 1)"
    )


async def _insert_campus(
    database: DatabaseUnderTest, tenant_id: uuid.UUID | None, code: str | None
) -> str | None:
    return await _owner_execute(
        database,
        _insert_campus_sql(),
        id=uuid.uuid7(),
        tenant_id=tenant_id,
        name="Navi Mumbai Campus",
        code=code,
    )


# The policies created by 0003. Later migrations may add policies to these
# tables (0004: tenants_member_read); they are tested with their own migration.
T01_03_POLICIES = [
    "campuses_readonly_tenant_read",
    "campuses_tenant_isolation",
    "tenants_own_read",
    "tenants_platform_insert",
    "tenants_platform_read",
    "tenants_platform_update",
]

T01_03_OBJECTS = (
    "SELECT (SELECT count(*) FROM pg_class WHERE relname IN ('tenants', 'campuses', "
    "    'pk_tenants', 'pk_campuses', 'uq_campuses_tenant_id_id', 'uq_campuses_tenant_id_code')) "
    "+ (SELECT count(*) FROM pg_policies WHERE policyname = ANY(:policies)) "
    "+ (SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
    "    WHERE t.relname IN ('tenants', 'campuses') AND c.contype <> 'n' "
    "    AND c.conname <> 'fk_tenants_owner_membership')"
)
# contype 'n' (NOT NULL, catalogued as constraints since PostgreSQL 18) is excluded, and so is
# the owner foreign key added by 0007 (tested with that migration).
# 2 tables + 4 indexes (pk_tenants, pk_campuses, 2 unique) + 6 policies
# + 7 constraints (2 pk, 2 unique, 2 check, 1 fk)
T01_03_OBJECT_COUNT = 2 + 4 + 6 + 7


async def _t01_03_objects(database: DatabaseUnderTest) -> int:
    return int(await _owner_scalar(database, T01_03_OBJECTS, policies=T01_03_POLICIES))


# --- Migration ------------------------------------------------------------------------


async def test_the_tenancy_migration_downgrades_and_upgrades_cleanly(
    migrated_database: DatabaseUnderTest,
) -> None:
    config = migrated_database.alembic_config()
    scripts = ScriptDirectory.from_config(config)
    tenancy = scripts.get_revision(TENANCY_REVISION)
    assert tenancy is not None
    head = scripts.get_current_head()

    assert await _t01_03_objects(migrated_database) == T01_03_OBJECT_COUNT
    await anyio.to_thread.run_sync(command.downgrade, config, str(tenancy.down_revision))
    try:
        assert await _t01_03_objects(migrated_database) == 0
        assert (
            await _owner_scalar(migrated_database, "SELECT version_num FROM alembic_version")
            == tenancy.down_revision
        )
    finally:
        await anyio.to_thread.run_sync(command.upgrade, config, "head")

    assert await _t01_03_objects(migrated_database) == T01_03_OBJECT_COUNT
    assert await _owner_scalar(migrated_database, "SELECT version_num FROM alembic_version") == head
    await anyio.to_thread.run_sync(command.check, config)


# --- Tables, constraints and indexes ---------------------------------------------------


async def test_tables_columns_and_indexes_follow_the_contract(
    migrated_database: DatabaseUnderTest,
) -> None:
    columns = await _owner_scalar(
        migrated_database,
        "SELECT string_agg(table_name || '.' || column_name || ':' || data_type || ':' "
        "|| is_nullable || ':' || coalesce(character_maximum_length::text, '-'), ',' "
        "ORDER BY table_name, ordinal_position) FROM information_schema.columns "
        "WHERE table_name IN ('tenants', 'campuses')",
    )
    indexes = await _owner_scalar(
        migrated_database,
        "SELECT string_agg(indexname, ',' ORDER BY indexname) FROM pg_indexes "
        "WHERE tablename IN ('tenants', 'campuses')",
    )
    owners = await _owner_scalar(
        migrated_database,
        "SELECT string_agg(DISTINCT tableowner, ',') FROM pg_tables "
        "WHERE tablename IN ('tenants', 'campuses')",
    )

    assert columns.split(",") == [
        "campuses.id:uuid:NO:-",
        "campuses.tenant_id:uuid:NO:-",
        "campuses.name:character varying:NO:200",
        "campuses.code:character varying:NO:32",
        "campuses.created_at:timestamp with time zone:NO:-",
        "campuses.updated_at:timestamp with time zone:NO:-",
        "campuses.version:integer:NO:-",
        "tenants.id:uuid:NO:-",
        "tenants.name:character varying:NO:200",
        "tenants.status:character varying:NO:16",
        "tenants.created_at:timestamp with time zone:NO:-",
        "tenants.updated_at:timestamp with time zone:NO:-",
        "tenants.version:integer:NO:-",
        # 0007 (T01-07, D7-1/D7-8): the primary administrator's membership.
        "tenants.owner_membership_id:uuid:YES:-",
    ]
    assert indexes.split(",") == [
        "pk_campuses",
        "pk_tenants",
        "uq_campuses_tenant_id_code",
        "uq_campuses_tenant_id_id",
    ]
    assert owners == urlsplit(migrated_database.owner_url).username


async def test_every_lifecycle_status_is_accepted_and_nothing_else(
    migrated_database: DatabaseUnderTest,
) -> None:
    for status in TenantStatus:
        await _new_tenant(migrated_database, status.value)

    for invalid in ("ARCHIVED", "active", "Trial", ""):
        error = await _owner_execute(
            migrated_database,
            "INSERT INTO tenants (id, name, status, version) VALUES (:id, 'Probe', :status, 1)",
            id=uuid.uuid7(),
            status=invalid,
        )
        assert error is not None
        assert CHECK_VIOLATION in error, invalid


async def test_campus_requires_an_existing_tenant_and_a_code(
    migrated_database: DatabaseUnderTest,
) -> None:
    tenant = await _new_tenant(migrated_database)

    assert FK_VIOLATION in (await _insert_campus(migrated_database, uuid.uuid7(), "MUM") or "")
    assert NOT_NULL_VIOLATION in (await _insert_campus(migrated_database, None, "MUM") or "")
    assert NOT_NULL_VIOLATION in (await _insert_campus(migrated_database, tenant, None) or "")
    assert await _insert_campus(migrated_database, tenant, "MUM") is None


@pytest.mark.parametrize("code", ["mum", "Mum-1", "-MUM", "MUM 1", "MUM_1", "", "A" * 33])
async def test_campus_codes_must_be_upper_case_and_well_formed(
    migrated_database: DatabaseUnderTest, code: str
) -> None:
    tenant = await _new_tenant(migrated_database)

    error = await _insert_campus(migrated_database, tenant, code)

    assert error is not None
    assert CHECK_VIOLATION in error or "too long" in error


async def test_campus_codes_are_unique_per_tenant_only(
    migrated_database: DatabaseUnderTest,
) -> None:
    tenant_a, tenant_b = await _new_tenant(migrated_database), await _new_tenant(migrated_database)

    assert await _insert_campus(migrated_database, tenant_a, "CHN-2") is None
    assert UNIQUE_VIOLATION in (await _insert_campus(migrated_database, tenant_a, "CHN-2") or "")
    assert await _insert_campus(migrated_database, tenant_b, "CHN-2") is None


async def test_tenant_and_id_are_unique_together_for_composite_foreign_keys(
    migrated_database: DatabaseUnderTest,
) -> None:
    definition = await _owner_scalar(
        migrated_database,
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conname = 'uq_campuses_tenant_id_id'",
    )

    assert definition == "UNIQUE (tenant_id, id)"


async def test_a_tenant_with_campuses_cannot_be_deleted(
    migrated_database: DatabaseUnderTest,
) -> None:
    tenant = await _new_tenant(migrated_database)
    assert await _insert_campus(migrated_database, tenant, "KOL") is None
    definition = await _owner_scalar(
        migrated_database,
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conname = 'fk_campuses_tenant_id_tenants'",
    )

    error = await _owner_execute(migrated_database, "DELETE FROM tenants WHERE id = :id", id=tenant)

    assert definition == "FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT"
    assert error is not None
    assert FK_VIOLATION in error


async def test_models_generate_uuid7_timestamps_and_optimistic_versions(
    migrated_database: DatabaseUnderTest,
) -> None:
    async with _engine(migrated_database.app_url) as engine:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        system = RequestContext(realm=Realm.SYSTEM, request_id=uuid.uuid7())
        async with context_transaction(factory, system) as session:
            tenant = Tenant(name="Coastal Nautical Institute")
            session.add(tenant)
        scoped = RequestContext(realm=Realm.SYSTEM, request_id=uuid.uuid7(), tenant_id=tenant.id)
        async with context_transaction(factory, scoped) as session:
            campus = Campus(tenant_id=tenant.id, name="Kochi Campus", code="KOCHI")
            session.add(campus)
        async with context_transaction(factory, scoped) as session:
            loaded = (
                await session.execute(select(Campus).where(Campus.id == campus.id))
            ).scalar_one()
            loaded.name = "Kochi Marine Campus"
            await session.flush()
            await session.refresh(loaded)

    assert tenant.id.version == 7
    assert campus.id.version == 7
    assert tenant.status == TenantStatus.TRIAL
    assert tenant.version == 1
    assert tenant.created_at is not None
    assert loaded.version == 2
    assert loaded.updated_at >= loaded.created_at


# --- Privileges and Row-Level Security -------------------------------------------------

_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")


async def test_runtime_privileges_exclude_delete_and_writes_for_readonly(
    migrated_database: DatabaseUnderTest,
) -> None:
    roles = migrated_database.roles
    for table in ("tenants", "campuses"):
        granted = {
            key: {
                privilege
                for privilege in _PRIVILEGES
                if await _owner_scalar(
                    migrated_database,
                    f"SELECT has_table_privilege('{roles[key]}', '{table}', '{privilege}')",
                )
            }
            for key in ("app", "readonly")
        }
        assert granted == {"app": {"SELECT", "INSERT", "UPDATE"}, "readonly": {"SELECT"}}, table

    for url in (migrated_database.app_url, migrated_database.readonly_url):
        async with _engine(url) as engine, engine.connect() as connection:
            bypass = (
                await connection.execute(
                    text("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
                )
            ).scalar()
        assert bypass is False


async def test_rls_is_enabled_not_forced_with_the_six_policies(
    migrated_database: DatabaseUnderTest,
) -> None:
    flags = await _owner_scalar(
        migrated_database,
        "SELECT string_agg(relname || ':' || relrowsecurity || ':' || relforcerowsecurity, ',' "
        "ORDER BY relname) FROM pg_class WHERE relname IN ('tenants', 'campuses')",
    )
    policies = await _owner_scalar(
        migrated_database,
        "SELECT string_agg(policyname || ':' || cmd || ':' || array_to_string(roles, '+'), ',' "
        "ORDER BY policyname) FROM pg_policies WHERE policyname = ANY(:policies)",
        policies=T01_03_POLICIES,
    )
    app, readonly = migrated_database.roles["app"], migrated_database.roles["readonly"]

    assert flags == "campuses:true:false,tenants:true:false"
    assert policies.split(",") == [
        f"campuses_readonly_tenant_read:SELECT:{readonly}",
        f"campuses_tenant_isolation:ALL:{app}",
        f"tenants_own_read:SELECT:{app}+{readonly}",
        f"tenants_platform_insert:INSERT:{app}",
        f"tenants_platform_read:SELECT:{app}",
        f"tenants_platform_update:UPDATE:{app}",
    ]
