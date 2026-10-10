"""Cross-tenant isolation of every Finance-lite route (Phase 02-5; ADR-0022, tenancy.md §8).

Institute B (Carol, its owner) owns a course with an active and a draft fee
structure. Alice, the owner of institute A with every permission, calls every
route with B's identifiers: reads and changes are **not found** (404, the
same answer as for a missing row), lists contain none of B's rows, B's
references are refused in A's writes with the answer given for an unknown
row, and B's rows are unchanged afterwards. Each test is named in
``tests/cross_tenant_registry.py``; the meta-test keeps the two in step.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import pytest
from admissions_support import active_course
from conftest import DatabaseUnderTest
from finance_support import FEE_STRUCTURES, ITEMS, errors, new_structure
from identity_support import Harness, auth_harness
from tenant_admin_support import data, send, sign_in

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@dataclass
class Other:
    """Institute B's rows, seen from institute A."""

    course: dict[str, Any]
    structure: dict[str, Any]
    draft: dict[str, Any]


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        yield harness


@pytest.fixture
async def b(h: Harness) -> Other:
    csrf = await sign_in(h, "carol")
    course = await active_course(h, csrf, "B")
    structure = await new_structure(h, csrf, course["id"], name="B fees")
    draft = await new_structure(h, csrf, course["id"], activate=False, name="B draft fees")
    return Other(course, structure, draft)


async def _alice(h: Harness) -> str:
    return await sign_in(h, "alice")


async def _unchanged(h: Harness, table: str, row: dict[str, Any]) -> None:
    rows = await h.owner(f"SELECT version FROM {table} WHERE id = :id", id=row["id"])  # noqa: S608
    assert rows[0][0] == row["version"], table


def _ids(response: Any) -> set[str]:
    return {item["id"] for item in data(response)}


async def test_fee_structure_list_holds_no_other_tenant_structure(h: Harness, b: Other) -> None:
    await _alice(h)
    assert not _ids(await h.client.get(FEE_STRUCTURES)) & {b.structure["id"], b.draft["id"]}
    for params in ({"course_id": b.course["id"]}, {"q": "B fees"}, {"q": b.course["code"]}):
        assert _ids(await h.client.get(FEE_STRUCTURES, params=params)) == set(), params


async def test_fee_structure_create_refuses_other_tenant_courses(h: Harness, b: Other) -> None:
    csrf = await _alice(h)
    answers = []
    for course_id in (b.course["id"], str(uuid.uuid7())):
        response = await send(
            h, "POST", FEE_STRUCTURES, csrf, {"course_id": course_id, "name": "X", "items": ITEMS}
        )
        assert response.status_code == 422
        answers.append(errors(response))
    # Another tenant's course gets exactly the answer of a course that does not exist.
    assert answers[0] == answers[1] == {("course_id", "course_not_available")}
    rows = await h.owner(
        "SELECT count(*) FROM fee_structures WHERE tenant_id = :t", t=h.world.tenant_a
    )
    assert rows[0][0] == 0


async def test_other_tenant_fee_structure_reads_are_not_found(h: Harness, b: Other) -> None:
    await _alice(h)
    for structure in (b.structure, b.draft):
        response = await h.client.get(f"{FEE_STRUCTURES}/{structure['id']}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_other_tenant_fee_structure_changes_are_not_found(h: Harness, b: Other) -> None:
    csrf = await _alice(h)
    for structure, method, suffix, body in (
        (b.draft, "PATCH", "", {"name": "Taken over", "version": b.draft["version"]}),
        (b.draft, "POST", "/status", {"status": "ACTIVE", "version": b.draft["version"]}),
        (b.structure, "POST", "/status", {"status": "ARCHIVED", "version": b.structure["version"]}),
    ):
        response = await send(h, method, f"{FEE_STRUCTURES}/{structure['id']}{suffix}", csrf, body)
        assert response.status_code == 404, (method, suffix)
    await _unchanged(h, "fee_structures", b.draft)
    await _unchanged(h, "fee_structures", b.structure)
