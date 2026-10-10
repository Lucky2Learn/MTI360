"""Course catalogue over HTTP (Phase 02-1; blueprint §4-§6, §17, ADR-0020 §1-§2).

* create (DRAFT), edit, activate, archive, reactivate; no delete route;
* the code is validated, upper-cased, unique per tenant and immutable;
* course.read is campus-scoped and courses have no campus: campus-restricted
  staff read the institute catalogue; course.manage is tenant-wide:
  restricted managers and counsellors cannot change it;
* optimistic locking and the three ``domain`` audit events.
"""

import uuid
from collections.abc import AsyncIterator

import anyio
import pytest
from conftest import DatabaseUnderTest
from courses_leads_support import COURSES, admissions_team, new_course
from identity_support import Harness, auth_harness
from tenant_admin_support import data, send, sign_in

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        await admissions_team(harness)
        yield harness


def _code() -> str:
    return f"C{uuid.uuid7().hex[-7:]}".upper()


async def test_a_manager_creates_edits_and_moves_a_course_through_its_lifecycle(h: Harness) -> None:
    csrf = await sign_in(h, "maya")
    code = _code()
    created = await send(
        h,
        "POST",
        COURSES,
        csrf,
        {
            "code": f" {code.lower()} ",
            "name": "  GP   Rating ",
            "category": "PRE_SEA",
            "duration_value": 6,
            "duration_unit": "MONTHS",
            "eligibility_summary": "10th pass with 40% in Science, Maths and English.",
        },
    )
    course = data(created, 201)
    assert (course["code"], course["name"], course["status"]) == (code, "GP Rating", "DRAFT")
    assert course["version"] == 1
    assert [row.event_type for row in await h.audit(created)] == ["course.created"]
    assert (await h.audit(created))[0].metadata == {"code": code}

    edited = await send(
        h,
        "PATCH",
        f"{COURSES}/{course['id']}",
        csrf,
        {"name": "General Purpose Rating", "description": "Pre-sea course.", "version": 1},
    )
    course = data(edited)
    assert course["name"] == "General Purpose Rating"
    assert course["version"] == 2
    (event,) = await h.audit(edited)
    assert event.event_type == "course.updated"
    assert event.metadata == {"changed_fields": ["description", "name"]}

    for target, expected in (("ACTIVE", "ACTIVE"), ("ARCHIVED", "ARCHIVED"), ("ACTIVE", "ACTIVE")):
        moved = await send(
            h,
            "POST",
            f"{COURSES}/{course['id']}/status",
            csrf,
            {"status": target, "version": course["version"]},
        )
        previous, course = course["status"], data(moved)
        assert course["status"] == expected
        (event,) = await h.audit(moved)
        assert (event.event_type, event.metadata) == (
            "course.status_changed",
            {"from": previous, "to": expected},
        )
    # ACTIVE → ACTIVE and back to DRAFT are not transitions.
    for target in ("ACTIVE", "DRAFT"):
        refused = await send(
            h,
            "POST",
            f"{COURSES}/{course['id']}/status",
            csrf,
            {"status": target, "version": course["version"]},
        )
        assert refused.status_code == 422


async def test_a_draft_can_be_archived_and_there_is_no_delete(h: Harness) -> None:
    csrf = await sign_in(h, "maya")
    course = await new_course(h, csrf, _code(), activate=False)
    archived = data(
        await send(
            h,
            "POST",
            f"{COURSES}/{course['id']}/status",
            csrf,
            {"status": "ARCHIVED", "version": 1},
        )
    )
    assert archived["status"] == "ARCHIVED"
    assert (await send(h, "DELETE", f"{COURSES}/{course['id']}", csrf)).status_code == 405


async def test_the_code_is_validated_unique_and_immutable(h: Harness) -> None:
    csrf = await sign_in(h, "maya")
    code = _code()
    course = await new_course(h, csrf, code)
    taken = await send(
        h, "POST", COURSES, csrf, {"code": code.lower(), "name": "Again", "category": "OTHER"}
    )
    assert taken.status_code == 409
    for bad in ("-GPR", "G P R", "GPR_1", "A" * 33):
        response = await send(
            h, "POST", COURSES, csrf, {"code": bad, "name": "Bad", "category": "OTHER"}
        )
        assert response.status_code == 422, bad
        assert response.json()["error"]["details"][0]["field"] == "code"
    changed = await send(
        h, "PATCH", f"{COURSES}/{course['id']}", csrf, {"code": "NEW", "version": course["version"]}
    )
    assert changed.status_code == 422  # unknown field: the code cannot be sent
    status_in_patch = await send(
        h, "PATCH", f"{COURSES}/{course['id']}", csrf, {"status": "ARCHIVED", "version": 2}
    )
    assert status_in_patch.status_code == 422


async def test_concurrent_creates_with_one_code_yield_one_course(h: Harness) -> None:
    csrf = await sign_in(h, "maya")
    code = _code()
    results: list[int] = []

    async def create() -> None:
        response = await send(
            h, "POST", COURSES, csrf, {"code": code, "name": "Race", "category": "OTHER"}
        )
        results.append(response.status_code)

    async with anyio.create_task_group() as group:
        group.start_soon(create)
        group.start_soon(create)
    assert sorted(results) == [201, 409]


async def test_validation_and_optimistic_locking(h: Harness) -> None:
    csrf = await sign_in(h, "maya")
    course = await new_course(h, csrf, _code())
    for body in (
        {"duration_value": 6, "version": course["version"]},  # unit missing
        {"duration_unit": "DAYS", "version": course["version"]},
        {"name": "   ", "version": course["version"]},
        {"category": "SHIP", "version": course["version"]},
        {"tenant_id": str(h.world.tenant_b), "version": course["version"]},
    ):
        response = await send(h, "PATCH", f"{COURSES}/{course['id']}", csrf, body)
        assert response.status_code == 422, body
    stale = await send(
        h, "PATCH", f"{COURSES}/{course['id']}", csrf, {"name": "Stale", "version": 1}
    )
    assert stale.status_code == 409
    stale_status = await send(
        h, "POST", f"{COURSES}/{course['id']}/status", csrf, {"status": "ARCHIVED", "version": 1}
    )
    assert stale_status.status_code == 409
    # An unchanged edit is a no-op: same version, no audit event.
    same = await send(
        h, "PATCH", f"{COURSES}/{course['id']}", csrf, {"name": course["name"], "version": 2}
    )
    assert data(same)["version"] == 2
    assert await h.audit(same) == []


async def test_campus_restricted_staff_read_the_institute_catalogue(h: Harness) -> None:
    manager = await sign_in(h, "maya")
    course = await new_course(h, manager, _code())
    for user in ("ravi", "sita", "kiran"):  # SELECTED-scope counsellors and manager
        await sign_in(h, user)
        listed = (await h.client.get(COURSES, params={"q": course["code"]})).json()
        assert [item["id"] for item in listed["data"]] == [course["id"]], user
        assert data(await h.client.get(f"{COURSES}/{course['id']}"))["code"] == course["code"]


async def test_only_tenant_wide_managers_change_the_catalogue(h: Harness) -> None:
    manager = await sign_in(h, "maya")
    course = await new_course(h, manager, _code())
    for user in ("ravi", "kiran"):  # a counsellor; a manager restricted to one campus
        csrf = await sign_in(h, user)
        attempts = (
            ("POST", COURSES, {"code": _code(), "name": "X", "category": "OTHER"}),
            ("PATCH", f"{COURSES}/{course['id']}", {"name": "X", "version": course["version"]}),
            (
                "POST",
                f"{COURSES}/{course['id']}/status",
                {"status": "ARCHIVED", "version": course["version"]},
            ),
        )
        for method, path, body in attempts:
            response = await send(h, method, path, csrf, body)
            assert response.status_code == 403, (user, method, path)


async def test_lists_filter_sort_and_paginate(h: Harness) -> None:
    csrf = await sign_in(h, "maya")
    tag = uuid.uuid7().hex[-5:].upper()
    active = await new_course(h, csrf, f"A{tag}", name=f"Alpha {tag}", category="POST_SEA")
    draft = await new_course(h, csrf, f"B{tag}", activate=False, name=f"Bravo {tag}")
    listed = (await h.client.get(COURSES, params={"q": tag, "sort": "-code"})).json()
    assert [c["id"] for c in listed["data"]] == [draft["id"], active["id"]]
    assert listed["meta"]["page"]["total"] == 2
    only_active = (await h.client.get(COURSES, params={"q": tag, "status": "ACTIVE"})).json()
    assert [c["id"] for c in only_active["data"]] == [active["id"]]
    post_sea = (await h.client.get(COURSES, params={"q": tag, "category": "POST_SEA"})).json()
    assert [c["id"] for c in post_sea["data"]] == [active["id"]]
    page = (await h.client.get(COURSES, params={"q": tag, "limit": 1, "offset": 1})).json()
    assert len(page["data"]) == 1
    assert page["meta"]["page"] == {"limit": 1, "offset": 1, "total": 2}
    # Search terms are literal (LIKE wildcards are escaped).
    assert (await h.client.get(COURSES, params={"q": "%"})).json()["data"] == []
    for bad in ({"status": "LIVE"}, {"sort": "status"}, {"category": "SHIP"}):
        assert (await h.client.get(COURSES, params=bad)).status_code == 422, bad
