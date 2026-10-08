"""Cross-tenant isolation of every course and lead route (Phase 02-1; INC-46).

Institute B (Carol, its owner) owns a course, a lead and a follow-up. Alice,
the owner of institute A with every permission, calls every route with B's
identifiers: reads and changes are **not found** (404, indistinguishable from
a missing row), lists and lookups contain none of B's rows, B's references
are refused in A's writes, and B's rows are unchanged afterwards. Each test is
named in ``tests/cross_tenant_registry.py``; the meta-test
``tests/security/test_cross_tenant_registry.py`` keeps the two in step.

A platform session never reaches these tenant routes.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from conftest import DatabaseUnderTest
from courses_leads_support import COURSES, FOLLOW_UPS, LEADS, fake_mobile, new_course, new_lead
from identity_support import Harness, auth_harness
from platform_support import platform_harness
from tenant_admin_support import data, send, sign_in

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@dataclass
class Other:
    """Institute B's rows, seen from institute A."""

    course: dict[str, Any]
    lead: dict[str, Any]
    follow_up: dict[str, Any]
    email: str


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        yield harness


@pytest.fixture
async def b(h: Harness) -> Other:
    csrf = await sign_in(h, "carol")
    course = await new_course(h, csrf, f"B{uuid.uuid7().hex[-7:]}".upper())
    email = f"other.{uuid.uuid7().hex[-6:]}@example.com"
    lead = await new_lead(
        h,
        csrf,
        full_name=f"Tenant B {uuid.uuid7().hex[-6:]}",
        email=email,
        interested_course_id=course["id"],
        campus_id=str(h.world.campus_b1),
        owner="me",
    )
    follow_up = data(
        await send(
            h,
            "POST",
            f"{LEADS}/{lead['id']}/follow-ups",
            csrf,
            {"due_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(), "kind": "CALL"},
        ),
        201,
    )
    return Other(course, lead, follow_up, email)


async def _alice(h: Harness) -> str:
    return await sign_in(h, "alice")


async def _unchanged(h: Harness, table: str, row: dict[str, Any]) -> None:
    rows = await h.owner(f"SELECT version FROM {table} WHERE id = :id", id=row["id"])  # noqa: S608
    assert rows[0][0] == row["version"], table


async def _activity_count(h: Harness, lead_id: str) -> int:
    rows = await h.owner("SELECT count(*) FROM lead_activities WHERE lead_id = :l", l=lead_id)
    return int(rows[0][0])


def _codes(response: Any) -> set[tuple[str, str]]:
    assert response.status_code == 422, response.text
    return {(d["field"], d["code"]) for d in response.json()["error"]["details"]}


# --- Courses -------------------------------------------------------------------------------


async def test_course_list_holds_no_other_tenant_course(h: Harness, b: Other) -> None:
    await _alice(h)
    for params in ({"q": b.course["code"]}, {"limit": 100}):
        listed = await h.client.get(COURSES, params=params)
        assert b.course["id"] not in listed.text, params
    assert data(await h.client.get(COURSES, params={"q": b.course["code"]})) == []


async def test_course_create_ignores_a_body_tenant(h: Harness, b: Other) -> None:
    csrf = await _alice(h)
    body = {"code": b.course["code"], "name": "Same code", "category": "OTHER"}
    smuggled = await send(h, "POST", COURSES, csrf, body | {"tenant_id": str(h.world.tenant_b)})
    assert smuggled.status_code == 422
    # The same code is free in A (unique per tenant) and the course belongs to A.
    created = data(await send(h, "POST", COURSES, csrf, body), 201)
    owner = await h.owner("SELECT tenant_id FROM courses WHERE id = :id", id=created["id"])
    assert owner[0][0] == h.world.tenant_a


async def test_other_tenant_course_reads_are_not_found(h: Harness, b: Other) -> None:
    await _alice(h)
    missing = await h.client.get(f"{COURSES}/{uuid.uuid7()}")
    other = await h.client.get(f"{COURSES}/{b.course['id']}")
    assert (other.status_code, other.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert other.json()["error"]["message"] == missing.json()["error"]["message"]


async def test_other_tenant_course_changes_are_not_found(h: Harness, b: Other) -> None:
    csrf = await _alice(h)
    path = f"{COURSES}/{b.course['id']}"
    version = b.course["version"]
    for method, suffix, body in (
        ("PATCH", "", {"name": "Hijacked", "version": version}),
        ("POST", "/status", {"status": "ARCHIVED", "version": version}),
    ):
        response = await send(h, method, f"{path}{suffix}", csrf, body)
        assert response.status_code == 404, (method, suffix)
    await _unchanged(h, "courses", b.course)


# --- Leads ---------------------------------------------------------------------------------


async def test_lead_list_holds_no_other_tenant_lead(h: Harness, b: Other) -> None:
    await _alice(h)
    for params in (
        {"q": b.lead["full_name"]},
        {"q": b.email},
        {"course": b.course["id"]},
        {"campus": str(h.world.campus_b1)},
        {"owner": str(h.world.memberships["carol_b"])},
        {"limit": 100},
    ):
        listed = await h.client.get(LEADS, params=params)
        assert listed.status_code == 200, params
        assert b.lead["id"] not in listed.text, params


async def test_lead_create_rejects_other_tenant_references(h: Harness, b: Other) -> None:
    csrf = await _alice(h)
    base = {"full_name": "Arjun Nair", "source": "PHONE"}
    cases = (
        ({"interested_course_id": b.course["id"]}, ("interested_course_id", "course_not_active")),
        ({"campus_id": str(h.world.campus_b1)}, ("campus_id", "campus_not_available")),
        ({"owner": str(h.world.memberships["carol_b"])}, ("owner", "owner_not_eligible")),
    )
    for extra, expected in cases:
        response = await send(h, "POST", LEADS, csrf, base | {"mobile": fake_mobile()} | extra)
        assert _codes(response) == {expected}, extra
    smuggled = base | {"mobile": fake_mobile(), "tenant_id": str(h.world.tenant_b)}
    assert (await send(h, "POST", LEADS, csrf, smuggled)).status_code == 422


async def test_duplicate_check_never_matches_another_tenant(h: Harness, b: Other) -> None:
    csrf = await _alice(h)
    check = await send(
        h,
        "POST",
        f"{LEADS}/duplicate-check",
        csrf,
        {"mobile": b.lead["mobile"], "email": b.email.upper()},
    )
    assert data(check) == {"candidates": []}


async def test_assignees_never_include_another_tenant(h: Harness, b: Other) -> None:
    await _alice(h)
    pool = data(await h.client.get(f"{LEADS}/assignees"))["items"]
    ids = {item["membership_id"] for item in pool}
    assert str(h.world.memberships["carol_b"]) not in ids
    assert str(h.world.memberships["bob_b"]) not in ids
    other = await h.client.get(f"{LEADS}/assignees", params={"campus_id": str(h.world.campus_b1)})
    assert _codes(other) == {("campus_id", "campus_not_available")}


async def test_other_tenant_lead_reads_are_not_found(h: Harness, b: Other) -> None:
    await _alice(h)
    for suffix in ("", "/follow-ups", "/activity"):
        response = await h.client.get(f"{LEADS}/{b.lead['id']}{suffix}")
        assert response.status_code == 404, suffix
        assert b.lead["full_name"] not in response.text


async def test_other_tenant_lead_changes_are_not_found(h: Harness, b: Other) -> None:
    csrf = await _alice(h)
    lead_b, version = b.lead["id"], b.lead["version"]
    before = await _activity_count(h, lead_b)
    due = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    for method, suffix, body in (
        ("PATCH", "", {"city": "Hijacked", "version": version}),
        ("POST", "/transition", {"to_status": "LOST", "reason": "x", "version": version}),
        ("POST", "/assign", {"owner_membership_id": None, "campus_id": None, "version": version}),
        ("POST", "/follow-ups", {"due_at": due, "kind": "CALL"}),
        ("POST", "/notes", {"body": "Hijacked"}),
    ):
        response = await send(h, method, f"{LEADS}/{lead_b}{suffix}", csrf, body)
        assert response.status_code == 404, (method, suffix)
    await _unchanged(h, "leads", b.lead)
    assert await _activity_count(h, lead_b) == before
    # B's lead and members cannot be referenced from A's own lead either.
    own = await new_lead(h, csrf)
    duplicate = await send(
        h,
        "POST",
        f"{LEADS}/{own['id']}/transition",
        csrf,
        {"to_status": "DUPLICATE", "duplicate_of_lead_id": lead_b, "version": own["version"]},
    )
    assert _codes(duplicate) == {("duplicate_of_lead_id", "duplicate_target_invalid")}
    assign = await send(
        h,
        "POST",
        f"{LEADS}/{own['id']}/assign",
        csrf,
        {
            "owner_membership_id": str(h.world.memberships["carol_b"]),
            "campus_id": None,
            "version": own["version"],
        },
    )
    assert _codes(assign) == {("owner", "owner_not_eligible")}
    follow_up = await send(
        h,
        "POST",
        f"{LEADS}/{own['id']}/follow-ups",
        csrf,
        {
            "due_at": due,
            "kind": "CALL",
            "assignee_membership_id": str(h.world.memberships["carol_b"]),
        },
    )
    assert _codes(follow_up) == {("assignee_membership_id", "owner_not_eligible")}


async def test_other_tenant_follow_ups_are_not_found(h: Harness, b: Other) -> None:
    csrf = await _alice(h)
    path = f"{FOLLOW_UPS}/{b.follow_up['id']}"
    for method, suffix, body in (
        ("PATCH", "", {"note": "Hijacked", "version": 1}),
        ("POST", "/complete", {"outcome": "x", "version": 1}),
        ("POST", "/cancel", {"version": 1}),
    ):
        response = await send(h, method, f"{path}{suffix}", csrf, body)
        assert response.status_code == 404, (method, suffix)
    await _unchanged(h, "lead_follow_ups", b.follow_up)


# --- Platform realm ------------------------------------------------------------------------


async def test_platform_sessions_cannot_reach_course_and_lead_routes(
    migrated_database: DatabaseUnderTest, redis_url: str
) -> None:
    async with platform_harness(migrated_database, redis_url) as p:
        csrf = await p.admin("nora")
        for path in (COURSES, LEADS, f"{LEADS}/assignees"):
            assert (await p.client.get(path)).status_code == 401, path
        created = await p.send("POST", LEADS, csrf, {"full_name": "X", "source": "PHONE"})
        assert created.status_code in {401, 403}
