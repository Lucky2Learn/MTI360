"""Realm guards and route coverage (T01-01; ADR-0005, ADR-0006, tenancy.md §8).

* Every authenticated realm denies by default (no authentication exists yet),
  before validation and before the handler runs.
* The public realm is anonymous and gets a trusted public context.
* No route under /api escapes a realm guard, and every route's guard matches
  the realm that owns its path prefix. This meta-test runs on the real
  application, so every route added by later tasks is covered automatically.
* Code that needs the request context (the database session) cannot run on a
  route mounted outside the realm routers.
"""

import pytest
from conftest import GUARDED_REALMS
from fastapi import FastAPI
from fastapi.routing import iter_route_contexts
from httpx import ASGITransport, AsyncClient

from app.api.realms import REALM_PREFIXES, Access, realm_for_path, realm_router, route_realm
from app.core.config import Settings
from app.core.context import Realm
from app.core.db.session import DbSession
from app.main import create_app

pytestmark = pytest.mark.anyio


def guard_violations(app: FastAPI) -> list[str]:
    """Routes under /api without a guard, or guarded by the wrong realm."""
    problems: list[str] = []
    for route in iter_route_contexts(app.routes):
        path = route.path or ""
        if not path.startswith("/api"):
            continue
        guard = route_realm(route)
        owner = realm_for_path(path)
        if guard is None:
            problems.append(f"unguarded: {path}")
        elif guard[0] is not owner:
            problems.append(f"{path}: guarded as {guard[0].value}, owned by {owner}")
    return problems


def api_paths(app: FastAPI) -> set[str]:
    return {
        route.path
        for route in iter_route_contexts(app.routes)
        if route.path is not None and route.path.startswith("/api")
    }


def test_every_api_route_of_the_application_is_guarded_by_its_realm(
    test_settings: Settings,
) -> None:
    assert guard_violations(create_app(test_settings)) == []


def test_the_coverage_check_sees_routes_inside_included_routers(probe_app: FastAPI) -> None:
    # Guards against a vacuous pass: FastAPI keeps included routers as lazy
    # entries, so the check must enumerate their effective routes.
    paths = api_paths(probe_app)

    assert "/api/v1/public/probe/rows" in paths
    for realm in GUARDED_REALMS:
        assert f"{REALM_PREFIXES[realm]}/probe/protected" in paths
    assert guard_violations(probe_app) == []


def test_the_coverage_check_detects_unguarded_and_misplaced_routes(
    test_settings: Settings,
) -> None:
    app = create_app(test_settings)

    @app.get("/api/v1/rogue")
    async def rogue() -> None:  # pragma: no cover - never called
        return None

    misplaced = realm_router(Realm.PUBLIC, access=Access.ANONYMOUS)

    @misplaced.get("/misplaced")
    async def misplaced_route() -> None:  # pragma: no cover - never called
        return None

    app.include_router(misplaced, prefix=REALM_PREFIXES[Realm.PLATFORM])

    assert guard_violations(app) == [
        "unguarded: /api/v1/rogue",
        "/api/v1/platform/misplaced: guarded as public, owned by platform",
    ]


def test_realm_prefixes_follow_adr_0006() -> None:
    assert REALM_PREFIXES == {
        Realm.PLATFORM: "/api/v1/platform",
        Realm.STUDENT: "/api/v1/student",
        Realm.PUBLIC: "/api/v1/public",
        Realm.WEBHOOK: "/api/v1/webhooks",
        Realm.TENANT: "/api/v1",
    }
    assert realm_for_path("/api/v1/platform/tenants") is Realm.PLATFORM
    assert realm_for_path("/api/v1/platformx") is Realm.TENANT
    assert realm_for_path("/api/v1/campuses") is Realm.TENANT
    assert realm_for_path("/health") is None


@pytest.mark.parametrize("realm", GUARDED_REALMS)
async def test_authenticated_realms_deny_by_default(
    probe_client: AsyncClient, realm: Realm
) -> None:
    path = f"{REALM_PREFIXES[realm]}/probe/protected"

    read = await probe_client.get(path)
    # Invalid body: the guard rejects before validation, so nothing about the
    # schema is revealed to an unauthenticated caller.
    write = await probe_client.post(path, json={"unexpected": True})

    for response in (read, write):
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


async def test_a_tenant_id_cannot_open_a_guarded_realm(probe_client: AsyncClient) -> None:
    response = await probe_client.get(
        "/api/v1/probe/protected",
        params={"tenant_id": "0199aaaa-bbbb-7ccc-8ddd-eeeeeeeeeeee"},
        headers={"X-Tenant-ID": "0199aaaa-bbbb-7ccc-8ddd-eeeeeeeeeeee"},
    )

    assert response.status_code == 401


async def test_public_realm_is_anonymous(probe_client: AsyncClient) -> None:
    response = await probe_client.get("/api/v1/public/probe/context")

    assert response.status_code == 200
    assert response.json()["data"]["realm"] == "public"


async def test_database_session_requires_a_realm_context(test_settings: Settings) -> None:
    app = create_app(test_settings)

    @app.get("/outside-realms")
    async def outside(session: DbSession) -> None:  # pragma: no cover - never reached
        raise AssertionError("must not obtain a session")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get("/outside-realms")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"


def test_realm_router_rejects_invalid_configurations() -> None:
    with pytest.raises(ValueError, match="system realm"):
        realm_router(Realm.SYSTEM)
    with pytest.raises(ValueError, match="webhook realm has no anonymous routes"):
        realm_router(Realm.WEBHOOK, access=Access.ANONYMOUS)
