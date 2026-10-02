"""Authorization matrix over HTTP (T01-05; D-B1, ADR-0011 §4, UI contract errors).

Test-only routes use the production building blocks: ``require_permission``
on the route, then a resource load through the request's own transaction
(RLS and the tenant ORM filter) and ``authorize(context, permission,
resource)``. They prove:

* 401 without a session, 403 without the permission, 404 for another
  tenant's or an unpermitted campus's resource — and the 404 is identical to
  the one for a resource that does not exist (IDOR, no existence leak);
* tenant-wide permissions are refused to campus-restricted members (D-B1);
* any permitted campus is reachable whatever the active campus (D-B1);
* tenant identifiers in the request are ignored; suspended tenants and
  memberships lose access; a tenant session never reaches the platform realm;
* denials record ``authz.denied`` and their bodies reveal nothing.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import pytest
from conftest import DatabaseUnderTest
from identity_support import Harness, add_role, assign_role, auth_harness

from app.api.realms import REALM_PREFIXES, Access, realm_router
from app.core.authz import authorize, require_permission
from app.core.context import Realm, current_context
from app.core.db.session import DbSession
from app.core.errors import NotFoundError
from app.modules.institute.models import Campus
from app.modules.institute.permissions import CAMPUS_READ, CAMPUS_UPDATE
from app.modules.platform_identity.permissions import PLATFORM_USER_READ
from app.modules.tenants.permissions import TENANT_PROFILE_READ

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@dataclass(frozen=True)
class CampusResource:
    """A campus as an authorization resource: its campus is itself."""

    tenant_id: uuid.UUID
    campus_id: uuid.UUID


def _probes() -> tuple[Any, Any]:
    tenant = realm_router(Realm.TENANT, access=Access.AUTHENTICATED)

    @tenant.get("/probe/institute", dependencies=[require_permission(TENANT_PROFILE_READ)])
    async def institute() -> dict[str, str | None]:
        context = current_context()
        return {"tenant": str(context.tenant_id)}

    @tenant.get("/probe/campuses/{campus_id}", dependencies=[require_permission(CAMPUS_READ)])
    async def campus(campus_id: uuid.UUID, db: DbSession) -> dict[str, str]:
        found = await db.get(Campus, campus_id)
        if found is None:
            raise NotFoundError()
        authorize(current_context(), CAMPUS_READ, CampusResource(found.tenant_id, found.id))
        return {"code": found.code}

    @tenant.put("/probe/campuses/{campus_id}", dependencies=[require_permission(CAMPUS_UPDATE)])
    async def update_campus(campus_id: uuid.UUID, db: DbSession) -> dict[str, str]:
        found = await db.get(Campus, campus_id)
        if found is None:
            raise NotFoundError()
        authorize(current_context(), CAMPUS_UPDATE, CampusResource(found.tenant_id, found.id))
        return {"code": found.code}

    platform = realm_router(Realm.PLATFORM, access=Access.AUTHENTICATED)

    @platform.get("/probe/users", dependencies=[require_permission(PLATFORM_USER_READ)])
    async def platform_users() -> None:  # pragma: no cover - never reached
        return None

    return tenant, platform


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        tenant, platform = _probes()
        harness.app.include_router(tenant, prefix=REALM_PREFIXES[Realm.TENANT])
        harness.app.include_router(platform, prefix=REALM_PREFIXES[Realm.PLATFORM])
        yield harness


async def _status(h: Harness, path: str) -> int:
    return (await h.client.get(path)).status_code


def _campus(campus_id: uuid.UUID) -> str:
    return f"/api/v1/probe/campuses/{campus_id}"


def _csrf(login: Any) -> dict[str, str]:
    return {"X-CSRF-Token": login.json()["data"]["csrf_token"]}


async def _select_campus(h: Harness, login: Any, campus_id: uuid.UUID) -> None:
    csrf = login.json()["data"]["csrf_token"]
    response = await h.client.put(
        "/api/v1/session/campus",
        json={"campus_id": str(campus_id)},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, response.text


async def _give_only(h: Harness, membership: str, role: str) -> None:
    await h.owner(
        "DELETE FROM membership_roles WHERE membership_id = :m", m=h.world.memberships[membership]
    )
    await assign_role(h.factory, h.world, membership, role)


# --- 401 -------------------------------------------------------------------------------------


async def test_without_a_session_every_protected_route_is_401(h: Harness) -> None:
    for path in ("/api/v1/probe/institute", _campus(h.world.campus_a1)):
        response = await h.client.get(path)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


# --- Allowed, 403 and the D-B1 matrix --------------------------------------------------------


async def test_an_all_campus_owner_reaches_everything_in_its_tenant(h: Harness) -> None:
    await h.login("alice")
    assert await _status(h, "/api/v1/probe/institute") == 200
    assert await _status(h, _campus(h.world.campus_a1)) == 200
    assert await _status(h, _campus(h.world.campus_a2)) == 200


async def test_a_missing_permission_is_403(h: Harness) -> None:
    await add_role(
        h.factory, h.world, "viewer_b", tenant_id=h.world.tenant_b, permissions=("campus.read",)
    )
    await _give_only(h, "carol_b", "viewer_b")
    await h.login("carol")
    assert await _status(h, _campus(h.world.campus_b1)) == 200
    response = await h.client.get("/api/v1/probe/institute")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


async def test_tenant_wide_permissions_are_refused_to_campus_restricted_members(
    h: Harness,
) -> None:
    # bob is Administrator in A but restricted to campus A1.
    await h.login("bob")
    csrf = (await h.client.get("/api/v1/session")).json()["data"]["csrf_token"]
    await h.client.put(
        "/api/v1/session/tenant",
        json={"tenant_id": str(h.world.tenant_a)},
        headers={"X-CSRF-Token": csrf},
    )
    assert await _status(h, "/api/v1/probe/institute") == 403
    assert await _status(h, _campus(h.world.campus_a1)) == 200
    # An unpermitted campus of the same tenant is not found.
    assert await _status(h, _campus(h.world.campus_a2)) == 404


async def test_any_permitted_campus_is_reachable_whatever_the_active_campus(h: Harness) -> None:
    login = await h.login("dave")  # A1 and A2, coordinator
    for active in (h.world.campus_a1, h.world.campus_a2):
        await _select_campus(h, login, active)
        for campus in (h.world.campus_a1, h.world.campus_a2):
            assert await _status(h, _campus(campus)) == 200
            assert (await h.client.put(_campus(campus), headers=_csrf(login))).status_code == 200
        assert await _status(h, _campus(h.world.campus_b1)) == 404
        assert await _status(h, "/api/v1/probe/institute") == 403


# --- 404: tenant isolation, IDOR -------------------------------------------------------------


async def test_another_tenants_resource_is_indistinguishable_from_a_missing_one(
    h: Harness,
) -> None:
    await h.login("alice")
    other = await h.client.get(_campus(h.world.campus_b1))
    missing = await h.client.get(_campus(uuid.uuid7()))
    assert other.status_code == missing.status_code == 404
    strip = ("request_id",)
    body = {k: v for k, v in other.json()["error"].items() if k not in strip}
    assert body == {k: v for k, v in missing.json()["error"].items() if k not in strip}
    assert "GOA" not in other.text
    assert str(h.world.tenant_b) not in other.text


async def test_tenant_identifiers_in_the_request_are_ignored(h: Harness) -> None:
    await h.login("alice")
    forged = str(h.world.tenant_b)
    response = await h.client.get(
        "/api/v1/probe/institute",
        params={"tenant_id": forged},
        headers={"X-Tenant-ID": forged, "X-Campus-ID": str(h.world.campus_b1)},
    )
    assert response.json() == {"tenant": str(h.world.tenant_a)}
    assert await _status(h, _campus(h.world.campus_b1) + f"?tenant_id={forged}") == 404


# --- Denial bodies and audit -----------------------------------------------------------------


async def test_denials_reveal_no_authorization_details_and_are_audited(h: Harness) -> None:
    await _select_campus(h, await h.login("dave"), h.world.campus_a1)
    response = await h.client.get("/api/v1/probe/institute")
    assert response.status_code == 403
    text = response.text.lower()
    for leak in ("tenant.profile.read", "coordinator", "institute owner", "administrator"):
        assert leak not in text
    rows = await h.audit(response)
    denied = [row for row in rows if row.event_type == "authz.denied"]
    assert len(denied) == 1
    assert denied[0]._mapping["metadata"] == {
        "permission": "tenant.profile.read",
        "realm": "tenant",
    }
    assert denied[0].principal_id == h.world.users["dave"]
    assert denied[0].tenant_id == h.world.tenant_a


async def test_allowed_requests_are_not_audited(h: Harness) -> None:
    await h.login("alice")
    response = await h.client.get("/api/v1/probe/institute")
    assert response.status_code == 200
    assert [row for row in await h.audit(response) if row.event_type == "authz.denied"] == []


# --- Tenant/membership status and realm separation -------------------------------------------


async def test_a_suspended_tenant_loses_access(h: Harness) -> None:
    await h.login("alice")
    assert await _status(h, "/api/v1/probe/institute") == 200
    await h.owner("UPDATE tenants SET status = 'SUSPENDED' WHERE id = :t", t=h.world.tenant_a)
    assert await _status(h, "/api/v1/probe/institute") == 401
    assert await _status(h, _campus(h.world.campus_a1)) == 401


async def test_a_suspended_membership_loses_access(h: Harness) -> None:
    await h.login("alice")
    await h.owner(
        "UPDATE tenant_memberships SET status = 'SUSPENDED' WHERE id = :m",
        m=h.world.memberships["alice_a"],
    )
    assert await _status(h, "/api/v1/probe/institute") == 401


async def test_a_tenant_session_never_reaches_the_platform_realm(h: Harness) -> None:
    await h.login("alice")  # Institute owner: every tenant permission
    assert await _status(h, "/api/v1/platform/probe/users") == 401
