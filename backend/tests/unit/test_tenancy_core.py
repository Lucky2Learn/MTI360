"""Tenancy core without a database (T01-03; ADR-0014).

The ORM filter and the repository check the trusted tenant before any SQL is
sent, so these tests use an engine that never connects. Database behaviour is
covered by ``tests/integration/test_tenancy_isolation.py``.
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import aliased

from app.core.context import (
    Realm,
    RequestContext,
    context_scope,
    current_context,
    optional_context,
)
from app.core.db.session import CONTEXT_INFO_KEY, session_context
from app.core.tenancy import (
    MissingTenantContextError,
    SystemContextError,
    TenantMismatchError,
    TenantScopedRepository,
    system_context,
    trusted_tenant_id,
)
from app.modules.institute.models import Campus

pytestmark = pytest.mark.anyio

# Port 9 (discard) on loopback: nothing is ever sent; the engine never connects.
UNREACHABLE = "postgresql+asyncpg://nobody:nothing@127.0.0.1:9/none"


class CampusRepository(TenantScopedRepository[Campus]):
    model = Campus


def _context(realm: Realm = Realm.TENANT, tenant: uuid.UUID | None = None) -> RequestContext:
    return RequestContext(realm=realm, request_id=uuid.uuid7(), tenant_id=tenant)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(UNREACHABLE)
    try:
        async with async_sessionmaker(engine)() as session:
            yield session
    finally:
        await engine.dispose()


# --- Trusted tenant of a session -------------------------------------------------------


async def test_the_trusted_tenant_comes_only_from_the_session_context(
    session: AsyncSession,
) -> None:
    tenant = uuid.uuid7()

    with pytest.raises(MissingTenantContextError):
        trusted_tenant_id(session)
    session.info[CONTEXT_INFO_KEY] = _context(Realm.PLATFORM)
    with pytest.raises(MissingTenantContextError):
        trusted_tenant_id(session)
    session.info[CONTEXT_INFO_KEY] = _context(tenant=tenant)
    assert trusted_tenant_id(session) == tenant


async def test_a_foreign_object_in_session_info_is_not_a_context(session: AsyncSession) -> None:
    session.info[CONTEXT_INFO_KEY] = {"tenant_id": str(uuid.uuid7())}

    assert session_context(session) is None


# --- ORM filter -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "statement",
    [
        select(Campus),
        select(aliased(Campus)),
        update(Campus).values(name="Renamed Campus"),
        delete(Campus),
    ],
    ids=["select", "alias", "bulk-update", "bulk-delete"],
)
async def test_tenant_scoped_orm_statements_fail_closed_without_a_tenant(
    session: AsyncSession, statement: object
) -> None:
    for context in (None, _context(Realm.PLATFORM), _context(Realm.SYSTEM)):
        if context is not None:
            session.info[CONTEXT_INFO_KEY] = context
        with pytest.raises(MissingTenantContextError):
            await session.execute(statement)  # type: ignore[call-overload]


# --- Repository -----------------------------------------------------------------------


def test_the_repository_has_no_delete_operation() -> None:
    operations = {name for name in dir(TenantScopedRepository) if not name.startswith("_")}

    assert operations == {"add", "count", "find", "get", "list", "select", "tenant_id"}
    assert not any("delete" in name or "remove" in name for name in operations)


async def test_the_repository_requires_a_tenant_context(session: AsyncSession) -> None:
    repository = CampusRepository(session)

    with pytest.raises(MissingTenantContextError):
        repository.select()
    with pytest.raises(MissingTenantContextError):
        await repository.find(uuid.uuid7())
    with pytest.raises(MissingTenantContextError):
        await repository.add(Campus(name="Pune Campus", code="PUNE"))


async def test_the_repository_rejects_an_entity_of_another_tenant(session: AsyncSession) -> None:
    session.info[CONTEXT_INFO_KEY] = _context(tenant=uuid.uuid7())
    campus = Campus(tenant_id=uuid.uuid7(), name="Goa Campus", code="GOA")

    with pytest.raises(TenantMismatchError):
        await CampusRepository(session).add(campus)
    assert campus not in session


# --- Context binding and system_context ------------------------------------------------


def test_context_scope_restores_the_previous_context_even_on_error() -> None:
    outer, inner = _context(Realm.SYSTEM), _context(Realm.SYSTEM)

    seen: list[RequestContext] = []

    def failing_job() -> None:
        with context_scope(inner):
            seen.append(current_context())
            raise RuntimeError("job failed")

    assert optional_context() is None
    with context_scope(outer):
        with pytest.raises(RuntimeError):
            failing_job()
        assert current_context() is outer
    assert seen == [inner]
    assert optional_context() is None


@pytest.mark.parametrize("realm", [r for r in Realm if r is not Realm.SYSTEM])
async def test_system_context_refuses_to_run_inside_a_request(realm: Realm) -> None:
    request = _context(realm, uuid.uuid7())
    factory = async_sessionmaker(create_async_engine(UNREACHABLE))

    with context_scope(request):
        with pytest.raises(SystemContextError):
            async with system_context(factory, tenant_id=uuid.uuid7()):
                pytest.fail("system_context must not open inside a request")
        assert current_context() is request


async def test_system_context_accepts_only_a_uuid_tenant() -> None:
    factory = async_sessionmaker(create_async_engine(UNREACHABLE))

    with pytest.raises(TypeError):
        async with system_context(factory, tenant_id="' OR true --"):  # type: ignore[arg-type]
            pytest.fail("a string tenant must be rejected")
    assert optional_context() is None
