"""Session permissions and roles (T01-05; UI contract §2, D-B1).

Through the real HTTP stack: the session exposes the sorted effective
permissions and the roles (name and ``is_system`` only) of the **active**
institute, the realm guard puts the same permissions and campus scope in the
request context, a tenant switch changes them, a campus switch does not, and
a role change is visible on the next session read.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from conftest import DatabaseUnderTest
from identity_support import Harness, assign_role, auth_harness

from app.api.realms import REALM_PREFIXES, Access, realm_router
from app.core.context import Realm, current_context

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

ALL_TENANT = [
    "audit.read",
    "campus.create",
    "campus.read",
    "campus.update",
    "course.manage",  # Phase 02-1
    "course.read",
    "lead.assign",
    "lead.create",
    "lead.read",
    "lead.update",
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
]
ADMIN = [code for code in ALL_TENANT if code != "role.delete"]
CAMPUS_ONLY = ["campus.read", "campus.update"]
# A campus-restricted Administrator keeps every campus-scoped permission (D-B1): since
# Phase 02-1 also course.read and the lead permissions, never the tenant-wide course.manage.
RESTRICTED_ADMIN = sorted(
    [*CAMPUS_ONLY, "course.read", "lead.assign", "lead.create", "lead.read", "lead.update"]
)
OWNER_ROLE = {"name": "Institute owner", "is_system": True}
ADMIN_ROLE = {"name": "Administrator", "is_system": True}


def _authz_probe() -> Any:
    probe = realm_router(Realm.TENANT, access=Access.AUTHENTICATED)

    @probe.get("/probe/authz", tags=["probe"])
    async def probe_authz() -> dict[str, Any]:
        context = current_context()
        return {
            "permissions": sorted(context.permissions),
            "all_campuses": context.all_campuses,
            "campus_ids": sorted(str(campus) for campus in context.campus_ids),
        }

    return probe


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        harness.app.include_router(_authz_probe(), prefix=REALM_PREFIXES[Realm.TENANT])
        yield harness


def _data(response: Any) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()["data"]
    return data


async def _switch(h: Harness, path: str, body: dict[str, Any], csrf: str) -> dict[str, Any]:
    return _data(await h.client.put(path, json=body, headers={"X-CSRF-Token": csrf}))


async def test_an_owner_sees_every_tenant_permission_sorted(h: Harness) -> None:
    session = _data(await h.login("alice"))
    assert session["status"] == "ready"
    assert session["permissions"] == ALL_TENANT
    assert session["roles"] == [OWNER_ROLE]
    assert _data(await h.client.get("/api/v1/session"))["permissions"] == ALL_TENANT


async def test_the_session_exposes_no_ids_or_secrets_for_roles(h: Harness) -> None:
    response = await h.login("alice")
    session = _data(response)
    for role in session["roles"]:
        assert set(role) == {"name", "is_system"}
    body = response.text
    assert str(h.world.roles["owner_a"]) not in body
    for word in ("password", "hash", "template", "role_id", "permission_id"):
        assert word not in body.lower()


async def test_the_guard_puts_the_same_authorization_in_the_context(h: Harness) -> None:
    await h.login("alice")
    probe = (await h.client.get("/api/v1/probe/authz")).json()
    assert probe["permissions"] == ALL_TENANT
    assert probe["all_campuses"] is True
    assert probe["campus_ids"] == sorted([str(h.world.campus_a1), str(h.world.campus_a2)])


async def test_without_an_active_institute_there_are_no_permissions(h: Harness) -> None:
    session = _data(await h.login("bob"))
    assert session["status"] == "institute_selection_required"
    assert (session["permissions"], session["roles"]) == ([], [])


async def test_a_tenant_switch_changes_the_authorization_state(h: Harness) -> None:
    csrf = _data(await h.login("bob"))["csrf_token"]
    in_b = await _switch(h, "/api/v1/session/tenant", {"tenant_id": str(h.world.tenant_b)}, csrf)
    assert in_b["permissions"] == ADMIN
    assert in_b["roles"] == [ADMIN_ROLE]
    assert (await h.client.get("/api/v1/probe/authz")).json()["permissions"] == ADMIN

    csrf = in_b["csrf_token"]  # the session was rotated
    in_a = await _switch(h, "/api/v1/session/tenant", {"tenant_id": str(h.world.tenant_a)}, csrf)
    # Administrator in A, but restricted to one campus: campus permissions only (D-B1).
    assert in_a["permissions"] == RESTRICTED_ADMIN
    assert "course.manage" not in in_a["permissions"]
    assert in_a["roles"] == [ADMIN_ROLE]
    probe = (await h.client.get("/api/v1/probe/authz")).json()
    assert probe == {
        "permissions": RESTRICTED_ADMIN,
        "all_campuses": False,
        "campus_ids": [str(h.world.campus_a1)],
    }


async def test_a_campus_switch_does_not_change_permissions(h: Harness) -> None:
    session = _data(await h.login("dave"))
    assert session["status"] == "campus_selection_required"
    assert session["permissions"] == CAMPUS_ONLY  # member.read is tenant-wide: filtered
    csrf = session["csrf_token"]
    seen = []
    for campus in (h.world.campus_a1, h.world.campus_a2, h.world.campus_a1):
        view = await _switch(h, "/api/v1/session/campus", {"campus_id": str(campus)}, csrf)
        probe = (await h.client.get("/api/v1/probe/authz")).json()
        seen.append((view["permissions"], probe["permissions"], probe["campus_ids"]))
    permitted = sorted([str(h.world.campus_a1), str(h.world.campus_a2)])
    assert seen == [(CAMPUS_ONLY, CAMPUS_ONLY, permitted)] * 3


async def test_a_role_change_is_visible_on_the_next_session_read(h: Harness) -> None:
    session = _data(await h.login("carol"))
    assert session["roles"] == [OWNER_ROLE]
    # Another role for carol (multiple roles): the session reread lists both.
    await assign_role(h.factory, h.world, "carol_b", "admin_b")
    reread = _data(await h.client.get("/api/v1/session"))
    assert reread["roles"] == [ADMIN_ROLE, OWNER_ROLE]
    assert reread["permissions"] == ALL_TENANT
    # Taking every role away removes every permission at once.
    await h.owner(
        "DELETE FROM membership_roles WHERE membership_id = :membership",
        membership=h.world.memberships["carol_b"],
    )
    emptied = _data(await h.client.get("/api/v1/session"))
    assert (emptied["permissions"], emptied["roles"]) == ([], [])
    assert (await h.client.get("/api/v1/probe/authz")).json()["permissions"] == []
