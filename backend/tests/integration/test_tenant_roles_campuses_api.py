"""Tenant roles, permission catalogue, campuses and institute summary over HTTP (T01-08).

Custom roles over the T01-05 access service (system roles immutable, no
escalation); campuses with D-B1 campus scoping (another campus or tenant is
not found; creation is tenant-wide); the read-only institute summary.
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from conftest import DatabaseUnderTest
from identity_support import Harness, auth_harness
from tenant_admin_support import add_owner, data, send, sign_in

from app.modules.access.catalog import tenant_permissions

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        yield harness


# --- Institute ---------------------------------------------------------------------------------


async def test_the_institute_summary_is_the_active_tenant(h: Harness) -> None:
    await sign_in(h, "carol")
    summary = data(await h.client.get("/api/v1/institute"))
    assert summary == {
        "name": f"Konkan Nautical Institute {h.world.suffix}",
        "status": "TRIAL",
        "trial": True,
    }


# --- Roles -------------------------------------------------------------------------------------


async def test_roles_and_the_permission_catalogue(h: Harness) -> None:
    await sign_in(h, "alice")
    catalogue = (await h.client.get("/api/v1/permissions")).json()["data"]
    assert [p["code"] for p in catalogue] == sorted(p.code for p in tenant_permissions())
    roles = (await h.client.get("/api/v1/roles")).json()["data"]
    names = [role["name"] for role in roles]
    # System roles first (Admissions manager and Counsellor since Phase 02-1).
    assert names[:4] == ["Administrator", "Admissions manager", "Counsellor", "Institute owner"]
    owner = next(role for role in roles if role["name"] == "Institute owner")
    assert owner["is_system"] is True
    assert owner["member_count"] == 1
    assert str(h.world.roles["owner_b"]) not in str(roles)
    other = await h.client.get(f"/api/v1/roles/{h.world.roles['owner_b']}")
    assert other.status_code == 404


async def test_custom_roles_are_created_changed_and_deleted(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    created = await send(
        h,
        "POST",
        "/api/v1/roles",
        csrf,
        {"name": "Training Coordinator", "permissions": ["campus.read", "member.read"]},
    )
    role = data(created, 201)
    assert role["permissions"] == ["campus.read", "member.read"]
    assert [e.event_type for e in await h.audit(created)] == ["role.created"]
    updated = await send(
        h,
        "PATCH",
        f"/api/v1/roles/{role['id']}",
        csrf,
        {"version": role["version"], "permissions": ["campus.read"]},
    )
    assert data(updated)["permissions"] == ["campus.read"]
    stale = await send(
        h, "PATCH", f"/api/v1/roles/{role['id']}", csrf, {"version": role["version"], "name": "X"}
    )
    assert stale.status_code == 409
    deleted = await send(
        h, "DELETE", f"/api/v1/roles/{role['id']}?version={role['version'] + 1}", csrf
    )
    assert deleted.status_code == 204
    assert (await h.client.get(f"/api/v1/roles/{role['id']}")).status_code == 404


async def test_system_roles_and_escalation_are_refused(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    system = await send(
        h,
        "PATCH",
        f"/api/v1/roles/{h.world.roles['admin_a']}",
        csrf,
        {"version": 1, "name": "Renamed"},
    )
    assert system.status_code == 403
    await add_owner(h, "gina", h.world.tenant_a, "admin_a")  # Administrator: no role.delete
    csrf = await sign_in(h, "gina")
    escalation = await send(
        h, "POST", "/api/v1/roles", csrf, {"name": "Deleter", "permissions": ["role.delete"]}
    )
    assert escalation.status_code == 403
    unknown = await send(
        h, "POST", "/api/v1/roles", csrf, {"name": "Platform", "permissions": ["tenant.read"]}
    )
    assert unknown.status_code == 422
    smuggled = await send(
        h, "POST", "/api/v1/roles", csrf, {"name": "X", "permissions": [], "is_system": True}
    )
    assert smuggled.status_code == 422


# --- Campuses (D-B1) ---------------------------------------------------------------------------


async def test_campuses_follow_the_members_campus_scope(h: Harness) -> None:
    await sign_in(h, "alice")
    all_campuses = (await h.client.get("/api/v1/campuses")).json()["data"]
    assert {c["code"] for c in all_campuses} == {"MUM", "PUNE"}
    await sign_in(h, "bob", h.world.tenant_a)  # A1 only
    mine = (await h.client.get("/api/v1/campuses")).json()["data"]
    assert [c["id"] for c in mine] == [str(h.world.campus_a1)]
    outside = await h.client.get(f"/api/v1/campuses/{h.world.campus_a2}")
    foreign = await h.client.get(f"/api/v1/campuses/{h.world.campus_b1}")
    missing = await h.client.get(f"/api/v1/campuses/{uuid.uuid7()}")
    assert outside.status_code == foreign.status_code == missing.status_code == 404


async def test_campus_creation_is_tenant_wide_and_codes_are_unique(h: Harness) -> None:
    csrf = await sign_in(h, "bob", h.world.tenant_a)  # campus-restricted: no campus.create
    refused = await send(h, "POST", "/api/v1/campuses", csrf, {"name": "Goa", "code": "GOA2"})
    assert refused.status_code == 403
    csrf = await sign_in(h, "alice")
    code = f"VSK{uuid.uuid7().hex[-4:]}".upper()
    created = await send(
        h, "POST", "/api/v1/campuses", csrf, {"name": "Visakhapatnam Campus", "code": code.lower()}
    )
    campus = data(created, 201)
    assert campus["code"] == code
    assert [e.event_type for e in await h.audit(created)] == ["campus.created"]
    duplicate = await send(h, "POST", "/api/v1/campuses", csrf, {"name": "Copy", "code": code})
    assert duplicate.status_code == 409
    invalid = await send(h, "POST", "/api/v1/campuses", csrf, {"name": "Bad", "code": "-x y"})
    assert invalid.status_code == 422
    smuggled = await send(
        h,
        "POST",
        "/api/v1/campuses",
        csrf,
        {"name": "X", "code": "X1", "tenant_id": str(h.world.tenant_b)},
    )
    assert smuggled.status_code == 422


async def test_campus_rename_is_versioned_and_scoped(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    campus = data(await h.client.get(f"/api/v1/campuses/{h.world.campus_a1}"))
    renamed = await send(
        h,
        "PATCH",
        f"/api/v1/campuses/{h.world.campus_a1}",
        csrf,
        {"name": "Mumbai Andheri Campus", "version": campus["version"]},
    )
    body = data(renamed)
    assert (body["name"], body["code"], body["version"]) == (
        "Mumbai Andheri Campus",
        campus["code"],
        campus["version"] + 1,
    )
    stale = await send(
        h,
        "PATCH",
        f"/api/v1/campuses/{h.world.campus_a1}",
        csrf,
        {"name": "Again", "version": campus["version"]},
    )
    assert stale.status_code == 409
    foreign = await send(
        h, "PATCH", f"/api/v1/campuses/{h.world.campus_b1}", csrf, {"name": "X", "version": 1}
    )
    assert foreign.status_code == 404
