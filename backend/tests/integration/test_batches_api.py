"""Batches and student allocation over HTTP (Phase 02-6).

* batch creation rules (active course, own campus, unique code, capacity 1-500,
  dates), edits (course and campus fixed, capacity >= allocations), statuses
  (close, reopen, cancel only when empty);
* the payment gate (decision B): PAID passes; outstanding fees, a missing or
  a cancelled invoice need an override reason, which is recorded with the
  invoice state and outstanding amount and audited;
* allocation → ENROLLED, no duplicate active allocation, course/campus/open/
  capacity rules; transfer keeps history and ENROLLED; withdrawal → ADMITTED;
* Student 360 (current batch, history), campus scope, role permissions;
* concurrency: the last seat, one admission into two batches, transfer racing
  withdrawal.
"""

from collections.abc import AsyncIterator
from typing import Any

import anyio
import pytest
from batches_support import (
    ALLOCATIONS,
    BATCHES,
    admission_status,
    allocate,
    batch,
    client_for,
    new_batch,
    pay_in_full,
    start,
)
from conftest import DatabaseUnderTest
from courses_leads_support import admissions_team, new_course
from finance_support import ITEMS_TOTAL, Billable, admitted, billable, finance_team, issue, pay
from identity_support import Harness, auth_harness
from tenant_admin_support import data, send, sign_in

pytestmark = [pytest.mark.anyio, pytest.mark.integration]
OVERRIDE = "Scholarship letter received; fees due before sea training."


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        await admissions_team(harness)
        await finance_team(harness)
        yield harness


@pytest.fixture
async def a1(h: Harness) -> Billable:
    return await billable(h, h.world.campus_a1)


def errors(response: Any) -> set[tuple[str | None, str]]:
    assert response.status_code == 422, response.text
    return {(d.get("field"), d["code"]) for d in response.json()["error"]["details"]}


def events(rows: list[Any]) -> list[str]:
    return [row.event_type for row in rows]


async def _second_student(h: Harness, a1: Billable, name: str = "Arjun Nair") -> str:
    admission = await admitted(h, course=a1.course, campus=h.world.campus_a1, full_name=name)
    return str(admission["id"])


# --- Batches ------------------------------------------------------------------------------


async def test_create_batch_rules(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "maya")
    created = await send(
        h,
        "POST",
        BATCHES,
        csrf,
        {
            "course_id": a1.course["id"],
            "campus_id": str(h.world.campus_a1),
            "code": " dns-2026-b ",
            "name": "  DNS   Batch 2026-B ",
            "start_date": start(10),
            "end_date": start(375),
            "capacity": 40,
        },
    )
    body = data(created, 201)
    assert (body["code"], body["name"], body["status"]) == (
        "DNS-2026-B",
        "DNS Batch 2026-B",
        "OPEN",
    )
    assert (body["capacity"], body["allocated_count"], body["available_seats"]) == (40, 0, 40)
    assert body["course"]["id"] == a1.course["id"]
    assert body["campus"]["id"] == str(h.world.campus_a1)
    assert events(await h.audit(created)) == ["batch.created"]

    duplicate = await send(
        h,
        "POST",
        BATCHES,
        csrf,
        {
            "course_id": a1.course["id"],
            "campus_id": str(h.world.campus_a1),
            "code": "dns-2026-B",
            "name": "Another",
            "start_date": start(10),
            "end_date": start(20),
            "capacity": 5,
        },
    )
    assert duplicate.status_code == 409

    draft = await new_course(h, csrf, "DRAFTX", activate=False)
    base = {
        "campus_id": str(h.world.campus_a1),
        "name": "Batch",
        "start_date": start(10),
        "end_date": start(20),
        "capacity": 10,
    }
    assert errors(
        await send(h, "POST", BATCHES, csrf, {**base, "course_id": draft["id"], "code": "X1"})
    ) == {("course_id", "course_not_active")}
    assert ("end_date", "invalid_dates") in errors(
        await send(
            h,
            "POST",
            BATCHES,
            csrf,
            {**base, "course_id": a1.course["id"], "code": "X2", "end_date": start(5)},
        )
    )
    for capacity in (0, 501):
        response = await send(
            h,
            "POST",
            BATCHES,
            csrf,
            {**base, "course_id": a1.course["id"], "code": "X3", "capacity": capacity},
        )
        assert response.status_code == 422, capacity

    # Kiran works at A1 only: A2 is not one of his campuses.
    kiran = await sign_in(h, "kiran")
    assert errors(
        await send(
            h,
            "POST",
            BATCHES,
            kiran,
            {
                **base,
                "course_id": a1.course["id"],
                "code": "X4",
                "campus_id": str(h.world.campus_a2),
            },
        )
    ) == {("campus_id", "campus_not_available")}
    # Counsellors and finance roles only read batches.
    for user in ("ravi", "farah"):
        other = await sign_in(h, user)
        response = await send(
            h, "POST", BATCHES, other, {**base, "course_id": a1.course["id"], "code": "X5"}
        )
        assert response.status_code == 403, user


async def test_edit_and_status_rules(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "maya")
    created = await new_batch(h, csrf, a1.course["id"], h.world.campus_a1, capacity=2)
    path = f"{BATCHES}/{created['id']}"

    # Course and campus never change (unknown fields are refused).
    moved = await send(
        h, "PATCH", path, csrf, {"campus_id": str(h.world.campus_a2), "version": created["version"]}
    )
    assert moved.status_code == 422
    edited = await send(
        h, "PATCH", path, csrf, {"name": "DNS 2026-B (morning)", "capacity": 3, "version": 1}
    )
    edited_body = data(edited)
    assert (edited_body["name"], edited_body["capacity"]) == ("DNS 2026-B (morning)", 3)
    assert events(await h.audit(edited)) == ["batch.updated"]
    assert (await send(h, "PATCH", path, csrf, {"name": "Stale", "version": 1})).status_code == 409

    # Capacity cannot drop below the active allocations.
    data(await allocate(h, csrf, created["id"], a1.admission_id, OVERRIDE), 201)
    second = await _second_student(h, a1)
    csrf = await sign_in(h, "maya")
    data(await allocate(h, csrf, created["id"], second, OVERRIDE), 201)
    current = await batch(h, created["id"])
    assert errors(
        await send(h, "PATCH", path, csrf, {"capacity": 1, "version": current["version"]})
    ) == {("capacity", "capacity_below_allocated")}

    # Close and reopen; cancel only when empty; nothing moves a cancelled batch.
    status = f"{path}/status"
    closed = data(
        await send(h, "POST", status, csrf, {"status": "CLOSED", "version": current["version"]})
    )
    assert closed["status"] == "CLOSED"
    reopened = data(
        await send(h, "POST", status, csrf, {"status": "OPEN", "version": closed["version"]})
    )
    assert reopened["status"] == "OPEN"
    assert errors(
        await send(h, "POST", status, csrf, {"status": "CANCELLED", "version": reopened["version"]})
    ) == {("status", "batch_has_allocations")}

    empty = await new_batch(h, csrf, a1.course["id"], h.world.campus_a1)
    cancelled = await send(
        h,
        "POST",
        f"{BATCHES}/{empty['id']}/status",
        csrf,
        {"status": "CANCELLED", "reason": "Not enough enrolments", "version": empty["version"]},
    )
    cancelled_body = data(cancelled)
    assert cancelled_body["status"] == "CANCELLED"
    assert cancelled_body["status_reason"] == "Not enough enrolments"
    assert events(await h.audit(cancelled)) == ["batch.status_changed"]
    assert errors(
        await send(
            h,
            "POST",
            f"{BATCHES}/{empty['id']}/status",
            csrf,
            {"status": "OPEN", "version": cancelled_body["version"]},
        )
    ) == {("status", "invalid_transition")}
    assert errors(
        await send(
            h,
            "PATCH",
            f"{BATCHES}/{empty['id']}",
            csrf,
            {"name": "Revived", "version": cancelled_body["version"]},
        )
    ) == {("status", "batch_cancelled")}


async def test_batch_list_filters_and_seats(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "maya")
    small = await new_batch(
        h, csrf, a1.course["id"], h.world.campus_a1, capacity=1, code="DNS-SMALL"
    )
    big = await new_batch(h, csrf, a1.course["id"], h.world.campus_a2, capacity=30, code="DNS-BIG")
    data(await allocate(h, csrf, small["id"], a1.admission_id, OVERRIDE), 201)

    def ids(response: Any) -> set[str]:
        return {item["id"] for item in data(response)}

    assert ids(await h.client.get(BATCHES, params={"q": "dns-small"})) == {small["id"]}
    assert ids(await h.client.get(BATCHES, params={"campus_id": str(h.world.campus_a2)})) == {
        big["id"]
    }
    assert ids(await h.client.get(BATCHES, params={"has_seats": "false"})) == {small["id"]}
    assert big["id"] in ids(await h.client.get(BATCHES, params={"has_seats": "true"}))
    assert ids(
        await h.client.get(BATCHES, params={"course_id": a1.course["id"], "status": "OPEN"})
    ) == {small["id"], big["id"]}
    full = await batch(h, small["id"])
    assert (full["allocated_count"], full["available_seats"]) == (1, 0)


# --- Allocation and the payment gate -----------------------------------------------------


async def test_allocation_needs_paid_fees_or_a_recorded_override(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "maya")
    target = await new_batch(h, csrf, a1.course["id"], h.world.campus_a1)

    # No invoice at all: never treated as paid.
    eligible = data(await h.client.get(f"{BATCHES}/{target['id']}/eligible-admissions"))
    assert [(e["admission_id"], e["invoice_state"], e["payment_cleared"]) for e in eligible] == [
        (a1.admission_id, "NO_INVOICE", False)
    ]
    assert errors(await allocate(h, csrf, target["id"], a1.admission_id)) == {
        ("override_reason", "payment_required")
    }
    assert errors(await allocate(h, csrf, target["id"], a1.admission_id, "   ")) == {
        ("override_reason", "payment_required")
    }
    assert await admission_status(h, a1.admission_id) == "ADMITTED"

    # A partly paid invoice: the override records the outstanding amount.
    fiona = await sign_in(h, "fiona")
    invoice = data(await issue(h, fiona, a1.admission_id), 201)
    data(await pay(h, fiona, invoice["id"], 10_000_000), 201)
    csrf = await sign_in(h, "maya")
    response = await allocate(h, csrf, target["id"], a1.admission_id, OVERRIDE)
    allocation = data(response, 201)
    assert allocation["status"] == "ACTIVE"
    assert allocation["payment_basis"] == "OVERRIDE"
    assert allocation["payment_override"] == {
        "reason": OVERRIDE,
        "invoice_state": "PARTIALLY_PAID",
        "outstanding_minor": ITEMS_TOTAL - 10_000_000,
    }
    assert allocation["allocated_by"]["display_name"]
    assert events(await h.audit(response)) == [
        "batch.student_allocated",
        "batch.payment_overridden",
    ]
    assert await admission_status(h, a1.admission_id) == "ENROLLED"
    assert (await batch(h, target["id"]))["allocated_count"] == 1
    # The override's free text never reaches the audit log.
    audit_text = str([row.metadata for row in await h.audit(response)])
    assert "Scholarship" not in audit_text

    # No duplicate active allocation, in the same or another batch.
    other = await new_batch(h, csrf, a1.course["id"], h.world.campus_a1)
    assert ("admission_id", "already_allocated") in errors(
        await allocate(h, csrf, other["id"], a1.admission_id, OVERRIDE)
    )
    assert data(await h.client.get(f"{BATCHES}/{other['id']}/eligible-admissions")) == []


async def test_paid_and_cancelled_invoices(h: Harness, a1: Billable) -> None:
    await pay_in_full(h, a1.admission_id)
    csrf = await sign_in(h, "maya")
    target = await new_batch(h, csrf, a1.course["id"], h.world.campus_a1)
    eligible = data(await h.client.get(f"{BATCHES}/{target['id']}/eligible-admissions"))
    assert [
        (e["invoice_state"], e["payment_cleared"], e["outstanding_minor"]) for e in eligible
    ] == [("PAID", True, 0)]
    response = await allocate(h, csrf, target["id"], a1.admission_id)
    paid = data(response, 201)
    assert (paid["payment_basis"], paid["payment_override"]) == ("PAID", None)
    assert events(await h.audit(response)) == ["batch.student_allocated"]

    # A cancelled invoice is not a paid one.
    second = await _second_student(h, a1, "Meera Pillai")
    fiona = await sign_in(h, "fiona")
    invoice = data(await issue(h, fiona, second), 201)
    data(
        await send(
            h,
            "POST",
            f"/api/v1/invoices/{invoice['id']}/cancel",
            fiona,
            {"reason": "Issued with the wrong fee heads", "version": invoice["version"]},
        )
    )
    csrf = await sign_in(h, "maya")
    assert errors(await allocate(h, csrf, target["id"], second)) == {
        ("override_reason", "payment_required")
    }
    overridden = data(await allocate(h, csrf, target["id"], second, OVERRIDE), 201)
    assert overridden["payment_override"]["invoice_state"] == "NO_INVOICE"
    assert overridden["payment_override"]["outstanding_minor"] is None


async def test_allocation_course_campus_status_and_capacity(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "maya")
    other_course = await new_course(h, csrf, "GME")
    wrong_course = await new_batch(h, csrf, other_course["id"], h.world.campus_a1)
    wrong_campus = await new_batch(h, csrf, a1.course["id"], h.world.campus_a2)
    assert ("admission_id", "course_mismatch") in errors(
        await allocate(h, csrf, wrong_course["id"], a1.admission_id, OVERRIDE)
    )
    assert ("admission_id", "campus_mismatch") in errors(
        await allocate(h, csrf, wrong_campus["id"], a1.admission_id, OVERRIDE)
    )
    closed = await new_batch(h, csrf, a1.course["id"], h.world.campus_a1)
    data(
        await send(
            h,
            "POST",
            f"{BATCHES}/{closed['id']}/status",
            csrf,
            {"status": "CLOSED", "version": closed["version"]},
        )
    )
    assert errors(await allocate(h, csrf, closed["id"], a1.admission_id, OVERRIDE)) == {
        ("batch_id", "batch_not_open")
    }
    one_seat = await new_batch(h, csrf, a1.course["id"], h.world.campus_a1, capacity=1)
    data(await allocate(h, csrf, one_seat["id"], a1.admission_id, OVERRIDE), 201)
    second = await _second_student(h, a1)
    csrf = await sign_in(h, "maya")
    assert errors(await allocate(h, csrf, one_seat["id"], second, OVERRIDE)) == {
        ("batch_id", "batch_full")
    }
    # An unknown admission gets the answer of one the caller may not use.
    assert errors(
        await allocate(h, csrf, one_seat["id"], "01a00000-0000-7000-8000-000000000000", OVERRIDE)
    ) == {("admission_id", "admission_not_available")}


# --- Transfer and withdrawal -------------------------------------------------------------


async def test_transfer_keeps_history_and_enrolment(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "maya")
    source = await new_batch(h, csrf, a1.course["id"], h.world.campus_a1, code="DNS-A")
    target = await new_batch(h, csrf, a1.course["id"], h.world.campus_a1, code="DNS-B")
    first = data(await allocate(h, csrf, source["id"], a1.admission_id, OVERRIDE), 201)
    path = f"{ALLOCATIONS}/{first['id']}/transfer"

    assert errors(
        await send(
            h, "POST", path, csrf, {"target_batch_id": source["id"], "reason": "x", "version": 1}
        )
    ) == {("target_batch_id", "same_batch")}
    assert (
        await send(h, "POST", path, csrf, {"target_batch_id": target["id"], "version": 1})
    ).status_code == 422  # a reason is mandatory
    other_course = await new_course(h, csrf, "GMEX")
    elsewhere = await new_batch(h, csrf, other_course["id"], h.world.campus_a1)
    assert ("target_batch_id", "course_mismatch") in errors(
        await send(
            h,
            "POST",
            path,
            csrf,
            {"target_batch_id": elsewhere["id"], "reason": "Timing", "version": 1},
        )
    )

    response = await send(
        h,
        "POST",
        path,
        csrf,
        {"target_batch_id": target["id"], "reason": "Prefers the evening batch", "version": 1},
    )
    moved = data(response)
    assert (moved["batch"]["id"], moved["status"], moved["payment_basis"]) == (
        target["id"],
        "ACTIVE",
        "TRANSFER",
    )
    assert moved["transferred_from_id"] == first["id"]
    assert moved["transferred_from_batch_code"] == "DNS-A"
    assert events(await h.audit(response)) == ["batch.student_transferred"]
    assert await admission_status(h, a1.admission_id) == "ENROLLED"
    assert (await batch(h, source["id"]))["allocated_count"] == 0
    assert (await batch(h, target["id"]))["allocated_count"] == 1

    history = data(await h.client.get(ALLOCATIONS, params={"student_id": a1.student_id}))
    by_id = {item["id"]: item for item in history}
    ended = by_id[first["id"]]
    assert (ended["status"], ended["end_reason"], ended["end_note"]) == (
        "ENDED",
        "TRANSFERRED",
        "Prefers the evening batch",
    )
    assert ended["transferred_to_batch_code"] == "DNS-B"
    assert ended["payment_override"]["reason"] == OVERRIDE  # the override stays on record
    # The ended allocation cannot be transferred again (stale).
    assert (
        await send(
            h,
            "POST",
            path,
            csrf,
            {"target_batch_id": target["id"], "reason": "Again", "version": 1},
        )
    ).status_code == 409


async def test_withdrawal_returns_the_admission_to_admitted(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "maya")
    target = await new_batch(h, csrf, a1.course["id"], h.world.campus_a1)
    first = data(await allocate(h, csrf, target["id"], a1.admission_id, OVERRIDE), 201)
    path = f"{ALLOCATIONS}/{first['id']}/withdraw"
    assert (
        await send(h, "POST", path, csrf, {"reason": "Medical", "version": 7})
    ).status_code == 409
    assert errors(await send(h, "POST", path, csrf, {"reason": "  ", "version": 1})) == {
        ("reason", "reason_required")
    }
    response = await send(h, "POST", path, csrf, {"reason": "Failed the medical", "version": 1})
    withdrawn = data(response)
    assert (withdrawn["status"], withdrawn["end_reason"]) == ("ENDED", "WITHDRAWN")
    assert withdrawn["ended_by"]["display_name"]
    assert events(await h.audit(response)) == ["batch.student_withdrawn"]
    assert await admission_status(h, a1.admission_id) == "ADMITTED"
    assert (await batch(h, target["id"]))["allocated_count"] == 0
    # History is kept, and the student may be allocated again.
    again = data(await allocate(h, csrf, target["id"], a1.admission_id, OVERRIDE), 201)
    rows = data(await h.client.get(f"{BATCHES}/{target['id']}/allocations"))
    assert [row["id"] for row in rows] == [again["id"], first["id"]]
    assert (
        data(
            await h.client.get(f"{BATCHES}/{target['id']}/allocations", params={"status": "ENDED"})
        )[0]["id"]
        == first["id"]
    )
    count = await h.owner(
        "SELECT count(*) FROM batch_allocations WHERE admission_id = :a", a=a1.admission_id
    )
    assert count[0][0] == 2


# --- Student 360, history and scope ------------------------------------------------------


async def test_student_360_shows_the_batch_and_its_history(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "maya")
    source = await new_batch(h, csrf, a1.course["id"], h.world.campus_a1, code="DNS-360A")
    target = await new_batch(h, csrf, a1.course["id"], h.world.campus_a1, code="DNS-360B")
    first = data(await allocate(h, csrf, source["id"], a1.admission_id, OVERRIDE), 201)
    data(
        await send(
            h,
            "POST",
            f"{ALLOCATIONS}/{first['id']}/transfer",
            csrf,
            {"target_batch_id": target["id"], "reason": "Timing", "version": 1},
        )
    )
    student = data(await h.client.get(f"/api/v1/students/{a1.student_id}"))
    admission = student["admissions"][0]
    assert admission["status"] == "ENROLLED"
    assert admission["current_batch"]["code"] == "DNS-360B"
    timeline = data(await h.client.get(f"/api/v1/students/{a1.student_id}/activity"))
    batch_kinds = [entry["kind"] for entry in timeline if entry["source"] == "batch"]
    assert batch_kinds == ["TRANSFERRED_IN", "ALLOCATED"]
    batch_activity = data(await h.client.get(f"{BATCHES}/{source['id']}/activity"))
    assert [entry["kind"] for entry in batch_activity] == [
        "TRANSFERRED_OUT",
        "ALLOCATED",
        "CREATED",
    ]

    # A finance officer at A1 reads batches (and the current batch) but cannot allocate.
    farah = await sign_in(h, "farah")
    assert (
        data(await h.client.get(f"/api/v1/students/{a1.student_id}"))["admissions"][0][
            "current_batch"
        ]["code"]
        == "DNS-360B"
    )
    assert (await h.client.get(f"{BATCHES}/{target['id']}/eligible-admissions")).status_code == 403
    assert (await allocate(h, farah, target["id"], a1.admission_id, OVERRIDE)).status_code == 403


async def test_campus_scope(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "maya")
    at_a1 = await new_batch(h, csrf, a1.course["id"], h.world.campus_a1)
    at_a2 = await new_batch(h, csrf, a1.course["id"], h.world.campus_a2)
    allocation = data(await allocate(h, csrf, at_a1["id"], a1.admission_id, OVERRIDE), 201)

    # Sita (counsellor, A2 only) sees A2's batch and nothing of A1's.
    sita = await sign_in(h, "sita")
    listed = {item["id"] for item in data(await h.client.get(BATCHES))}
    assert at_a2["id"] in listed
    assert at_a1["id"] not in listed
    for path in (f"{BATCHES}/{at_a1['id']}", f"{BATCHES}/{at_a1['id']}/allocations"):
        assert (await h.client.get(path)).status_code == 404, path
    assert data(await h.client.get(ALLOCATIONS)) == []
    # Counsellors read only.
    assert (
        await send(
            h,
            "POST",
            f"{BATCHES}/{at_a2['id']}/status",
            sita,
            {"status": "CLOSED", "version": 1},
        )
    ).status_code == 403

    # Kiran (A1 admissions manager) cannot touch A2's batch: 404, not 403.
    kiran = await sign_in(h, "kiran")
    for method, path, body in (
        ("PATCH", f"{BATCHES}/{at_a2['id']}", {"name": "Mine now", "version": 1}),
        ("POST", f"{BATCHES}/{at_a2['id']}/status", {"status": "CLOSED", "version": 1}),
    ):
        assert (await send(h, method, path, kiran, body)).status_code == 404, path
    # Transferring A1's student into A2 is refused (another campus).
    response = await send(
        h,
        "POST",
        f"{ALLOCATIONS}/{allocation['id']}/transfer",
        kiran,
        {"target_batch_id": at_a2["id"], "reason": "Move", "version": 1},
    )
    assert errors(response) == {("target_batch_id", "target_not_available")}


# --- Concurrency -------------------------------------------------------------------------


async def test_two_users_racing_for_the_last_seat(h: Harness, a1: Billable) -> None:
    second = await _second_student(h, a1)
    csrf = await sign_in(h, "maya")
    one_seat = await new_batch(h, csrf, a1.course["id"], h.world.campus_a1, capacity=1)
    results: list[Any] = []
    path = f"{BATCHES}/{one_seat['id']}/allocations"
    async with (
        client_for(h, "maya") as (maya, maya_csrf),
        client_for(h, "alice") as (alice, alice_csrf),
    ):

        async def run(client: Any, token: str, admission: str) -> None:
            results.append(
                await client.post(
                    path,
                    json={"admission_id": admission, "override_reason": OVERRIDE},
                    headers={"X-CSRF-Token": token},
                )
            )

        async with anyio.create_task_group() as group:
            group.start_soon(run, maya, maya_csrf, a1.admission_id)
            group.start_soon(run, alice, alice_csrf, second)
    assert sorted(r.status_code for r in results) == [201, 422], [r.text for r in results]
    loser = next(r for r in results if r.status_code == 422)
    assert loser.json()["error"]["details"][0]["code"] == "batch_full"
    assert (await batch(h, one_seat["id"]))["allocated_count"] == 1
    statuses = sorted(
        [await admission_status(h, a1.admission_id), await admission_status(h, second)]
    )
    assert statuses == ["ADMITTED", "ENROLLED"]


async def test_one_admission_into_two_batches_at_once(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "maya")
    first = await new_batch(h, csrf, a1.course["id"], h.world.campus_a1)
    other = await new_batch(h, csrf, a1.course["id"], h.world.campus_a1)
    results: list[Any] = []
    async with (
        client_for(h, "maya") as (maya, maya_csrf),
        client_for(h, "alice") as (alice, alice_csrf),
    ):

        async def run(client: Any, token: str, batch_id: str) -> None:
            results.append(
                await client.post(
                    f"{BATCHES}/{batch_id}/allocations",
                    json={"admission_id": a1.admission_id, "override_reason": OVERRIDE},
                    headers={"X-CSRF-Token": token},
                )
            )

        async with anyio.create_task_group() as group:
            group.start_soon(run, maya, maya_csrf, first["id"])
            group.start_soon(run, alice, alice_csrf, other["id"])
    codes = sorted(r.status_code for r in results)
    assert codes[0] == 201, [r.text for r in results]
    assert codes[1] in (409, 422), [r.text for r in results]
    active = await h.owner(
        "SELECT count(*) FROM batch_allocations WHERE admission_id = :a AND status = 'ACTIVE'",
        a=a1.admission_id,
    )
    assert active[0][0] == 1
    total = (await batch(h, first["id"]))["allocated_count"] + (await batch(h, other["id"]))[
        "allocated_count"
    ]
    assert total == 1


async def test_transfer_racing_withdrawal(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "maya")
    source = await new_batch(h, csrf, a1.course["id"], h.world.campus_a1)
    target = await new_batch(h, csrf, a1.course["id"], h.world.campus_a1)
    allocation = data(await allocate(h, csrf, source["id"], a1.admission_id, OVERRIDE), 201)
    results: dict[str, Any] = {}
    async with (
        client_for(h, "maya") as (maya, maya_csrf),
        client_for(h, "alice") as (alice, alice_csrf),
    ):

        async def transfer() -> None:
            results["transfer"] = await maya.post(
                f"{ALLOCATIONS}/{allocation['id']}/transfer",
                json={"target_batch_id": target["id"], "reason": "Timing", "version": 1},
                headers={"X-CSRF-Token": maya_csrf},
            )

        async def withdraw() -> None:
            results["withdraw"] = await alice.post(
                f"{ALLOCATIONS}/{allocation['id']}/withdraw",
                json={"reason": "Left the institute", "version": 1},
                headers={"X-CSRF-Token": alice_csrf},
            )

        async with anyio.create_task_group() as group:
            group.start_soon(transfer)
            group.start_soon(withdraw)
    codes = {name: response.status_code for name, response in results.items()}
    assert sorted(codes.values()) == [200, 409], codes
    counts = (
        (await batch(h, source["id"]))["allocated_count"],
        (await batch(h, target["id"]))["allocated_count"],
    )
    status = await admission_status(h, a1.admission_id)
    if codes["transfer"] == 200:
        assert (counts, status) == ((0, 1), "ENROLLED")
    else:
        assert (counts, status) == ((0, 0), "ADMITTED")
