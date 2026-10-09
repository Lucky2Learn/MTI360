"""Applications, review and admission over HTTP (Phase 02-2; ADR-0021 §2-§7, §10-§12).

The admissions team of ``courses_leads_support`` signs in through the real
API: Maya (all campuses, admissions manager), Kiran (A1 manager), Ravi (A1
counsellor) and Sita (A2 counsellor). Covered: the full staff-assisted flow
from a lead to a student, validation and field codes, permissions
(counsellors never review or admit), campus scope (404 outside it),
optimistic locking and concurrent admission, explicit student linking, the
second application of a lead, numbering, and audit metadata free of
personal values.
"""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import anyio
import pytest
from admissions_support import (
    APPLICATIONS,
    DETAILS,
    STUDENTS,
    active_course,
    admit,
    approved,
    decide,
    errors,
    new_application,
    patch,
    ready,
    reload,
    review,
    submit,
    upload,
    use_memory_storage,
)
from conftest import DatabaseUnderTest
from courses_leads_support import LEADS, admissions_team, fake_mobile, new_lead
from identity_support import Harness, auth_harness
from tenant_admin_support import data, send, sign_in

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

PERSONAL = ("Arjun", "Meera", "example.com", "90000", "15ZL", "Sea View", "Medical")


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        await admissions_team(harness)
        use_memory_storage(harness)
        yield harness


def _no_personal_values(rows: list[Any]) -> None:
    for row in rows:
        text = repr(row.metadata)
        assert not any(value in text for value in PERSONAL), row.event_type


async def test_a_lead_becomes_an_admitted_student(h: Harness) -> None:
    w = h.world
    manager = await sign_in(h, "maya")
    course = await active_course(h, manager, "GPR")
    counsellor = await sign_in(h, "ravi")
    lead = await new_lead(
        h,
        counsellor,
        full_name="Arjun Nair",
        email="arjun.nair@example.com",
        campus_id=str(w.campus_a1),
        interested_course_id=course["id"],
        owner="me",
        city="Ratnagiri",
    )
    created_response = await send(
        h,
        "POST",
        APPLICATIONS,
        counsellor,
        {"lead_id": lead["id"], "course_id": course["id"], "campus_id": str(w.campus_a1)},
    )
    application = data(created_response, 201)
    # Prefilled from the lead server-side; owned by the lead's counsellor; a draft.
    assert application["number"].startswith("APP-")
    assert (application["full_name"], application["email"], application["city"]) == (
        "Arjun Nair",
        "arjun.nair@example.com",
        "Ratnagiri",
    )
    assert application["status"] == "DRAFT"
    assert application["owner"] == {"display_name": "Ravi"}
    assert application["lead"] == {
        "id": lead["id"],
        "full_name": "Arjun Nair",
        "status": "APPLICATION",
    }
    assert set(application["missing_for_submit"]) == {
        "date_of_birth",
        "highest_qualification",
        "declaration",
    }
    audited = {row.event_type: row.metadata for row in await h.audit(created_response)}
    assert audited == {
        "application.created": {"from_lead": True},
        "lead.status_changed": {"from": "NEW", "to": "APPLICATION", "has_reason": False},
    }
    lead_now = data(await h.client.get(f"{LEADS}/{lead['id']}"))
    assert lead_now["status"] == "APPLICATION"

    passport = data(await upload(h, counsellor, application["id"]), 201)
    assert passport["status"] == "UPLOADED"
    application = await ready(h, counsellor, application)
    assert (application["missing_for_submit"], application["declared_by"]) == (
        [],
        {"display_name": "Ravi"},
    )
    submitted = await submit(h, counsellor, application)
    application = data(submitted)
    assert application["status"] == "SUBMITTED"
    assert application["documents"] == {"total": 1, "verified": 0, "pending": 1}

    # The manager verifies the document, approves and admits.
    manager = await sign_in(h, "maya")
    documents = data(await h.client.get(f"{APPLICATIONS}/{application['id']}/documents"))["items"]
    assert [d["status"] for d in documents] == ["UNDER_REVIEW"]
    data(await decide(h, manager, documents[0]))
    application = data(await review(h, manager, application, "UNDER_REVIEW"))
    approval = await review(h, manager, application, "APPROVED")
    application = data(approval)
    assert application["status"] == "APPROVED"
    assert application["reviewed_by"] == {"display_name": "Maya"}
    candidates = data(await h.client.get(f"{APPLICATIONS}/{application['id']}/student-candidates"))[
        "candidates"
    ]
    assert candidates == []
    admitted_response = await admit(h, manager, application)
    application = data(admitted_response)
    assert application["status"] == "ADMITTED"
    admission = application["admission"]
    assert admission["admission_number"].startswith("ADM-")
    assert admission["student_number"].startswith("STU-")
    assert admission["student_visible"] is True
    lead_now = data(await h.client.get(f"{LEADS}/{lead['id']}"))
    assert lead_now["status"] == "ADMITTED"
    events = {row.event_type for row in await h.audit(admitted_response)}
    assert events == {"student.created", "admission.approved", "lead.status_changed"}
    _no_personal_values(await h.audit(admitted_response))
    _no_personal_values(await h.audit(submitted))

    student = data(await h.client.get(f"{STUDENTS}/{admission['student_id']}"))
    assert (student["full_name"], student["home_campus"]["id"]) == ("Arjun Nair", str(w.campus_a1))
    assert [a["admission_number"] for a in student["admissions"]] == [admission["admission_number"]]
    kinds = [
        a["kind"] for a in data(await h.client.get(f"{APPLICATIONS}/{application['id']}/activity"))
    ]
    assert kinds == [
        "ADMITTED",
        "STATUS_CHANGED",
        "STATUS_CHANGED",
        "DOCUMENT_VERIFIED",
        "SUBMITTED",
        "UPDATED",
        "DOCUMENT_UPLOADED",
        "CREATED",
    ]
    # Final: nothing changes any more.
    assert errors(await patch(h, manager, application, city="Pune")) == {
        ("status", "application_locked")
    }
    assert errors(await review(h, manager, application, "REJECTED", "x")) == {
        ("to_status", "invalid_transition")
    }
    assert errors(await admit(h, manager, application)) == {("status", "invalid_transition")}


async def test_creation_is_validated(h: Harness) -> None:
    w = h.world
    manager = await sign_in(h, "maya")
    course = await active_course(h, manager)
    other = await active_course(h, manager)
    draft = await active_course(h, manager)
    data(
        await send(
            h,
            "POST",
            f"/api/v1/courses/{draft['id']}/status",
            manager,
            {"status": "ARCHIVED", "version": draft["version"]},
        )
    )
    other_campus_lead = await new_lead(h, manager, campus_id=str(w.campus_a2))
    counsellor = await sign_in(h, "ravi")  # campus A1 only
    lost = await new_lead(h, counsellor, campus_id=str(w.campus_a1))
    lost = data(
        await send(
            h,
            "POST",
            f"{LEADS}/{lost['id']}/transition",
            counsellor,
            {"to_status": "LOST", "reason": "No response", "version": lost["version"]},
        )
    )

    async def create(**body: Any) -> Any:
        return await send(h, "POST", APPLICATIONS, counsellor, body)

    base = {"course_id": course["id"], "campus_id": str(w.campus_a1), "full_name": "Meera Pillai"}
    assert errors(await create(**{**base, "campus_id": str(w.campus_a2)})) == {
        ("campus_id", "campus_not_available")
    }
    assert errors(await create(**{**base, "campus_id": str(uuid.uuid7())})) == {
        ("campus_id", "campus_not_available")
    }
    assert errors(await create(**{**base, "course_id": draft["id"]})) == {
        ("course_id", "course_not_active")
    }
    assert errors(await create(**{**base, "lead_id": lost["id"]})) == {("lead_id", "lead_closed")}
    assert errors(await create(**{**base, "lead_id": other_campus_lead["id"]})) == {
        ("lead_id", "lead_not_available")
    }
    assert errors(await create(**{**base, "full_name": "  "})) == {("full_name", "required")}
    assert errors(
        await create(
            **{**base, "email": "not-an-email", "indos_number": "!", "date_of_birth": "2999-01-01"}
        )
    ) == {("email", "invalid"), ("indos_number", "invalid"), ("date_of_birth", "invalid")}
    # Unknown fields, such as a tenant or a status, are refused outright.
    for extra in ({"tenant_id": str(w.tenant_b)}, {"status": "APPROVED"}, {"number": "APP-1"}):
        response = await create(**base, **extra)
        assert response.status_code == 422, extra
    # One open application per lead and course; another course is fine.
    lead = await new_lead(h, counsellor, campus_id=str(w.campus_a1))
    first = await new_application(h, counsellor, course=course, campus=w.campus_a1, lead=lead)
    assert errors(
        await new_application(
            h, counsellor, course=course, campus=w.campus_a1, lead=lead, status=422
        )
    ) == {("course_id", "application_exists")}
    second = await new_application(h, counsellor, course=other, campus=w.campus_a1, lead=lead)
    assert first["number"] != second["number"]
    lead_now = data(await h.client.get(f"{LEADS}/{lead['id']}"))
    assert lead_now["status"] == "APPLICATION"
    started = [
        a["details"]["application_number"]
        for a in data(await h.client.get(f"{LEADS}/{lead['id']}/activity"))
        if a["kind"] == "APPLICATION_STARTED"
    ]
    assert started == [second["number"], first["number"]]


async def test_drafts_are_edited_with_versions_and_submitted_when_complete(h: Harness) -> None:
    w = h.world
    manager = await sign_in(h, "maya")
    course, other = await active_course(h, manager), await active_course(h, manager)
    application = await new_application(h, manager, course=course, campus=w.campus_a1)
    stale = dict(application)
    application = data(await patch(h, manager, application, city="Mumbai", course_id=other["id"]))
    assert (application["city"], application["course"]["id"]) == ("Mumbai", other["id"])
    conflict = await patch(h, manager, stale, city="Pune")
    assert conflict.status_code == 409
    assert errors(await submit(h, manager, application)) == {
        ("date_of_birth", "required_for_submit"),
        ("highest_qualification", "required_for_submit"),
        ("declaration", "required_for_submit"),
    }
    assert errors(await patch(h, manager, application, campus_id=str(uuid.uuid7()))) == {
        ("campus_id", "campus_not_available")
    }
    application = await ready(h, manager, application)
    unchanged = data(await patch(h, manager, application, city="Mumbai"))
    assert unchanged["version"] == application["version"]  # no change, no new version
    withdrawn = data(await patch(h, manager, application, declaration_confirmed=False))
    assert withdrawn["declared_at"] is None
    application = data(await patch(h, manager, withdrawn, declaration_confirmed=True))
    application = data(await submit(h, manager, application))
    assert errors(await patch(h, manager, application, city="Pune")) == {
        ("status", "application_locked")
    }
    assert errors(await submit(h, manager, application)) == {("status", "invalid_transition")}


async def test_review_decisions_reasons_documents_and_correction(h: Harness) -> None:
    w = h.world
    manager = await sign_in(h, "maya")
    course = await active_course(h, manager)
    application = await ready(
        h, manager, await new_application(h, manager, course=course, campus=w.campus_a1)
    )
    document = data(await upload(h, manager, application["id"]), 201)
    application = data(await submit(h, manager, await reload(h, application)))
    for target in ("CORRECTION_REQUIRED", "REJECTED", "NOT_ELIGIBLE"):
        assert errors(await review(h, manager, application, target)) == {
            ("reason", "reason_required")
        }
    assert errors(await review(h, manager, application, "APPROVED")) == {
        ("documents", "documents_not_verified")
    }
    documents = data(await h.client.get(f"{APPLICATIONS}/{application['id']}/documents"))["items"]
    rejected = data(await decide(h, manager, documents[0], reason="Scan is unreadable"))
    assert rejected["status"] == "REJECTED"
    # Back to the applicant: correction, a replacement, resubmission.
    corrected = await review(h, manager, application, "CORRECTION_REQUIRED", "Re-scan the passport")
    application = data(corrected)
    assert (application["status"], application["status_reason"]) == (
        "CORRECTION_REQUIRED",
        "Re-scan the passport",
    )
    assert application["editable"] is True
    (event,) = await h.audit(corrected)
    assert event.metadata == {"from": "SUBMITTED", "to": "CORRECTION_REQUIRED", "has_reason": True}
    replacement = data(await upload(h, manager, application["id"], replaces=document["id"]), 201)
    assert replacement["status"] == "UPLOADED"
    application = data(await patch(h, manager, application, city="Navi Mumbai"))
    resubmitted = await submit(h, manager, application)
    application = data(resubmitted)
    (event,) = [e for e in await h.audit(resubmitted) if e.event_type == "application.submitted"]
    assert event.metadata == {"resubmission": True}
    assert application["status_reason"] is None
    pending = data(await h.client.get(f"{APPLICATIONS}/{application['id']}/documents"))["items"]
    current = [d for d in pending if d["current"]]
    assert [(d["status"], d["id"]) for d in current] == [("UNDER_REVIEW", replacement["id"])]
    data(await decide(h, manager, current[0]))
    application = data(await review(h, manager, application, "APPROVED"))
    assert application["documents"] == {"total": 1, "verified": 1, "pending": 0}
    # A rejected application is final.
    other = await ready(
        h, manager, await new_application(h, manager, course=course, campus=w.campus_a1)
    )
    other = data(await submit(h, manager, other))
    other = data(await review(h, manager, other, "NOT_ELIGIBLE", "Below the PCM requirement"))
    assert errors(await review(h, manager, other, "UNDER_REVIEW")) == {
        ("to_status", "invalid_transition")
    }
    assert other["review_options"] == []


async def test_counsellors_do_not_review_or_admit(h: Harness) -> None:
    w = h.world
    manager = await sign_in(h, "maya")
    course = await active_course(h, manager)
    application = await approved(h, manager, course=course, campus=w.campus_a1)
    counsellor = await sign_in(h, "ravi")
    assert (await review(h, counsellor, application, "REJECTED", "x")).status_code == 403
    assert (await admit(h, counsellor, application)).status_code == 403
    candidates = await h.client.get(f"{APPLICATIONS}/{application['id']}/student-candidates")
    assert candidates.status_code == 403
    # ... but they read it, and start and edit applications.
    assert data(await h.client.get(f"{APPLICATIONS}/{application['id']}"))["status"] == "APPROVED"
    mine = await new_application(h, counsellor, course=course, campus=w.campus_a1)
    assert mine["owner"] == {"display_name": "Ravi"}


async def test_campus_scope_hides_other_campuses(h: Harness) -> None:
    w = h.world
    manager = await sign_in(h, "maya")
    course = await active_course(h, manager)
    a1 = await new_application(h, manager, course=course, campus=w.campus_a1)
    a2 = await new_application(h, manager, course=course, campus=w.campus_a2)
    sita = await sign_in(h, "sita")  # campus A2 only
    listed = {item["id"] for item in data(await h.client.get(APPLICATIONS))}
    assert a2["id"] in listed
    assert a1["id"] not in listed
    for path in ("", "/activity", "/documents"):
        response = await h.client.get(f"{APPLICATIONS}/{a1['id']}{path}")
        assert response.status_code == 404, path
    assert (await patch(h, sita, a1, city="Goa")).status_code == 404
    assert (await submit(h, sita, a1)).status_code == 404
    assert (await upload(h, sita, a1["id"])).status_code == 404
    # A restricted manager cannot move an application to a campus outside their scope.
    kiran = await sign_in(h, "kiran")  # A1 only
    mine = await new_application(h, kiran, course=course, campus=w.campus_a1)
    assert errors(await patch(h, kiran, mine, campus_id=str(w.campus_a2))) == {
        ("campus_id", "campus_not_available")
    }


async def test_admission_links_only_an_explicitly_chosen_visible_student(h: Harness) -> None:
    w = h.world
    manager = await sign_in(h, "maya")
    course, refresher = await active_course(h, manager), await active_course(h, manager)
    mobile = fake_mobile()
    first = await approved(
        h, manager, course=course, campus=w.campus_a1, full_name="Meera Pillai", mobile=mobile
    )
    first = data(await admit(h, manager, first))
    student_id = first["admission"]["student_id"]
    # The same person returns for a Post-Sea refresher at the same campus.
    second = await approved(
        h, manager, course=refresher, campus=w.campus_a1, full_name="Meera Pillai", mobile=mobile
    )
    candidates = data(await h.client.get(f"{APPLICATIONS}/{second['id']}/student-candidates"))[
        "candidates"
    ]
    assert [(c["id"], c["matched_on"]) for c in candidates] == [(student_id, ["mobile"])]
    assert errors(await admit(h, manager, second, student="existing")) == {
        ("student_id", "required")
    }
    assert errors(await admit(h, manager, second, "existing", str(uuid.uuid7()))) == {
        ("student_id", "student_not_available")
    }
    linked = data(await admit(h, manager, second, "existing", student_id))
    assert linked["admission"]["student_id"] == student_id
    student = data(await h.client.get(f"{STUDENTS}/{student_id}"))
    assert len(student["admissions"]) == 2
    # A student of a campus the approver cannot see is neither offered nor linkable.
    kiran = await sign_in(h, "kiran")  # A1 only
    manager = await sign_in(h, "maya")
    a2_student = data(
        await admit(
            h,
            manager,
            await approved(h, manager, course=course, campus=w.campus_a2, mobile=mobile),
        )
    )["admission"]["student_id"]
    kiran = await sign_in(h, "kiran")
    third = await approved(h, kiran, course=course, campus=w.campus_a1, mobile=mobile)
    offered = data(await h.client.get(f"{APPLICATIONS}/{third['id']}/student-candidates"))
    assert a2_student not in {c["id"] for c in offered["candidates"]}
    assert errors(await admit(h, kiran, third, "existing", a2_student)) == {
        ("student_id", "student_not_available")
    }
    # Creating a new student is always an explicit, allowed choice.
    assert data(await admit(h, kiran, third))["admission"]["student_id"] not in {
        student_id,
        a2_student,
    }


async def test_concurrent_admissions_create_one_admission(h: Harness) -> None:
    w = h.world
    manager = await sign_in(h, "maya")
    course = await active_course(h, manager)
    application = await approved(h, manager, course=course, campus=w.campus_a1)
    results: list[int] = []

    async def attempt() -> None:
        results.append((await admit(h, manager, application)).status_code)

    async with anyio.create_task_group() as group:
        group.start_soon(attempt)
        group.start_soon(attempt)
    assert sorted(results) == [200, 409]
    rows = await h.owner(
        "SELECT count(*) FROM admissions WHERE application_id = :a", a=uuid.UUID(application["id"])
    )
    assert rows[0][0] == 1


async def test_numbers_are_unique_and_sequential_per_tenant(h: Harness) -> None:
    w = h.world
    manager = await sign_in(h, "maya")
    course = await active_course(h, manager)
    created: list[str] = []

    async def create() -> None:
        created.append(
            (await new_application(h, manager, course=course, campus=w.campus_a1))["number"]
        )

    async with anyio.create_task_group() as group:
        for _ in range(4):
            group.start_soon(create)
    assert len(set(created)) == 4
    values = sorted(int(number.rsplit("-", 1)[1]) for number in created)
    assert values == list(range(values[0], values[0] + 4))
    # Institute B has its own sequence.
    carol = await sign_in(h, "carol")
    b_course = await active_course(h, carol)
    b_app = await new_application(h, carol, course=b_course, campus=w.campus_b1)
    assert b_app["number"].endswith("-00001") or int(b_app["number"].rsplit("-", 1)[1]) >= 1


async def test_lists_filter_and_search(h: Harness) -> None:
    w = h.world
    manager = await sign_in(h, "maya")
    course = await active_course(h, manager)
    one = await new_application(
        h, manager, course=course, campus=w.campus_a1, full_name="Kabir Desai", mobile=fake_mobile()
    )
    two = await approved(h, manager, course=course, campus=w.campus_a2)
    found = data(await h.client.get(APPLICATIONS, params={"q": "kabir"}))
    assert [item["id"] for item in found] == [one["id"]]
    by_number = data(await h.client.get(APPLICATIONS, params={"q": two["number"]}))
    assert [item["id"] for item in by_number] == [two["id"]]
    approved_only = data(
        await h.client.get(APPLICATIONS, params={"status": "APPROVED", "campus": str(w.campus_a2)})
    )
    assert {item["id"] for item in approved_only} == {two["id"]}
    bad = await h.client.get(APPLICATIONS, params={"status": "WITHDRAWN"})
    assert bad.status_code == 422
    bad_sort = await h.client.get(APPLICATIONS, params={"sort": "mobile"})
    assert bad_sort.status_code == 422
    assert DETAILS["indos_number"] not in str(found)
