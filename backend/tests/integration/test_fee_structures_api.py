"""Fee structures over HTTP (Phase 02-5; ADR-0022, readiness plan §5-§7).

* create (DRAFT) with cleaned fee heads and a computed total, edit while
  DRAFT only, activate (archiving the course's previous active structure),
  archive; no delete route;
* validation: fee heads, duplicates, line count, amounts, the course;
* fee_structure.read is campus-scoped and structures have no campus:
  campus-restricted staff read them; fee_structure.manage is tenant-wide;
* optimistic locking, a concurrent second activation, and the audit events.
"""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import anyio
import pytest
from conftest import DatabaseUnderTest
from courses_leads_support import COURSES, admissions_team
from finance_support import (
    FEE_STRUCTURES,
    ITEMS,
    ITEMS_TOTAL,
    errors,
    finance_course,
    finance_team,
    new_structure,
)
from identity_support import Harness, auth_harness
from tenant_admin_support import data, send, sign_in

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        await admissions_team(harness)
        await finance_team(harness)
        yield harness


async def _status(h: Harness, csrf: str, structure: dict[str, Any], target: str) -> Any:
    return await send(
        h,
        "POST",
        f"{FEE_STRUCTURES}/{structure['id']}/status",
        csrf,
        {"status": target, "version": structure["version"]},
    )


async def test_a_manager_creates_edits_and_activates_a_fee_structure(h: Harness) -> None:
    course = await finance_course(h, "DNS")
    csrf = await sign_in(h, "fiona")
    created = await send(
        h,
        "POST",
        FEE_STRUCTURES,
        csrf,
        {
            "course_id": course["id"],
            "name": "  DNS   2026-27 ",
            "items": [{"fee_head": "  Tuition   fee ", "amount_minor": 25_000_000}],
        },
    )
    structure = data(created, 201)
    assert (structure["name"], structure["status"], structure["currency"]) == (
        "DNS 2026-27",
        "DRAFT",
        "INR",
    )
    assert structure["items"] == [{"fee_head": "Tuition fee", "amount_minor": 25_000_000}]
    assert structure["total_minor"] == 25_000_000
    assert structure["course"] == {
        "id": course["id"],
        "code": course["code"],
        "name": course["name"],
    }
    (event,) = await h.audit(created)
    assert (event.event_type, event.metadata) == (
        "fee_structure.created",
        {"line_count": 1, "total_minor": 25_000_000, "currency": "INR"},
    )

    edited = await send(
        h,
        "PATCH",
        f"{FEE_STRUCTURES}/{structure['id']}",
        csrf,
        {"items": ITEMS, "version": structure["version"]},
    )
    structure = data(edited)
    assert (structure["total_minor"], structure["version"]) == (ITEMS_TOTAL, 2)
    (event,) = await h.audit(edited)
    assert event.metadata == {"changed_fields": ["items"]}

    activated = await _status(h, csrf, structure, "ACTIVE")
    structure = data(activated)
    assert structure["status"] == "ACTIVE"
    assert structure["activated_at"] is not None
    (event,) = await h.audit(activated)
    assert (event.event_type, event.metadata) == (
        "fee_structure.activated",
        {"from": "DRAFT", "archived_previous": False},
    )
    # An active structure is frozen: edit refused, a new version is a new draft.
    frozen = await send(
        h,
        "PATCH",
        f"{FEE_STRUCTURES}/{structure['id']}",
        csrf,
        {"name": "Changed", "version": structure["version"]},
    )
    assert frozen.status_code == 422
    assert errors(frozen) == {("status", "not_editable")}

    successor = await new_structure(h, csrf, course["id"], activate=False, name="DNS 2027-28")
    replaced = await _status(h, csrf, successor, "ACTIVE")
    assert data(replaced)["status"] == "ACTIVE"
    events = {(e.event_type, tuple(sorted(e.metadata.items()))) for e in await h.audit(replaced)}
    assert events == {
        ("fee_structure.archived", (("from", "ACTIVE"), ("replaced_by_activation", True))),
        ("fee_structure.activated", (("archived_previous", True), ("from", "DRAFT"))),
    }
    previous = data(await h.client.get(f"{FEE_STRUCTURES}/{structure['id']}"))
    assert previous["status"] == "ARCHIVED"
    assert previous["archived_at"] is not None
    # Archived is final; there is no delete route.
    assert (await _status(h, csrf, previous, "ACTIVE")).status_code == 422
    deleted = await send(h, "DELETE", f"{FEE_STRUCTURES}/{structure['id']}", csrf)
    assert deleted.status_code == 405


async def test_fee_structures_are_validated(h: Harness) -> None:
    course = await finance_course(h, "GPR")
    archived_course = await finance_course(h, "OLD")
    archived = await send(
        h,
        "POST",
        f"{COURSES}/{archived_course['id']}/status",
        await sign_in(h, "maya"),
        {"status": "ARCHIVED", "version": archived_course["version"]},
    )
    data(archived)
    csrf = await sign_in(h, "fiona")
    base = {"course_id": course["id"], "name": "GP Rating 2026"}
    for body, expected in (
        ({**base, "items": []}, {("items", "line_count"), ("items", "total_out_of_range")}),
        (
            {**base, "items": [{"fee_head": f"Head {n}", "amount_minor": 100} for n in range(31)]},
            {("items", "line_count")},
        ),
        (
            {**base, "items": [ITEMS[0], {"fee_head": "TUITION", "amount_minor": 1}]},
            {("items", "duplicate_fee_head")},
        ),
        (
            {**base, "items": [{"fee_head": "Tuition", "amount_minor": 0}]},
            {("items", "total_out_of_range")},
        ),
        (
            {**base, "items": [{"fee_head": "   ", "amount_minor": 1}]},
            {("items.0.fee_head", "string_too_short")},
        ),
        ({**base, "name": "   ", "items": ITEMS}, {("name", "string_too_short")}),
        (
            {**base, "course_id": archived_course["id"], "items": ITEMS},
            {("course_id", "course_not_available")},
        ),
        (
            {**base, "course_id": str(uuid.uuid7()), "items": ITEMS},
            {("course_id", "course_not_available")},
        ),
    ):
        response = await send(h, "POST", FEE_STRUCTURES, csrf, body)
        assert response.status_code == 422, body
        assert errors(response) == expected, body
    for body in (
        {**base, "items": [{"fee_head": "Tuition", "amount_minor": -1}]},
        {**base, "items": [{"fee_head": "Tuition", "amount_minor": 1.5}]},
        {**base, "items": [{"fee_head": "Tuition", "amount_minor": "100"}]},
        {**base, "items": [{"fee_head": "Tuition", "amount_minor": 100.0}]},
        {**base, "items": ITEMS, "total_minor": 1},
        {**base, "items": ITEMS, "currency": "USD"},
        {**base, "items": ITEMS, "tenant_id": str(h.world.tenant_b)},
    ):
        response = await send(h, "POST", FEE_STRUCTURES, csrf, body)
        assert response.status_code == 422, body


async def test_optimistic_locking_and_unchanged_edits(h: Harness) -> None:
    course = await finance_course(h, "ETO")
    csrf = await sign_in(h, "fiona")
    structure = await new_structure(h, csrf, course["id"], activate=False)
    path = f"{FEE_STRUCTURES}/{structure['id']}"
    assert (await send(h, "PATCH", path, csrf, {"name": "Stale", "version": 9})).status_code == 409
    stale = await send(h, "POST", f"{path}/status", csrf, {"status": "ACTIVE", "version": 9})
    assert stale.status_code == 409
    same = await send(h, "PATCH", path, csrf, {"items": ITEMS, "version": 1})
    assert data(same)["version"] == 1
    assert await h.audit(same) == []


async def test_concurrent_activations_of_one_course_yield_one_active_structure(h: Harness) -> None:
    course = await finance_course(h, "MEO")
    csrf = await sign_in(h, "fiona")
    first = await new_structure(h, csrf, course["id"], activate=False, name="A")
    second = await new_structure(h, csrf, course["id"], activate=False, name="B")
    results: list[int] = []

    async def activate(structure: dict[str, Any]) -> None:
        results.append((await _status(h, csrf, structure, "ACTIVE")).status_code)

    async with anyio.create_task_group() as group:
        group.start_soon(activate, first)
        group.start_soon(activate, second)
    listed = data(
        await h.client.get(FEE_STRUCTURES, params={"course_id": course["id"], "status": "ACTIVE"})
    )
    assert len(listed) == 1
    # Either both succeed in turn (the second archives the first) or one sees the race: 409.
    assert sorted(results) in ([200, 200], [200, 409])


async def test_campus_restricted_staff_read_fee_structures(h: Harness) -> None:
    course = await finance_course(h, "BST")
    manager = await sign_in(h, "fiona")
    structure = await new_structure(h, manager, course["id"])
    for user in ("farah", "feroz", "fatima", "ravi", "kiran"):  # officers, managers, counsellor
        await sign_in(h, user)
        listed = data(await h.client.get(FEE_STRUCTURES, params={"course_id": course["id"]}))
        assert [item["id"] for item in listed] == [structure["id"]], user
        assert (
            data(await h.client.get(f"{FEE_STRUCTURES}/{structure['id']}"))["id"] == structure["id"]
        )


async def test_only_tenant_wide_finance_managers_change_fee_structures(h: Harness) -> None:
    course = await finance_course(h, "PSC")
    manager = await sign_in(h, "fiona")
    structure = await new_structure(h, manager, course["id"], activate=False)
    for user in ("farah", "fatima", "maya", "ravi"):
        csrf = await sign_in(h, user)
        for method, path, body in (
            ("POST", FEE_STRUCTURES, {"course_id": course["id"], "name": "X", "items": ITEMS}),
            ("PATCH", f"{FEE_STRUCTURES}/{structure['id']}", {"name": "X", "version": 1}),
            (
                "POST",
                f"{FEE_STRUCTURES}/{structure['id']}/status",
                {"status": "ACTIVE", "version": 1},
            ),
        ):
            response = await send(h, method, path, csrf, body)
            assert response.status_code == 403, (user, method, path)
    assert data(await h.client.get(f"{FEE_STRUCTURES}/{structure['id']}"))["version"] == 1


async def test_lists_filter_search_and_sort(h: Harness) -> None:
    dns = await finance_course(h, "DNS")
    gpr = await finance_course(h, "GPR")
    csrf = await sign_in(h, "fiona")
    a = await new_structure(h, csrf, dns["id"], name="Alpha fees")
    b = await new_structure(h, csrf, gpr["id"], activate=False, name="Beta fees")
    by_course = data(await h.client.get(FEE_STRUCTURES, params={"course_id": gpr["id"]}))
    assert [item["id"] for item in by_course] == [b["id"]]
    drafts = data(await h.client.get(FEE_STRUCTURES, params={"status": "DRAFT", "q": "beta"}))
    assert [item["id"] for item in drafts] == [b["id"]]
    by_course_code = data(await h.client.get(FEE_STRUCTURES, params={"q": dns["code"]}))
    assert [item["id"] for item in by_course_code] == [a["id"]]
    descending = data(
        await h.client.get(FEE_STRUCTURES, params={"sort": "-name", "q": "fees", "limit": 2})
    )
    assert [item["name"] for item in descending][:2] == ["Beta fees", "Alpha fees"]
    assert (await h.client.get(FEE_STRUCTURES, params={"sort": "total_minor"})).status_code == 422
