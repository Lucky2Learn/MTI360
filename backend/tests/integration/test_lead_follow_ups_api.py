"""Follow-ups, notes and the lead timeline over HTTP (Phase 02-1; blueprint §11-§13).

* follow-ups: schedule (default assignee), reschedule, complete, cancel;
  closed ones are immutable; overdue and the next follow-up are derived and
  drive the list filters;
* notes are append-only plain text; the timeline is newest first with actor
  names; follow-ups and notes are activity only, never audit events;
* the end-to-end flow leaves an INTERESTED lead with everything 02-2 prefills.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from conftest import DatabaseUnderTest
from courses_leads_support import FOLLOW_UPS, LEADS, admissions_team, new_course, new_lead
from identity_support import Harness, auth_harness
from tenant_admin_support import data, send, sign_in

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        await admissions_team(harness)
        yield harness


def _at(delta: timedelta) -> str:
    return (datetime.now(UTC) + delta).isoformat()


async def _schedule(h: Harness, csrf: str, lead_id: str, delta: timedelta, **extra: Any) -> Any:
    body = {"due_at": _at(delta), "kind": "CALL", **extra}
    return await send(h, "POST", f"{LEADS}/{lead_id}/follow-ups", csrf, body)


def _errors(response: Any) -> set[tuple[str, str]]:
    assert response.status_code == 422, response.text
    return {(d["field"], d["code"]) for d in response.json()["error"]["details"]}


async def test_follow_ups_are_scheduled_completed_and_cancelled(h: Harness) -> None:
    w = h.world
    manager = await sign_in(h, "maya")
    lead = await new_lead(
        h, manager, campus_id=str(w.campus_a1), owner=str(w.memberships["ravi_m"])
    )
    csrf = await sign_in(h, "ravi")
    scheduled = await _schedule(
        h, csrf, lead["id"], timedelta(days=2), note="Discuss DNS sponsorship"
    )
    later = data(scheduled, 201)
    assert later["assignee"]["display_name"] == "Ravi"  # the lead owner by default
    assert (later["status"], later["overdue"], later["version"]) == ("OPEN", False, 1)
    assert await h.audit(scheduled) == []  # activity only
    overdue = data(await _schedule(h, csrf, lead["id"], -timedelta(hours=2), kind="VISIT"), 201)
    assert overdue["overdue"] is True
    items = data(await h.client.get(f"{LEADS}/{lead['id']}/follow-ups"))["items"]
    assert [i["id"] for i in items] == [overdue["id"], later["id"]]  # due date order
    detail = data(await h.client.get(f"{LEADS}/{lead['id']}"))
    assert detail["overdue_follow_ups"] == 1
    assert detail["next_follow_up_at"] == items[0]["due_at"]

    moved = data(
        await send(
            h,
            "PATCH",
            f"{FOLLOW_UPS}/{later['id']}",
            csrf,
            {"due_at": _at(timedelta(days=3)), "kind": "WHATSAPP", "version": 1},
        )
    )
    assert (moved["kind"], moved["version"]) == ("WHATSAPP", 2)
    done = await send(
        h,
        "POST",
        f"{FOLLOW_UPS}/{overdue['id']}/complete",
        csrf,
        {"outcome": "Visited the campus with parents.", "version": 1},
    )
    completed = data(done)
    assert (completed["status"], completed["completed_by"]) == ("DONE", {"display_name": "Ravi"})
    assert completed["outcome"] == "Visited the campus with parents."
    assert await h.audit(done) == []
    cancelled = data(
        await send(h, "POST", f"{FOLLOW_UPS}/{moved['id']}/cancel", csrf, {"version": 2})
    )
    assert (cancelled["status"], cancelled["outcome"]) == ("CANCELLED", None)
    # Closed follow-ups never change again.
    for method, suffix, body in (
        ("PATCH", "", {"kind": "CALL", "version": 2}),
        ("POST", "/complete", {"version": 2}),
        ("POST", "/cancel", {"version": 2}),
    ):
        response = await send(h, method, f"{FOLLOW_UPS}/{completed['id']}{suffix}", csrf, body)
        assert _errors(response) == {("status", "follow_up_closed")}, (method, suffix)
    open_only = data(
        await h.client.get(f"{LEADS}/{lead['id']}/follow-ups", params={"status": "OPEN"})
    )
    assert open_only["items"] == []
    kinds = [a["kind"] for a in data(await h.client.get(f"{LEADS}/{lead['id']}/activity"))]
    assert kinds[:5] == [
        "FOLLOW_UP_CANCELLED",
        "FOLLOW_UP_COMPLETED",
        "FOLLOW_UP_SCHEDULED",
        "FOLLOW_UP_SCHEDULED",
        "FOLLOW_UP_SCHEDULED",
    ]


async def test_follow_up_validation_and_locking(h: Harness) -> None:
    w = h.world
    csrf = await sign_in(h, "ravi")
    lead = await new_lead(h, csrf, campus_id=str(w.campus_a1))
    assert _errors(await _schedule(h, csrf, lead["id"], -timedelta(days=2))) == {
        ("due_at", "out_of_range")
    }
    assert _errors(await _schedule(h, csrf, lead["id"], timedelta(days=400))) == {
        ("due_at", "out_of_range")
    }
    naive = await send(
        h,
        "POST",
        f"{LEADS}/{lead['id']}/follow-ups",
        csrf,
        {"due_at": "2026-12-01T10:00:00", "kind": "CALL"},
    )
    assert _errors(naive) == {("due_at", "timezone_required")}
    sita = str(w.memberships["sita_m"])  # campus A2 only: not eligible for an A1 lead
    assert _errors(
        await _schedule(h, csrf, lead["id"], timedelta(days=1), assignee_membership_id=sita)
    ) == {("assignee_membership_id", "owner_not_eligible")}
    item = data(await _schedule(h, csrf, lead["id"], timedelta(days=1)), 201)
    assert item["assignee"]["display_name"] == "Ravi"  # no owner: the creator
    stale = await send(h, "PATCH", f"{FOLLOW_UPS}/{item['id']}", csrf, {"note": "x", "version": 9})
    assert stale.status_code == 409
    stale_done = await send(h, "POST", f"{FOLLOW_UPS}/{item['id']}/complete", csrf, {"version": 9})
    assert stale_done.status_code == 409
    assert (await send(h, "DELETE", f"{FOLLOW_UPS}/{item['id']}", csrf)).status_code == 405


async def test_follow_up_state_filters_the_lead_list(h: Harness) -> None:
    csrf = await sign_in(h, "maya")
    tag = uuid.uuid7().hex[-6:]
    overdue = await new_lead(h, csrf, full_name=f"Overdue {tag}")
    today = await new_lead(h, csrf, full_name=f"Today {tag}")
    upcoming = await new_lead(h, csrf, full_name=f"Upcoming {tag}")
    nothing = await new_lead(h, csrf, full_name=f"Nothing {tag}")
    data(await _schedule(h, csrf, overdue["id"], -timedelta(minutes=30)), 201)
    data(await _schedule(h, csrf, today["id"], timedelta(minutes=1)), 201)
    data(await _schedule(h, csrf, upcoming["id"], timedelta(days=3)), 201)

    async def ids(state: str) -> set[str]:
        params: dict[str, str | int] = {"q": tag, "follow_up": state, "utc_offset": 0}
        return {lead["id"] for lead in data(await h.client.get(LEADS, params=params))}

    assert await ids("overdue") == {overdue["id"]}
    assert today["id"] in await ids("today")
    assert upcoming["id"] in await ids("upcoming")
    assert await ids("none") == {nothing["id"]}
    listed = data(await h.client.get(LEADS, params={"q": tag, "sort": "next_follow_up_at"}))
    assert [lead["id"] for lead in listed] == [
        overdue["id"],
        today["id"],
        upcoming["id"],
        nothing["id"],  # no follow-up: last
    ]
    assert listed[0]["overdue_follow_ups"] == 1
    bad = await h.client.get(LEADS, params={"follow_up": "soon"})
    assert bad.status_code == 422
    assert (await h.client.get(LEADS, params={"utc_offset": 900})).status_code == 422


async def test_notes_are_append_only_plain_text(h: Harness) -> None:
    csrf = await sign_in(h, "ravi")
    lead = await new_lead(h, csrf)
    body = "<script>alert('x')</script> Father asked about **DNS** fees."
    added = await send(h, "POST", f"{LEADS}/{lead['id']}/notes", csrf, {"body": f"  {body}  "})
    note = data(added, 201)
    assert (note["kind"], note["body"], note["actor"]) == ("NOTE", body, {"display_name": "Ravi"})
    assert await h.audit(added) == []
    for bad in ("", " " * 5, "x" * 4001):
        response = await send(h, "POST", f"{LEADS}/{lead['id']}/notes", csrf, {"body": bad})
        assert response.status_code == 422, len(bad)
    # No route edits or deletes a note.
    for method in ("PATCH", "PUT", "DELETE"):
        response = await send(h, method, f"{LEADS}/{lead['id']}/notes", csrf, {"body": "x"})
        assert response.status_code == 405, method
    timeline = await h.client.get(f"{LEADS}/{lead['id']}/activity", params={"limit": 1})
    page = timeline.json()
    assert [a["kind"] for a in page["data"]] == ["NOTE"]  # newest first
    assert page["meta"]["page"]["total"] == 2
    older = await h.client.get(f"{LEADS}/{lead['id']}/activity", params={"limit": 1, "offset": 1})
    assert [a["kind"] for a in data(older)] == ["CREATED"]


async def test_a_lead_becomes_ready_to_apply_with_every_prefill_field(h: Harness) -> None:
    w = h.world
    manager = await sign_in(h, "maya")
    course = await new_course(h, manager, f"DNS{uuid.uuid7().hex[-5:]}".upper(), name="DNS")
    lead = await new_lead(
        h,
        manager,
        full_name="Kavya Menon",
        email=f"kavya.{uuid.uuid7().hex[-6:]}@example.com",
        date_of_birth="2007-03-02",
        city="Kochi",
        highest_qualification="12th PCM, 81%",
        interested_course_id=course["id"],
        source="WEBSITE",
    )
    lead = data(
        await send(
            h,
            "POST",
            f"{LEADS}/{lead['id']}/assign",
            manager,
            {
                "owner_membership_id": str(w.memberships["ravi_m"]),
                "campus_id": str(w.campus_a1),
                "version": lead["version"],
            },
        )
    )
    csrf = await sign_in(h, "ravi")
    data(await _schedule(h, csrf, lead["id"], timedelta(days=1)), 201)
    data(await send(h, "POST", f"{LEADS}/{lead['id']}/notes", csrf, {"body": "Keen on DNS."}), 201)
    for status in ("CONTACTED", "QUALIFIED", "COUNSELLING", "INTERESTED"):
        lead = data(
            await send(
                h,
                "POST",
                f"{LEADS}/{lead['id']}/transition",
                csrf,
                {"to_status": status, "version": lead["version"]},
            )
        )
    assert lead["status"] == "INTERESTED"
    prefill = {
        key: lead[key]
        for key in ("full_name", "email", "date_of_birth", "city", "highest_qualification")
    }
    assert all(prefill.values())
    assert lead["interested_course"]["id"] == course["id"]
    assert lead["campus"]["id"] == str(w.campus_a1)
    assert lead["owner"]["membership_id"] == str(w.memberships["ravi_m"])
    kinds = [a["kind"] for a in data(await h.client.get(f"{LEADS}/{lead['id']}/activity"))]
    assert kinds == [
        "STATUS_CHANGED",
        "STATUS_CHANGED",
        "STATUS_CHANGED",
        "STATUS_CHANGED",
        "NOTE",
        "FOLLOW_UP_SCHEDULED",
        "ASSIGNED",
        "CREATED",
    ]
