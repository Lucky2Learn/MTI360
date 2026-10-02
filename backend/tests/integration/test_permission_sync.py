"""Registry ↔ database synchronisation (T01-05; D-B4).

Permissions reach the database only through migrations. These tests fail
when code and database drift apart: a permission declared in code but not
migrated (or migrated differently), or system role clones that no longer
match their code templates.
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from conftest import DatabaseUnderTest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.context import Realm, RequestContext
from app.core.db import create_sessionmaker
from app.core.db.session import context_transaction
from app.core.tenancy import system_context
from app.modules.access.catalog import all_permissions
from app.modules.access.models import PermissionRecord
from app.modules.access.service import clone_system_roles
from app.modules.access.templates import system_role_templates
from app.modules.tenants.models import Tenant

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@pytest.fixture
async def app_db(
    migrated_database: DatabaseUnderTest,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(migrated_database.app_url, poolclass=NullPool)
    try:
        yield create_sessionmaker(engine)
    finally:
        await engine.dispose()


async def test_the_database_catalogue_matches_the_code_registry(
    app_db: async_sessionmaker[AsyncSession],
) -> None:
    context = RequestContext(realm=Realm.TENANT, request_id=uuid.uuid7())
    async with context_transaction(app_db, context) as db:
        rows = (await db.execute(select(PermissionRecord))).scalars().all()
        database = {(row.realm, row.code): (row.scope, row.module, row.description) for row in rows}
    code = {
        p.key: (p.scope.value if p.scope else None, p.module, p.description)
        for p in all_permissions()
    }
    assert database == code


async def test_cloned_system_roles_match_the_templates(
    app_db: async_sessionmaker[AsyncSession],
) -> None:
    async with system_context(app_db) as db:
        tenant = Tenant(name=f"Coastal Maritime Institute {uuid.uuid7().hex[-8:]}", status="ACTIVE")
        db.add(tenant)
    async with system_context(app_db, tenant_id=tenant.id) as db:
        created = await clone_system_roles(db, tenant.id)
    async with system_context(app_db, tenant_id=tenant.id) as db:
        rows = (
            await db.execute(
                text(
                    "SELECT r.template_code, r.name, r.is_system, rp.permission_code "
                    "FROM roles r JOIN role_permissions rp ON rp.role_id = r.id "
                    "WHERE r.tenant_id = :tenant"
                ),
                {"tenant": tenant.id},
            )
        ).all()
    clones: dict[str, tuple[str, set[str]]] = {}
    for template_code, name, is_system, code in rows:
        assert is_system
        clones.setdefault(template_code, (name, set()))[1].add(code)
    assert set(created) == set(clones)
    assert clones == {t.code.value: (t.name, set(t.permissions)) for t in system_role_templates()}


async def test_migrated_clones_match_the_templates(migrated_database: DatabaseUnderTest) -> None:
    """Every tenant's system roles hold exactly the template permissions."""
    engine = create_async_engine(migrated_database.owner_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT DISTINCT r.template_code, "
                        "array_agg(rp.permission_code ORDER BY rp.permission_code) "
                        "FROM roles r JOIN role_permissions rp ON rp.role_id = r.id "
                        "WHERE r.is_system GROUP BY r.id, r.template_code"
                    )
                )
            ).all()
    finally:
        await engine.dispose()
    expected = {t.code.value: sorted(t.permissions) for t in system_role_templates()}
    for template_code, codes in rows:
        assert list(codes) == expected[template_code], template_code
