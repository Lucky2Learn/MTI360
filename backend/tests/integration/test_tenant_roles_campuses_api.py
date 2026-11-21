"""Tenant roles, permission catalogue, campuses and institute summary over HTTP (T01-08).

Custom roles over the T01-05 access service (system roles immutable, no
escalation); campuses with D-B1 campus scoping (another campus or tenant is
not found; creation is tenant-wide); the read-only institute summary.
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from conftest import DatabaseUnderTest
from identity_support import Harness, add_role, auth_harness
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
    # System roles first (Admissions manager and Counsellor since Phase 02-1, the two
    # finance roles since Phase 02-5).
    assert names[:6] == [
        "Administrator",
        "Admissions manager",
        "Counsellor",
        "Finance manager",
        "Finance officer",
        "Institute owner",
    ]
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
    events = await h.audit(renamed)
    assert [
        (e.event_type, e.tenant_id, e.target_type, e.target_id, e.metadata) for e in events
    ] == [("campus.updated", h.world.tenant_a, "campus", h.world.campus_a1, {"name_changed": True})]
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


async def _campus_row(h: Harness, campus_id: uuid.UUID) -> tuple[str, str, int]:
    rows = await h.owner("SELECT name, code, version FROM campuses WHERE id = :c", c=campus_id)
    return (rows[0][0], rows[0][1], rows[0][2])


async def test_campus_rename_outside_the_members_campuses_is_not_found(h: Harness) -> None:
    csrf = await sign_in(h, "bob", h.world.tenant_a)  # Administrator, campus A1 only (D-B1)
    before = await _campus_row(h, h.world.campus_a2)
    outside = await send(
        h,
        "PATCH",
        f"/api/v1/campuses/{h.world.campus_a2}",
        csrf,
        {"name": "Pune Hinjewadi Campus", "version": before[2]},
    )
    assert outside.status_code == 404
    assert outside.json()["error"]["code"] == "NOT_FOUND"
    assert await h.audit(outside) == []
    assert await _campus_row(h, h.world.campus_a2) == before


async def test_campus_rename_needs_campus_update(h: Harness) -> None:
    await add_role(
        h.factory,
        h.world,
        "campus_reader_a",
        tenant_id=h.world.tenant_a,
        permissions=("campus.read",),
    )
    await add_owner(h, "ivan", h.world.tenant_a, "campus_reader_a")  # all campuses, read only
    csrf = await sign_in(h, "ivan")
    campus = data(await h.client.get(f"/api/v1/campuses/{h.world.campus_a1}"))
    refused = await send(
        h,
        "PATCH",
        f"/api/v1/campuses/{h.world.campus_a1}",
        csrf,
        {"name": "Mumbai Andheri Campus", "version": campus["version"]},
    )
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "PERMISSION_DENIED"
    assert await _campus_row(h, h.world.campus_a1) == (
        campus["name"],
        campus["code"],
        campus["version"],
    )


async def test_campus_rename_validates_the_body(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    before = await _campus_row(h, h.world.campus_a1)
    version = before[2]
    for body in (
        {"name": "", "version": version},
        {"name": "   ", "version": version},
        {"name": "Mumbai Andheri Campus"},
        {"name": "Mumbai Andheri Campus", "version": 0},
        {"name": "Mumbai Andheri Campus", "version": version, "code": "BOM"},  # INC-41
    ):
        response = await send(h, "PATCH", f"/api/v1/campuses/{h.world.campus_a1}", csrf, body)
        assert response.status_code == 422, body
        assert response.json()["error"]["code"] == "VALIDATION_ERROR", body
        assert await h.audit(response) == [], body
    assert await _campus_row(h, h.world.campus_a1) == before


async def test_campus_codes_are_unique_per_tenant_whatever_the_case_or_spacing(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    for code in ("mum", " Mum ", "MUM ", "\tmum"):
        duplicate = await send(
            h, "POST", "/api/v1/campuses", csrf, {"name": "Mumbai Annexe", "code": code}
        )
        assert duplicate.status_code == 409, repr(code)
        assert duplicate.json()["error"]["code"] == "CONFLICT", repr(code)
        assert await h.audit(duplicate) == [], repr(code)
    rows = await h.owner(
        "SELECT count(*) FROM campuses WHERE tenant_id = :t AND code = 'MUM'", t=h.world.tenant_a
    )
    assert rows[0][0] == 1
    # Institute B's code is free in institute A, normalized the same way.
    created = await send(
        h, "POST", "/api/v1/campuses", csrf, {"name": "Goa Campus", "code": " goa "}
    )
    assert data(created, 201)["code"] == "GOA"
