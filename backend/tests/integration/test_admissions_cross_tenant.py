"""Cross-tenant isolation of every application, document and student route (Phase 02-2).

Institute B (Carol, its owner) owns a lead, an admitted application with a
verified document, an open application with a document under review, and a
student. Alice, the owner of institute A with every permission, calls every
route with B's identifiers: reads and changes are **not found** (404, the
same answer as for a missing row), lists contain none of B's rows, B's
references are refused in A's writes, B's student is never offered or linked,
and B's rows and stored bytes are unchanged afterwards. Each test is named in
``tests/cross_tenant_registry.py``; the meta-test keeps the two in step.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import pytest
from admissions_support import (
    APPLICATIONS,
    DOCUMENTS,
    STUDENTS,
    active_course,
    admit,
    approved,
    decide,
    new_application,
    ready,
    reload,
    review,
    submit,
    upload,
    use_memory_storage,
)
from conftest import DatabaseUnderTest
from courses_leads_support import new_lead
from identity_support import Harness, auth_harness
from tenant_admin_support import data, send, sign_in

from app.integrations.storage import InMemoryObjectStorage

pytestmark = [pytest.mark.anyio, pytest.mark.integration]
MOBILE = "+91 90000 10999"


@dataclass
class Other:
    """Institute B's rows, seen from institute A."""

    course: dict[str, Any]
    lead: dict[str, Any]
    admitted: dict[str, Any]
    open_application: dict[str, Any]
    document: dict[str, Any]
    student_id: str


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        use_memory_storage(harness)
        yield harness


@pytest.fixture
async def b(h: Harness) -> Other:
    w = h.world
    csrf = await sign_in(h, "carol")
    course = await active_course(h, csrf, "B")
    lead = await new_lead(h, csrf, campus_id=str(w.campus_b1), mobile=MOBILE)
    admitted = await approved(
        h, csrf, course=course, campus=w.campus_b1, full_name="Tenant B Student", mobile=MOBILE
    )
    admitted = data(await admit(h, csrf, admitted))
    open_application = await ready(
        h, csrf, await new_application(h, csrf, course=course, campus=w.campus_b1, lead=lead)
    )
    data(await upload(h, csrf, open_application["id"]), 201)
    open_application = data(await submit(h, csrf, await reload(h, open_application)))
    document = data(await h.client.get(f"{APPLICATIONS}/{open_application['id']}/documents"))[
        "items"
    ][0]
    lead = data(await h.client.get(f"/api/v1/leads/{lead['id']}"))  # now in APPLICATION
    return Other(
        course, lead, admitted, open_application, document, admitted["admission"]["student_id"]
    )


async def _alice(h: Harness) -> str:
    return await sign_in(h, "alice")


async def _unchanged(h: Harness, table: str, row: dict[str, Any]) -> None:
    rows = await h.owner(f"SELECT version FROM {table} WHERE id = :id", id=row["id"])  # noqa: S608
    assert rows[0][0] == row["version"], table


def _ids(response: Any) -> set[str]:
    return {item["id"] for item in data(response)}


async def test_application_list_holds_no_other_tenant_application(h: Harness, b: Other) -> None:
    await _alice(h)
    listed = _ids(await h.client.get(APPLICATIONS, params={"limit": 100}))
    assert not {b.admitted["id"], b.open_application["id"]} & listed
    for params in (
        {"lead": b.lead["id"]},
        {"course": b.course["id"]},
        {"campus": str(h.world.campus_b1)},
        {"q": b.open_application["number"]},
        {"q": "Tenant B"},
    ):
        assert _ids(await h.client.get(APPLICATIONS, params=params)) == set(), params


async def test_application_create_rejects_other_tenant_references(h: Harness, b: Other) -> None:
    w = h.world
    csrf = await _alice(h)
    course = await active_course(h, csrf, "A")
    base = {"course_id": course["id"], "campus_id": str(w.campus_a1), "full_name": "Meera Pillai"}
    for field, foreign, code in (
        ("course_id", b.course["id"], "course_not_active"),
        ("campus_id", str(w.campus_b1), "campus_not_available"),
        ("lead_id", b.lead["id"], "lead_not_available"),
    ):
        response = await send(h, "POST", APPLICATIONS, csrf, {**base, field: foreign})
        assert response.status_code == 422, field
        assert {(d["field"], d["code"]) for d in response.json()["error"]["details"]} == {
            (field, code)
        }
    with_tenant = await send(h, "POST", APPLICATIONS, csrf, {**base, "tenant_id": str(w.tenant_b)})
    assert with_tenant.status_code == 422
    created = data(await send(h, "POST", APPLICATIONS, csrf, base), 201)
    rows = await h.owner(
        "SELECT tenant_id FROM applications WHERE id = :id", id=uuid.UUID(created["id"])
    )
    assert rows[0][0] == w.tenant_a
    await _unchanged(h, "leads", b.lead)


async def test_other_tenant_application_reads_are_not_found(h: Harness, b: Other) -> None:
    await _alice(h)
    for application in (b.admitted, b.open_application):
        for suffix in ("", "/activity", "/documents", "/student-candidates"):
            response = await h.client.get(f"{APPLICATIONS}/{application['id']}{suffix}")
            assert response.status_code == 404, suffix
            assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_other_tenant_application_changes_are_not_found(h: Harness, b: Other) -> None:
    csrf = await _alice(h)
    target = b.open_application
    path = f"{APPLICATIONS}/{target['id']}"
    version = {"version": target["version"]}
    for method, suffix, body in (
        ("PATCH", "", {"city": "Elsewhere", **version}),
        ("POST", "/submit", version),
        ("POST", "/review", {"to_status": "REJECTED", "reason": "x", **version}),
    ):
        response = await send(h, method, f"{path}{suffix}", csrf, body)
        assert response.status_code == 404, suffix
    assert (await upload(h, csrf, target["id"])).status_code == 404
    storage: InMemoryObjectStorage = h.app.state.storage
    assert all(f"/{h.world.tenant_a}/" not in key for key in storage.objects)
    await _unchanged(h, "applications", target)


async def test_admission_never_links_another_tenants_student(h: Harness, b: Other) -> None:
    w = h.world
    csrf = await _alice(h)
    assert (await admit(h, csrf, b.open_application)).status_code == 404
    course = await active_course(h, csrf, "A")
    mine = await approved(h, csrf, course=course, campus=w.campus_a1, mobile=MOBILE)
    offered = data(await h.client.get(f"{APPLICATIONS}/{mine['id']}/student-candidates"))
    assert offered["candidates"] == []  # same mobile, other tenant: never a match
    response = await admit(h, csrf, mine, "existing", b.student_id)
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["code"] == "student_not_available"
    created = data(await admit(h, csrf, await reload(h, mine)))
    assert created["admission"]["student_id"] != b.student_id
    rows = await h.owner(
        "SELECT count(*) FROM admissions WHERE student_id = :s", s=uuid.UUID(b.student_id)
    )
    assert rows[0][0] == 1


async def test_document_queue_holds_no_other_tenant_document(h: Harness, b: Other) -> None:
    await _alice(h)
    for params in (
        {},
        {"status": ["UNDER_REVIEW", "VERIFIED", "UPLOADED", "REJECTED"]},
        {"campus": str(h.world.campus_b1)},
        {"q": b.open_application["number"]},
    ):
        assert b.document["id"] not in _ids(await h.client.get(DOCUMENTS, params=params)), params


async def test_other_tenant_documents_are_not_found(h: Harness, b: Other) -> None:
    csrf = await _alice(h)
    download = await h.client.get(f"{DOCUMENTS}/{b.document['id']}/download")
    assert download.status_code == 404
    assert "content-disposition" not in download.headers
    assert (await decide(h, csrf, b.document)).status_code == 404
    assert (await decide(h, csrf, b.document, reason="Not ours")).status_code == 404
    await _unchanged(h, "application_documents", b.document)
    storage: InMemoryObjectStorage = h.app.state.storage
    assert any(f"/{h.world.tenant_b}/" in key for key in storage.objects)


async def test_student_list_holds_no_other_tenant_student(h: Harness, b: Other) -> None:
    await _alice(h)
    for params in ({}, {"q": "Tenant B"}, {"campus": str(h.world.campus_b1)}):
        assert b.student_id not in _ids(await h.client.get(STUDENTS, params=params)), params


async def test_other_tenant_student_reads_are_not_found(h: Harness, b: Other) -> None:
    await _alice(h)
    for suffix in ("", "/documents", "/activity"):
        response = await h.client.get(f"{STUDENTS}/{b.student_id}{suffix}")
        assert response.status_code == 404, suffix


async def test_a_reviewer_of_tenant_a_cannot_decide_tenant_b(h: Harness, b: Other) -> None:
    """Belt and braces for the review route with an approved application of B."""
    csrf = await _alice(h)
    response = await review(h, csrf, b.admitted, "UNDER_REVIEW")
    assert response.status_code == 404
