"""Leads over HTTP (Phase 02-1; blueprint §7-§10, §13, §17, §25).

Creation and validation, the ACTIVE-course rule, the private duplicate
warning, the staff pipeline, assignment eligibility, campus visibility (the
institute pool included), optimistic locking, and audit metadata free of
personal data.
"""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from conftest import DatabaseUnderTest
from courses_leads_support import COURSES, LEADS, admissions_team, fake_mobile, new_course, new_lead
from identity_support import Harness, auth_harness
from sqlalchemy import text
from tenant_admin_support import data, send, sign_in

from app.core.context import Realm, RequestContext
from app.core.db.session import context_transaction
from app.core.errors import ValidationFailedError
from app.core.tenancy import system_context
from app.modules.leads import service

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        await admissions_team(harness)
        yield harness


def _code() -> str:
    return f"L{uuid.uuid7().hex[-7:]}".upper()


def _errors(response: Any) -> set[tuple[str, str]]:
    assert response.status_code == 422, response.text
    return {(d["field"], d["code"]) for d in response.json()["error"]["details"]}


async def _activity(h: Harness, lead_id: str) -> list[dict[str, Any]]:
    response = await h.client.get(f"{LEADS}/{lead_id}/activity")
    return data(response)  # type: ignore[no-any-return]


async def _move(h: Harness, csrf: str, lead: dict[str, Any], to: str, **extra: Any) -> Any:
    body = {"to_status": to, "version": lead["version"], **extra}
    return await send(h, "POST", f"{LEADS}/{lead['id']}/transition", csrf, body)


# --- Create ------------------------------------------------------------------------------------


async def test_a_counsellor_logs_a_walk_in_for_their_campus(h: Harness) -> None:
    manager = await sign_in(h, "maya")
    course = await new_course(h, manager, _code())
    csrf = await sign_in(h, "ravi")
    created = await send(
        h,
        "POST",
        LEADS,
        csrf,
        {
            "full_name": "  Arjun   Nair ",
            "mobile": "+91 90000 10001",
            "email": "Arjun.Nair@Example.com",
            "source": "WALK_IN",
            "interested_course_id": course["id"],
            "campus_id": str(h.world.campus_a1),
            "owner": "me",
            "date_of_birth": "2007-05-14",
            "city": "Ratnagiri",
            "highest_qualification": "12th PCM, 68%",
        },
    )
    lead = data(created, 201)
    assert lead["full_name"] == "Arjun Nair"
    assert (lead["status"], lead["source"], lead["version"]) == ("NEW", "WALK_IN", 1)
    assert lead["interested_course"]["id"] == course["id"]
    assert lead["campus"]["id"] == str(h.world.campus_a1)
    assert lead["owner"]["membership_id"] == str(h.world.memberships["ravi_m"])
    assert lead["owner"]["active"] is True
    assert lead["created_by"] == {"display_name": "Ravi"}
    assert {t["to_status"] for t in lead["transitions"]} >= {"CONTACTED", "LOST", "DUPLICATE"}
    assert "APPLICATION" not in {t["to_status"] for t in lead["transitions"]}
    (event,) = await h.audit(created)
    assert (event.event_type, event.category) == ("lead.created", "domain")
    assert event.metadata == {
        "source": "WALK_IN",
        "has_course": True,
        "has_campus": True,
        "has_owner": True,
    }
    (activity,) = await _activity(h, lead["id"])
    assert activity["kind"] == "CREATED"
    assert activity["details"] == {"source": "WALK_IN", "possible_duplicates": 0}
    assert activity["actor"] == {"display_name": "Ravi"}


async def test_lead_validation(h: Harness) -> None:
    manager = await sign_in(h, "maya")
    draft = await new_course(h, manager, _code(), activate=False)
    archived = await new_course(h, manager, _code())
    data(
        await send(
            h,
            "POST",
            f"{COURSES}/{archived['id']}/status",
            manager,
            {"status": "ARCHIVED", "version": archived["version"]},
        )
    )
    csrf = await sign_in(h, "ravi")
    base = {"full_name": "Arjun Nair", "source": "PHONE"}

    def with_mobile(**extra: Any) -> dict[str, Any]:
        return base | {"mobile": fake_mobile(), **extra}

    inactive = {("interested_course_id", "course_not_active")}
    unavailable = {("campus_id", "campus_not_available")}
    cases: list[tuple[dict[str, Any], set[tuple[str, str]]]] = [
        (base, {("mobile", "contact_required")}),
        (base | {"mobile": "call me"}, {("mobile", "invalid")}),
        (base | {"email": "arjun"}, {("email", "invalid")}),
        (with_mobile(date_of_birth="2099-01-01"), {("date_of_birth", "invalid")}),
        (with_mobile(interested_course_id=draft["id"]), inactive),
        (with_mobile(interested_course_id=archived["id"]), inactive),
        (with_mobile(interested_course_id=str(uuid.uuid7())), inactive),
        # Another campus, an unknown one and another tenant's one answer identically.
        (with_mobile(campus_id=str(h.world.campus_a2)), unavailable),
        (with_mobile(campus_id=str(uuid.uuid7())), unavailable),
        (with_mobile(campus_id=str(h.world.campus_b1)), unavailable),
    ]
    for body, expected in cases:
        assert _errors(await send(h, "POST", LEADS, csrf, body)) == expected, body
    for body in (
        base | {"mobile": fake_mobile(), "tenant_id": str(h.world.tenant_b)},
        base | {"mobile": fake_mobile(), "status": "QUALIFIED"},
        base | {"mobile": fake_mobile(), "source": "TELEPATHY"},
        {"mobile": fake_mobile(), "source": "PHONE"},
    ):
        assert (await send(h, "POST", LEADS, csrf, body)).status_code == 422, body


async def test_only_assigners_give_a_new_lead_to_someone_else(h: Harness) -> None:
    sita = str(h.world.memberships["sita_m"])
    csrf = await sign_in(h, "ravi")
    other = await send(
        h,
        "POST",
        LEADS,
        csrf,
        {"full_name": "Meera Iyer", "mobile": fake_mobile(), "source": "PHONE", "owner": sita},
    )
    assert other.status_code == 403
    mine = await new_lead(h, csrf, owner=str(h.world.memberships["ravi_m"]))  # self by ID is fine
    assert mine["owner"]["display_name"] == "Ravi"
    manager = await sign_in(h, "maya")
    given = await new_lead(h, manager, owner=sita, campus_id=str(h.world.campus_a2))
    assert given["owner"]["display_name"] == "Sita"
    # Sita does not work at campus A1: not an eligible owner there.
    refused = await send(
        h,
        "POST",
        LEADS,
        manager,
        {
            "full_name": "Meera Iyer",
            "mobile": fake_mobile(),
            "source": "PHONE",
            "owner": sita,
            "campus_id": str(h.world.campus_a1),
        },
    )
    assert _errors(refused) == {("owner", "owner_not_eligible")}


async def test_archived_courses_stay_on_existing_leads(h: Harness) -> None:
    manager = await sign_in(h, "maya")
    course = await new_course(h, manager, _code())
    lead = await new_lead(h, manager, interested_course_id=course["id"])
    data(
        await send(
            h,
            "POST",
            f"{COURSES}/{course['id']}/status",
            manager,
            {"status": "ARCHIVED", "version": course["version"]},
        )
    )
    kept = data(await h.client.get(f"{LEADS}/{lead['id']}"))
    assert kept["interested_course"]["status"] == "ARCHIVED"
    # Other edits keep the archived course; choosing it again is not a change.
    edited = data(
        await send(
            h,
            "PATCH",
            f"{LEADS}/{lead['id']}",
            manager,
            {"city": "Pune", "interested_course_id": course["id"], "version": lead["version"]},
        )
    )
    assert edited["interested_course"]["id"] == course["id"]
    other = await new_lead(h, manager)
    refused = await send(
        h,
        "PATCH",
        f"{LEADS}/{other['id']}",
        manager,
        {"interested_course_id": course["id"], "version": other["version"]},
    )
    assert _errors(refused) == {("interested_course_id", "course_not_active")}


# --- Duplicate warning -------------------------------------------------------------------------


async def test_possible_duplicates_warn_without_blocking(h: Harness) -> None:
    csrf = await sign_in(h, "maya")
    mobile = fake_mobile()
    first = await new_lead(
        h, csrf, mobile=mobile, email=f"meera.{uuid.uuid7().hex[-6:]}@example.com"
    )
    variant = "0" + mobile.replace("+91", "").replace(" ", "")
    check = data(await send(h, "POST", f"{LEADS}/duplicate-check", csrf, {"mobile": variant}))
    assert [(c["id"], c["matched_on"]) for c in check["candidates"]] == [(first["id"], ["mobile"])]
    both = data(
        await send(
            h,
            "POST",
            f"{LEADS}/duplicate-check",
            csrf,
            {"mobile": mobile, "email": first["email"].upper()},
        )
    )
    assert both["candidates"][0]["matched_on"] == ["mobile", "email"]
    assert set(both["candidates"][0]) == {
        "id",
        "full_name",
        "status",
        "course_name",
        "campus_name",
        "owner_name",
        "created_at",
        "matched_on",
    }
    # Creation is never blocked; the CREATED activity counts the visible candidates only.
    second = await new_lead(h, csrf, mobile=variant)
    (created,) = await _activity(h, second["id"])
    assert created["details"]["possible_duplicates"] == 1
    excluded = data(
        await send(
            h,
            "POST",
            f"{LEADS}/duplicate-check",
            csrf,
            {"mobile": mobile, "exclude_lead_id": second["id"]},
        )
    )
    assert [c["id"] for c in excluded["candidates"]] == [first["id"]]
    # A lead marked DUPLICATE is no longer a candidate.
    data(await _move(h, csrf, second, "DUPLICATE", duplicate_of_lead_id=first["id"]))
    again = data(await send(h, "POST", f"{LEADS}/duplicate-check", csrf, {"mobile": mobile}))
    assert [c["id"] for c in again["candidates"]] == [first["id"]]
    assert (await send(h, "POST", f"{LEADS}/duplicate-check", csrf, {})).status_code == 422


async def test_the_duplicate_warning_never_discloses_invisible_leads(h: Harness) -> None:
    manager = await sign_in(h, "maya")
    mobile = fake_mobile()
    hidden = await new_lead(h, manager, mobile=mobile, campus_id=str(h.world.campus_a2))
    # Ravi (campus A1) sees nothing at all: no candidate, no count, no hint.
    ravi = await sign_in(h, "ravi")
    check = await send(h, "POST", f"{LEADS}/duplicate-check", ravi, {"mobile": mobile})
    assert data(check) == {"candidates": []}
    assert hidden["id"] not in check.text
    created = await new_lead(h, ravi, mobile=mobile)
    (activity,) = await _activity(h, created["id"])
    assert activity["details"]["possible_duplicates"] == 0
    # Another tenant never matches.
    carol = await sign_in(h, "carol")
    assert data(await send(h, "POST", f"{LEADS}/duplicate-check", carol, {"mobile": mobile})) == {
        "candidates": []
    }
    # A pool lead is visible to every campus, so it is a candidate for Ravi.
    manager = await sign_in(h, "maya")
    pool = await new_lead(h, manager, mobile=(pool_mobile := fake_mobile()))
    ravi = await sign_in(h, "ravi")
    seen = data(await send(h, "POST", f"{LEADS}/duplicate-check", ravi, {"mobile": pool_mobile}))
    assert [c["id"] for c in seen["candidates"]] == [pool["id"]]


async def test_at_most_five_candidates(h: Harness) -> None:
    csrf = await sign_in(h, "maya")
    email = f"family.{uuid.uuid7().hex[-6:]}@example.com"
    for _ in range(6):
        await new_lead(h, csrf, email=email)
    check = data(await send(h, "POST", f"{LEADS}/duplicate-check", csrf, {"email": email}))
    assert len(check["candidates"]) == 5


# --- Pipeline ----------------------------------------------------------------------------------


async def test_a_lead_moves_through_the_pipeline_and_closes_with_reasons(h: Harness) -> None:
    csrf = await sign_in(h, "ravi")
    lead = await new_lead(h, csrf, campus_id=str(h.world.campus_a1))
    for status in ("CONTACTED", "QUALIFIED", "COUNSELLING", "QUALIFIED", "INTERESTED"):
        moved = await _move(h, csrf, lead, status)
        lead = data(moved)
        assert lead["status"] == status
    (event,) = await h.audit(moved)
    assert (event.event_type, event.metadata) == (
        "lead.status_changed",
        {"from": "QUALIFIED", "to": "INTERESTED", "has_reason": False},
    )
    assert _errors(await _move(h, csrf, lead, "LOST")) == {("reason", "reason_required")}
    reason = "Joined another institute in Kochi"
    lost = await _move(h, csrf, lead, "LOST", reason=reason)
    lead = data(lost)
    assert (lead["status"], lead["status_reason"]) == ("LOST", reason)
    (event,) = await h.audit(lost)
    assert event.metadata == {"from": "INTERESTED", "to": "LOST", "has_reason": True}
    assert reason not in str(event.metadata)
    # Reopening needs a reason; closed → closed is not a move.
    assert _errors(await _move(h, csrf, lead, "CONTACTED")) == {("reason", "reason_required")}
    assert _errors(await _move(h, csrf, lead, "DEFERRED", reason="x")) == {
        ("to_status", "invalid_transition")
    }
    lead = data(await _move(h, csrf, lead, "CONTACTED", reason="Called back"))
    assert lead["status_reason"] == "Called back"
    history = [a for a in await _activity(h, lead["id"]) if a["kind"] == "STATUS_CHANGED"]
    assert history[0]["details"] == {"from": "LOST", "to": "CONTACTED", "reason": "Called back"}
    assert len(history) == 7


async def test_application_states_and_no_op_moves_are_refused(h: Harness) -> None:
    csrf = await sign_in(h, "ravi")
    lead = await new_lead(h, csrf)
    for target in ("APPLICATION", "ADMITTED", "NEW"):
        assert _errors(await _move(h, csrf, lead, target)) == {
            ("to_status", "invalid_transition")
        }, target
    assert (await _move(h, csrf, lead, "ENROLLED")).status_code == 422
    assert (await _move(h, csrf, lead | {"version": 99}, "CONTACTED")).status_code == 409


async def test_duplicate_links_need_a_visible_original(h: Harness) -> None:
    manager = await sign_in(h, "maya")
    other_campus = await new_lead(h, manager, campus_id=str(h.world.campus_a2))
    original = await new_lead(h, manager, campus_id=str(h.world.campus_a1))
    csrf = await sign_in(h, "ravi")
    lead = await new_lead(h, csrf)
    invalid = {("duplicate_of_lead_id", "duplicate_target_invalid")}
    for target in (None, lead["id"], other_campus["id"], str(uuid.uuid7())):
        response = await _move(h, csrf, lead, "DUPLICATE", duplicate_of_lead_id=target)
        assert _errors(response) == invalid, target
    marked = data(await _move(h, csrf, lead, "DUPLICATE", duplicate_of_lead_id=original["id"]))
    assert marked["duplicate_of"] == {"id": original["id"], "full_name": "Arjun Nair"}
    # A duplicate cannot be the original of another duplicate.
    third = await new_lead(h, csrf)
    response = await _move(h, csrf, third, "DUPLICATE", duplicate_of_lead_id=marked["id"])
    assert _errors(response) == invalid
    # Reopening clears the link.
    reopened = data(await _move(h, csrf, marked, "NEW", reason="Different course"))
    assert reopened["duplicate_of"] is None


async def test_the_application_entry_point_is_a_system_transition_for_open_leads(
    h: Harness,
) -> None:
    csrf = await sign_in(h, "maya")
    open_lead = await new_lead(h, csrf)
    closed = data(await _move(h, csrf, await new_lead(h, csrf), "LOST", reason="No response"))
    async with system_context(h.factory, tenant_id=h.world.tenant_a) as db:
        lead = await service.mark_application_started(
            db, uuid.UUID(open_lead["id"]), actor_membership_id=None
        )
        assert lead.status == "APPLICATION"
    async with system_context(h.factory, tenant_id=h.world.tenant_a) as db:
        with pytest.raises(ValidationFailedError):
            await service.mark_application_started(
                db, uuid.UUID(closed["id"]), actor_membership_id=None
            )
    progressed = data(await h.client.get(f"{LEADS}/{open_lead['id']}"))
    assert progressed["status"] == "APPLICATION"
    assert progressed["transitions"] == []  # staff cannot move it in 02-1


# --- Assignment --------------------------------------------------------------------------------


async def test_managers_assign_owner_and_campus_with_eligibility(h: Harness) -> None:
    w = h.world
    ravi, sita = str(w.memberships["ravi_m"]), str(w.memberships["sita_m"])
    csrf = await sign_in(h, "maya")
    lead = await new_lead(h, csrf)  # institute pool, unassigned

    async def assign(owner: str | None, campus: uuid.UUID | None) -> Any:
        body = {
            "owner_membership_id": owner,
            "campus_id": str(campus) if campus else None,
            "version": lead["version"],
        }
        return await send(h, "POST", f"{LEADS}/{lead['id']}/assign", csrf, body)

    assigned = await assign(ravi, w.campus_a1)
    lead = data(assigned)
    assert (lead["owner"]["display_name"], lead["campus"]["id"]) == ("Ravi", str(w.campus_a1))
    (event,) = await h.audit(assigned)
    assert (event.event_type, event.metadata) == (
        "lead.assigned",
        {"owner_changed": True, "campus_changed": True},
    )
    activity = (await _activity(h, lead["id"]))[0]
    assert activity["kind"] == "ASSIGNED"
    assert activity["details"]["owner_to_name"] == "Ravi"
    assert activity["details"]["campus_to_name"] == "Mum Campus"
    # Moving the lead to campus A2 while Ravi (A1 only) still owns it is refused.
    assert _errors(await assign(ravi, w.campus_a2)) == {("owner", "owner_not_eligible")}
    lead = data(await assign(sita, w.campus_a2))
    # Ineligible owners: no lead.update (Dave's custom role), suspended, unknown, other tenant.
    await h.owner(
        "UPDATE tenant_memberships SET status = 'SUSPENDED' WHERE id = :m",
        m=w.memberships["kiran_m"],
    )
    for owner in (
        str(w.memberships["dave_a"]),
        str(w.memberships["kiran_m"]),
        str(uuid.uuid7()),
        str(w.memberships["carol_b"]),
    ):
        assert _errors(await assign(owner, None)) == {("owner", "owner_not_eligible")}, owner
    assert _errors(await assign(None, w.campus_b1)) == {("campus_id", "campus_not_available")}
    # Unassign into the pool.
    lead = data(await assign(None, None))
    assert (lead["owner"], lead["campus"]) == (None, None)
    assert (await assign(None, None)).status_code == 200  # no change, no event
    stale = await send(
        h,
        "POST",
        f"{LEADS}/{lead['id']}/assign",
        csrf,
        {"owner_membership_id": ravi, "campus_id": None, "version": 1},
    )
    assert stale.status_code == 409


async def test_counsellors_cannot_assign_and_restricted_managers_stay_in_their_campus(
    h: Harness,
) -> None:
    w = h.world
    manager = await sign_in(h, "maya")
    a2_lead = await new_lead(h, manager, campus_id=str(w.campus_a2))
    pool = await new_lead(h, manager)
    ravi = await sign_in(h, "ravi")
    body = {"owner_membership_id": None, "campus_id": str(w.campus_a1), "version": pool["version"]}
    assert (await send(h, "POST", f"{LEADS}/{pool['id']}/assign", ravi, body)).status_code == 403
    assert (await h.client.get(f"{LEADS}/assignees")).status_code == 403
    kiran = await sign_in(h, "kiran")  # Admissions manager restricted to campus A1
    moved = await send(h, "POST", f"{LEADS}/{pool['id']}/assign", kiran, body)
    assert data(moved)["campus"]["id"] == str(w.campus_a1)
    to_a2 = body | {"campus_id": str(w.campus_a2), "version": data(moved)["version"]}
    refused = await send(h, "POST", f"{LEADS}/{pool['id']}/assign", kiran, to_a2)
    assert _errors(refused) == {("campus_id", "campus_not_available")}
    other = await send(
        h,
        "POST",
        f"{LEADS}/{a2_lead['id']}/assign",
        kiran,
        {"owner_membership_id": None, "campus_id": None, "version": a2_lead["version"]},
    )
    assert other.status_code == 404


async def test_the_assignee_list_holds_eligible_members_only(h: Harness) -> None:
    w = h.world
    await sign_in(h, "maya")

    async def names(campus: str | None) -> set[str]:
        params = {"campus_id": campus} if campus else {}
        response = await h.client.get(f"{LEADS}/assignees", params=params)
        return {item["display_name"] for item in data(response)["items"]}

    a1 = await names(str(w.campus_a1))
    assert {"Ravi", "Maya", "Kiran", "Alice"} <= a1
    assert not a1 & {"Sita", "Dave", "Carol"}
    assert "Sita" in await names(str(w.campus_a2))
    pool = await names("none")
    assert {"Ravi", "Sita", "Maya"} <= pool
    assert "Dave" not in pool
    unavailable = await h.client.get(f"{LEADS}/assignees", params={"campus_id": str(w.campus_b1)})
    assert _errors(unavailable) == {("campus_id", "campus_not_available")}
    assert (await h.client.get(f"{LEADS}/assignees", params={"campus_id": "x"})).status_code == 422


# --- Visibility and editing --------------------------------------------------------------------


async def test_campus_restricted_counsellors_see_the_pool_and_their_campus_only(
    h: Harness,
) -> None:
    w = h.world
    manager = await sign_in(h, "maya")
    tag = uuid.uuid7().hex[-6:]
    pool = await new_lead(h, manager, full_name=f"Pool {tag}")
    mumbai = await new_lead(h, manager, full_name=f"Mumbai {tag}", campus_id=str(w.campus_a1))
    pune = await new_lead(h, manager, full_name=f"Pune {tag}", campus_id=str(w.campus_a2))
    csrf = await sign_in(h, "ravi")
    listed = data(await h.client.get(LEADS, params={"q": tag}))
    assert {lead["id"] for lead in listed} == {pool["id"], mumbai["id"]}
    for method, suffix, body in (
        ("GET", "", None),
        ("PATCH", "", {"city": "Pune", "version": 1}),
        ("POST", "/transition", {"to_status": "CONTACTED", "version": 1}),
        ("GET", "/activity", None),
        ("GET", "/follow-ups", None),
        ("POST", "/notes", {"body": "Called"}),
    ):
        response = await send(h, method, f"{LEADS}/{pune['id']}{suffix}", csrf, body)
        assert response.status_code == 404, (method, suffix)
    # The institute pool is open to every campus: Ravi and Sita both work it.
    data(await send(h, "PATCH", f"{LEADS}/{pool['id']}", csrf, {"city": "Alibag", "version": 1}))
    sita = await sign_in(h, "sita")
    updated = data(await h.client.get(f"{LEADS}/{pool['id']}"))
    assert updated["city"] == "Alibag"
    data(await send(h, "PATCH", f"{LEADS}/{pool['id']}", sita, {"city": "Pune", "version": 2}))
    sita_list = data(await h.client.get(LEADS, params={"q": tag, "campus": "none"}))
    assert [lead["id"] for lead in sita_list] == [pool["id"]]


async def test_editing_records_field_names_only(h: Harness) -> None:
    csrf = await sign_in(h, "ravi")
    lead = await new_lead(h, csrf, email=f"arjun.{uuid.uuid7().hex[-6:]}@example.com")
    edited = await send(
        h,
        "PATCH",
        f"{LEADS}/{lead['id']}",
        csrf,
        {"full_name": "Arjun K Nair", "mobile": None, "city": "Kochi", "version": 1},
    )
    lead = data(edited)
    assert (lead["full_name"], lead["mobile"], lead["version"]) == ("Arjun K Nair", None, 2)
    (event,) = await h.audit(edited)
    assert event.metadata == {"changed_fields": ["city", "full_name", "mobile"]}
    activity = (await _activity(h, lead["id"]))[0]
    assert activity == activity | {
        "kind": "UPDATED",
        "details": {"fields": ["city", "full_name", "mobile"]},
    }
    no_contact = await send(
        h, "PATCH", f"{LEADS}/{lead['id']}", csrf, {"email": None, "version": 2}
    )
    assert _errors(no_contact) == {("mobile", "contact_required")}
    for body in ({"campus_id": None, "version": 2}, {"owner": "me", "version": 2}):
        assert (await send(h, "PATCH", f"{LEADS}/{lead['id']}", csrf, body)).status_code == 422
    stale = await send(h, "PATCH", f"{LEADS}/{lead['id']}", csrf, {"city": "Goa", "version": 1})
    assert stale.status_code == 409


async def test_list_filters_and_search(h: Harness) -> None:
    w = h.world
    manager = await sign_in(h, "maya")
    course = await new_course(h, manager, _code())
    tag = uuid.uuid7().hex[-6:]
    ravi = str(w.memberships["ravi_m"])
    mobile = fake_mobile()
    a = await new_lead(h, manager, full_name=f"Kavya {tag}", source="WEBSITE", mobile=mobile)
    b = await new_lead(
        h,
        manager,
        full_name=f"Rohan {tag}",
        email=f"rohan.{tag}@example.com",
        interested_course_id=course["id"],
        campus_id=str(w.campus_a1),
        owner=ravi,
    )
    data(await _move(h, manager, b, "CONTACTED"))

    async def ids(**params: Any) -> list[str]:
        response = await h.client.get(LEADS, params={"q": tag, **params})
        return [lead["id"] for lead in data(response)]

    assert await ids(sort="full_name") == [a["id"], b["id"]]
    assert await ids(status="CONTACTED") == [b["id"]]
    assert set(await ids(status=["NEW", "CONTACTED"])) == {a["id"], b["id"]}
    assert await ids(owner=ravi) == [b["id"]]
    assert await ids(owner="unassigned") == [a["id"]]
    assert await ids(campus="none") == [a["id"]]
    assert await ids(campus=str(w.campus_a1)) == [b["id"]]
    assert await ids(course=course["id"]) == [b["id"]]
    assert await ids(source="WEBSITE") == [a["id"]]
    assert await ids(follow_up="none", sort="full_name") == [a["id"], b["id"]]
    # Search by email prefix and by mobile digits (without the name tag).
    by_email = data(await h.client.get(LEADS, params={"q": f"rohan.{tag}"}))
    assert [lead["id"] for lead in by_email] == [b["id"]]
    digits = mobile.replace(" ", "")[-7:]
    by_mobile = data(await h.client.get(LEADS, params={"q": digits}))
    assert a["id"] in [lead["id"] for lead in by_mobile]
    await sign_in(h, "ravi")
    assert await ids(owner="me") == [b["id"]]
    for bad in ({"owner": "someone"}, {"campus": "x"}, {"status": "ENROLLED"}, {"sort": "mobile"}):
        assert (await h.client.get(LEADS, params=bad)).status_code == 422, bad


async def test_audit_metadata_never_holds_personal_data(h: Harness) -> None:
    csrf = await sign_in(h, "maya")
    secret_name = f"Zubin {uuid.uuid7().hex[-6:]}"
    email = f"zubin.{uuid.uuid7().hex[-6:]}@example.com"
    mobile = fake_mobile()
    lead = await new_lead(h, csrf, full_name=secret_name, email=email, mobile=mobile, city="Thane")
    lead = data(
        await send(
            h,
            "PATCH",
            f"{LEADS}/{lead['id']}",
            csrf,
            {"full_name": secret_name + " K", "version": 1},
        )
    )
    reason = "Private family reason"
    lead = data(await _move(h, csrf, lead, "DEFERRED", reason=reason))
    data(
        await send(
            h,
            "POST",
            f"{LEADS}/{lead['id']}/notes",
            csrf,
            {"body": "Father is a Chief Engineer; call after 6 pm."},
        ),
        201,
    )
    rows = await h.owner(
        "SELECT event_type, metadata::text FROM audit_events WHERE target_id = :t", t=lead["id"]
    )
    assert {row[0] for row in rows} == {"lead.created", "lead.updated", "lead.status_changed"}
    metadata = " ".join(row[1] for row in rows)
    for value in (
        secret_name,
        email,
        mobile,
        mobile.replace(" ", "")[-10:],
        reason,
        "Thane",
        "Chief",
    ):
        assert value not in metadata, value


async def test_a_platform_session_cannot_use_tenant_lead_routes(h: Harness) -> None:
    h.client.cookies.clear()
    # No tenant session at all: authentication is required before anything else.
    assert (await h.client.get(LEADS)).status_code == 401
    assert (await h.client.get(COURSES)).status_code == 401


async def test_a_context_without_tenant_reads_nothing(h: Harness) -> None:
    context = RequestContext(realm=Realm.TENANT, request_id=uuid.uuid7())
    async with context_transaction(h.factory, context) as db:
        count = await db.scalar(text("SELECT count(*) FROM leads"))
    assert count == 0
