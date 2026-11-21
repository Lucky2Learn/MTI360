"""Cross-tenant isolation of every batch route (Phase 02-6; tenancy.md §8).

Institute B (Carol, its owner) has an admitted student allocated to an open
batch, and a second open batch. Alice, the owner of institute A with every
permission, calls every route with B's identifiers: reads and changes are
**not found** (404), lists contain none of B's rows, B's references in A's
writes get the answer given for an unknown row, and B's rows are unchanged.
Each test is named in ``tests/cross_tenant_registry.py``.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import pytest
from batches_support import ALLOCATIONS, BATCHES, allocate, new_batch, start
from conftest import DatabaseUnderTest
from courses_leads_support import new_course
from finance_support import Billable, billable
from identity_support import Harness, auth_harness
from tenant_admin_support import data, send, sign_in

pytestmark = [pytest.mark.anyio, pytest.mark.integration]
UNKNOWN = "01a00000-0000-7000-8000-000000000000"


@dataclass
class Other:
    billable: Billable
    batch: dict[str, Any]
    spare: dict[str, Any]
    allocation: dict[str, Any]


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        yield harness


@pytest.fixture
async def b(h: Harness) -> Other:
    other = await billable(h, h.world.campus_b1, prefix="B", admissions="carol", finance="carol")
    csrf = await sign_in(h, "carol")
    batch = await new_batch(h, csrf, other.course["id"], h.world.campus_b1, code="B-DNS-1")
    spare = await new_batch(h, csrf, other.course["id"], h.world.campus_b1, code="B-DNS-2")
    allocation = data(
        await allocate(h, csrf, batch["id"], other.admission_id, "Fees by sponsor"), 201
    )
    batch = data(await h.client.get(f"{BATCHES}/{batch['id']}"))
    return Other(other, batch, spare, allocation)


async def _alice(h: Harness) -> str:
    return await sign_in(h, "alice")


async def _unchanged(h: Harness, b: Other) -> None:
    rows = await h.owner(
        "SELECT id::text, version, allocated_count FROM batches WHERE id IN (:a, :s)",
        a=b.batch["id"],
        s=b.spare["id"],
    )
    found = {row[0]: (row[1], row[2]) for row in rows}
    assert found[b.batch["id"]] == (b.batch["version"], 1)
    assert found[b.spare["id"]] == (b.spare["version"], 0)
    allocation = await h.owner(
        "SELECT status, version FROM batch_allocations WHERE id = :id", id=b.allocation["id"]
    )
    assert tuple(allocation[0]) == ("ACTIVE", b.allocation["version"])
    admission = await h.owner(
        "SELECT status FROM admissions WHERE id = :id", id=b.billable.admission_id
    )
    assert admission[0][0] == "ENROLLED"


def _ids(response: Any) -> set[str]:
    return {item["id"] for item in data(response)}


async def test_batch_list_holds_no_other_tenant_batch(h: Harness, b: Other) -> None:
    await _alice(h)
    assert not _ids(await h.client.get(BATCHES)) & {b.batch["id"], b.spare["id"]}
    for params in (
        {"course_id": b.billable.course["id"]},
        {"campus_id": str(h.world.campus_b1)},
        {"q": "B-DNS"},
    ):
        assert _ids(await h.client.get(BATCHES, params=params)) == set(), params


async def test_batch_create_refuses_other_tenant_references(h: Harness, b: Other) -> None:
    csrf = await _alice(h)
    course = await new_course(h, csrf, "ADNS")
    base = {
        "code": "A-BATCH",
        "name": "Batch",
        "start_date": start(10),
        "end_date": start(20),
        "capacity": 10,
    }
    answers = []
    for course_id in (b.billable.course["id"], str(uuid.uuid7())):
        response = await send(
            h,
            "POST",
            BATCHES,
            csrf,
            {**base, "course_id": course_id, "campus_id": str(h.world.campus_a1)},
        )
        assert response.status_code == 422
        answers.append(response.json()["error"]["details"])
    assert answers[0] == answers[1]
    response = await send(
        h,
        "POST",
        BATCHES,
        csrf,
        {**base, "course_id": course["id"], "campus_id": str(h.world.campus_b1)},
    )
    assert {d["code"] for d in response.json()["error"]["details"]} == {"campus_not_available"}
    # A tenant ID in the body is not a field: refused, never used.
    response = await send(
        h,
        "POST",
        BATCHES,
        csrf,
        {
            **base,
            "course_id": course["id"],
            "campus_id": str(h.world.campus_a1),
            "tenant_id": str(h.world.tenant_b),
        },
    )
    assert response.status_code == 422
    rows = await h.owner("SELECT count(*) FROM batches WHERE tenant_id = :t", t=h.world.tenant_a)
    assert rows[0][0] == 0


async def test_other_tenant_batch_reads_are_not_found(h: Harness, b: Other) -> None:
    await _alice(h)
    for suffix in ("", "/allocations", "/eligible-admissions", "/activity"):
        response = await h.client.get(f"{BATCHES}/{b.batch['id']}{suffix}")
        assert response.status_code == 404, suffix
        assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_other_tenant_batch_changes_are_not_found(h: Harness, b: Other) -> None:
    csrf = await _alice(h)
    for method, suffix, body in (
        ("PATCH", "", {"name": "Taken over", "version": b.spare["version"]}),
        ("POST", "/status", {"status": "CLOSED", "version": b.spare["version"]}),
        ("POST", "/status", {"status": "CANCELLED", "version": b.spare["version"]}),
    ):
        response = await send(h, method, f"{BATCHES}/{b.spare['id']}{suffix}", csrf, body)
        assert response.status_code == 404, (method, suffix)
    await _unchanged(h, b)


async def test_allocation_refuses_other_tenant_references(h: Harness, b: Other) -> None:
    csrf = await _alice(h)
    # B's batch: not found.
    response = await allocate(h, csrf, b.spare["id"], b.billable.admission_id, "x")
    assert response.status_code == 404
    # A's batch with B's admission: the answer for an unknown admission.
    mine = await billable(h, h.world.campus_a1, prefix="A", admissions="alice", finance="alice")
    csrf = await _alice(h)
    target = await new_batch(h, csrf, mine.course["id"], h.world.campus_a1)
    answers = []
    for admission_id in (b.billable.admission_id, UNKNOWN):
        response = await allocate(h, csrf, target["id"], admission_id, "Sponsor letter")
        assert response.status_code == 422
        answers.append(response.json()["error"]["details"])
    assert answers[0] == answers[1]
    assert {d["code"] for d in answers[0]} == {"admission_not_available"}
    await _unchanged(h, b)


async def test_allocation_list_holds_no_other_tenant_allocation(h: Harness, b: Other) -> None:
    await _alice(h)
    assert data(await h.client.get(ALLOCATIONS)) == []
    params = {"student_id": b.billable.student_id}
    assert data(await h.client.get(ALLOCATIONS, params=params)) == []
    student = await h.client.get(f"/api/v1/students/{b.billable.student_id}/activity")
    assert student.status_code == 404


async def test_other_tenant_allocation_changes_are_not_found(h: Harness, b: Other) -> None:
    csrf = await _alice(h)
    path = f"{ALLOCATIONS}/{b.allocation['id']}"
    for suffix, body in (
        ("/transfer", {"target_batch_id": b.spare["id"], "reason": "Mine", "version": 1}),
        ("/withdraw", {"reason": "Mine", "version": 1}),
    ):
        response = await send(h, "POST", f"{path}{suffix}", csrf, body)
        assert response.status_code == 404, suffix
    await _unchanged(h, b)
