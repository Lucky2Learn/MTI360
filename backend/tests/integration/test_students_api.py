"""Students and Student 360 over HTTP (Phase 02-2; ADR-0021 §2, §6, §11).

A student is visible by its home campus; its admissions, documents and
timeline entries by their own campuses. The timeline shows lead history only
to ``lead.read`` holders and application history only to
``application.read`` holders. Students are read-only in the MVP.
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from admissions_support import (
    APPLICATIONS,
    STUDENTS,
    active_course,
    admit,
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
from courses_leads_support import admissions_team, new_lead
from identity_support import Harness, add_membership, add_role, add_user, assign_role, auth_harness
from tenant_admin_support import data, send, sign_in

from app.core.tenancy import system_context

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        await admissions_team(harness)
        use_memory_storage(harness)
        yield harness


async def _admitted_from_lead(h: Harness, campus: uuid.UUID) -> tuple[dict[str, str], str]:
    """A lead → application (with a verified passport) → admission; returns the lead and the
    student ID."""
    csrf = await sign_in(h, "maya")
    course = await active_course(h, csrf)
    lead = await new_lead(h, csrf, campus_id=str(campus), full_name="Vikram Rao")
    data(
        await send(
            h, "POST", f"/api/v1/leads/{lead['id']}/notes", csrf, {"body": "Asked about DNS"}
        ),
        201,
    )
    application = await new_application(h, csrf, course=course, campus=campus, lead=lead)
    application = await ready(h, csrf, application)
    data(await upload(h, csrf, application["id"]), 201)
    application = data(await submit(h, csrf, await reload(h, application)))
    document = data(await h.client.get(f"{APPLICATIONS}/{application['id']}/documents"))["items"][0]
    data(await decide(h, csrf, document))
    application = data(await review(h, csrf, application, "APPROVED"))
    application = data(await admit(h, csrf, application))
    return lead, application["admission"]["student_id"]


async def _member_with(h: Harness, name: str, permissions: tuple[str, ...]) -> None:
    async with system_context(h.factory) as db:
        await add_user(db, h.world, name)
    await add_membership(h.factory, h.world, f"{name}_m", user=name, tenant_id=h.world.tenant_a)
    await add_role(
        h.factory, h.world, f"{name}_role", tenant_id=h.world.tenant_a, permissions=permissions
    )
    await assign_role(h.factory, h.world, f"{name}_m", f"{name}_role")


async def test_student_360_shows_profile_admissions_documents_and_history(h: Harness) -> None:
    lead, student_id = await _admitted_from_lead(h, h.world.campus_a1)
    student = data(await h.client.get(f"{STUDENTS}/{student_id}"))
    assert (student["full_name"], student["status"], student["home_campus"]["id"]) == (
        "Vikram Rao",
        "ACTIVE",
        str(h.world.campus_a1),
    )
    assert student["student_number"].startswith("STU-")
    (admission,) = student["admissions"]
    assert admission["admission_number"].startswith("ADM-")
    assert admission["approved_by"] == {"display_name": "Maya"}
    documents = data(await h.client.get(f"{STUDENTS}/{student_id}/documents"))["items"]
    assert [(d["document_type"], d["status"]) for d in documents] == [("PASSPORT", "VERIFIED")]
    timeline = data(await h.client.get(f"{STUDENTS}/{student_id}/activity"))
    sources = {(entry["source"], entry["kind"]) for entry in timeline}
    assert {
        ("lead", "CREATED"),
        ("lead", "NOTE"),
        ("lead", "APPLICATION_STARTED"),
        ("application", "SUBMITTED"),
        ("application", "DOCUMENT_VERIFIED"),
        ("application", "ADMITTED"),
    } <= sources
    assert timeline[0]["kind"] in {"ADMITTED", "STATUS_CHANGED"}  # newest first
    note = next(entry for entry in timeline if entry["kind"] == "NOTE")
    assert note["body"] == "Asked about DNS"
    listed = data(await h.client.get(STUDENTS, params={"q": "vikram"}))
    assert [item["id"] for item in listed] == [student_id]
    assert listed[0]["admissions"] == 1
    assert lead["id"] not in str(listed)


async def test_students_are_scoped_by_home_campus(h: Harness) -> None:
    _, student_id = await _admitted_from_lead(h, h.world.campus_a1)
    await sign_in(h, "sita")  # campus A2 only
    assert student_id not in {item["id"] for item in data(await h.client.get(STUDENTS))}
    for path in ("", "/activity", "/documents"):
        response = await h.client.get(f"{STUDENTS}/{student_id}{path}")
        assert response.status_code == 404, path
    await sign_in(h, "ravi")  # campus A1 counsellor: reads students and documents
    assert data(await h.client.get(f"{STUDENTS}/{student_id}"))["id"] == student_id
    assert (await h.client.get(f"{STUDENTS}/{uuid.uuid7()}")).status_code == 404


async def test_the_timeline_follows_the_readers_permissions(h: Harness) -> None:
    _, student_id = await _admitted_from_lead(h, h.world.campus_a1)
    await _member_with(h, "registrar", ("student.read",))
    await sign_in(h, "registrar")
    assert data(await h.client.get(f"{STUDENTS}/{student_id}"))["id"] == student_id
    assert data(await h.client.get(f"{STUDENTS}/{student_id}/activity")) == []
    assert (await h.client.get(f"{STUDENTS}/{student_id}/documents")).status_code == 403
    await _member_with(h, "auditor", ("student.read", "application.read"))
    await sign_in(h, "auditor")
    sources = {
        entry["source"] for entry in data(await h.client.get(f"{STUDENTS}/{student_id}/activity"))
    }
    assert sources == {"application"}
    # Without student.read nothing of the student is readable.
    await _member_with(h, "clerk", ("application.read", "document.read"))
    await sign_in(h, "clerk")
    assert (await h.client.get(STUDENTS)).status_code == 403
    assert (await h.client.get(f"{STUDENTS}/{student_id}")).status_code == 403
