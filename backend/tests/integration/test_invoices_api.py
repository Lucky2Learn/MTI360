"""Fee invoices, payments and receipts over HTTP (Phase 02-5; ADR-0022, addendum R1-R3).

* issue a non-tax fee invoice from the course's active fee structure (FY
  numbers), with recorded adjustments; one live invoice per admission;
  cancellation only without pending or confirmed payments;
* cash, UPI and bank transfer are confirmed with a receipt; cheques and
  demand drafts are PENDING until confirmed (receipt) or failed (reason);
* reversal restores the balance, keeps the receipt (cancelled) and is never
  done by the recorder (422 ``recorder_cannot_reverse``; ``recorded_by_me``);
* idempotency keys in the body: replays answer 200 with the original and no
  side effects, a different payload is 409, concurrent duplicates make one row;
* campus scope, permissions, the summary, gap-free numbers and the
  ``paid_minor`` invariant; audit metadata free of names and references.
"""

import re
from collections.abc import AsyncIterator
from typing import Any

import anyio
import pytest
from conftest import DatabaseUnderTest
from courses_leads_support import admissions_team
from finance_support import (
    INVOICES,
    ITEMS,
    ITEMS_TOTAL,
    PAYMENTS,
    SUMMARY,
    Billable,
    billable,
    due_in,
    errors,
    finance_team,
    issue,
    key,
    paid_matches_confirmed,
    pay,
    today_ist,
)
from identity_support import Harness, auth_harness
from tenant_admin_support import data, send, sign_in

from app.core.sequences import financial_year_label, financial_year_start

pytestmark = [pytest.mark.anyio, pytest.mark.integration]
TUITION, HOSTEL, UNIFORM = (item["amount_minor"] for item in ITEMS)


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        await admissions_team(harness)
        await finance_team(harness)
        yield harness


@pytest.fixture
async def a1(h: Harness) -> Billable:
    return await billable(h, h.world.campus_a1)


def _label() -> str:
    return financial_year_label(financial_year_start(today_ist()))


async def _invoice(h: Harness, invoice_id: str) -> dict[str, Any]:
    return data(await h.client.get(f"{INVOICES}/{invoice_id}"))  # type: ignore[no-any-return]


async def _act(h: Harness, csrf: str, payment: dict[str, Any], action: str, **body: Any) -> Any:
    return await send(
        h,
        "POST",
        f"{PAYMENTS}/{payment['id']}/{action}",
        csrf,
        {"version": payment["version"], **body},
    )


def _audit_values(events: list[Any]) -> str:
    return " ".join(str(value) for event in events for value in event.metadata.values())


async def test_an_officer_issues_a_fee_invoice_from_the_active_structure(
    h: Harness, a1: Billable
) -> None:
    csrf = await sign_in(h, "farah")  # Finance officer, campus A1
    issued = await issue(h, csrf, a1.admission_id)
    invoice = data(issued, 201)
    assert re.fullmatch(rf"INV-{_label()}-\d{{5}}", invoice["number"])
    assert (invoice["status"], invoice["currency"], invoice["adjusted"]) == ("ISSUED", "INR", False)
    assert (invoice["total_minor"], invoice["paid_minor"], invoice["balance_minor"]) == (
        ITEMS_TOTAL,
        0,
        ITEMS_TOTAL,
    )
    assert invoice["structure_total_minor"] == ITEMS_TOTAL
    assert invoice["admission"]["id"] == a1.admission_id
    assert invoice["student"]["id"] == a1.student_id
    assert invoice["fee_structure"]["id"] == a1.structure["id"]
    assert [
        (line["fee_head"], line["amount_minor"], line["adjusted"]) for line in invoice["lines"]
    ] == [(item["fee_head"], item["amount_minor"], False) for item in ITEMS]
    assert [item["kind"] for item in invoice["activity"]] == ["ISSUED"]
    (event,) = [e for e in await h.audit(issued) if e.event_type == "invoice.issued"]
    assert event.metadata == {
        "total_minor": ITEMS_TOTAL,
        "structure_total_minor": ITEMS_TOTAL,
        "currency": "INR",
        "adjusted": False,
        "adjusted_line_count": 0,
    }
    assert "Kavya" not in _audit_values(await h.audit(issued))


async def test_adjustments_need_a_reason_and_keep_the_structure_amounts(
    h: Harness, a1: Billable
) -> None:
    csrf = await sign_in(h, "farah")
    lines = [
        {"fee_head": "tuition", "amount_minor": 20_000_000},  # matched without regard to case
        {"fee_head": "Uniform and kit", "amount_minor": UNIFORM},
        {"fee_head": "Medical examination", "amount_minor": 150_000},  # added
    ]  # Hostel left out
    refused = await issue(h, csrf, a1.admission_id, lines=lines)
    assert refused.status_code == 422
    assert errors(refused) == {("adjustment_reason", "required")}
    unadjusted = await issue(h, csrf, a1.admission_id, reason="Scholarship")
    assert errors(unadjusted) == {("adjustment_reason", "not_adjusted")}

    issued = await issue(
        h, csrf, a1.admission_id, lines=lines, reason="Merit scholarship; day scholar"
    )
    invoice = data(issued, 201)
    assert invoice["adjusted"] is True
    assert invoice["adjustment_reason"] == "Merit scholarship; day scholar"
    assert (invoice["total_minor"], invoice["structure_total_minor"]) == (
        20_000_000 + UNIFORM + 150_000,
        ITEMS_TOTAL,
    )
    assert [
        (line["fee_head"], line["amount_minor"], line["structure_amount_minor"], line["adjusted"])
        for line in invoice["lines"]
    ] == [
        ("Tuition", 20_000_000, TUITION, True),
        ("Hostel", 0, HOSTEL, True),
        ("Uniform and kit", UNIFORM, UNIFORM, False),
        ("Medical examination", 150_000, None, True),
    ]
    (event,) = [e for e in await h.audit(issued) if e.event_type == "invoice.issued"]
    assert (event.metadata["adjusted"], event.metadata["adjusted_line_count"]) == (True, 3)
    assert "scholarship" not in _audit_values(await h.audit(issued)).lower()


async def test_issue_is_validated(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "fiona")
    yesterday = due_in(-1)
    assert errors(await issue(h, csrf, a1.admission_id, due_date=yesterday)) == {
        ("due_date", "in_the_past")
    }
    unknown = await issue(h, csrf, "01a00000-0000-7000-8000-000000000000")
    assert errors(unknown) == {("admission_id", "admission_not_available")}
    for lines in (
        [{"fee_head": "Tuition", "amount_minor": "100"}],
        [{"fee_head": "Tuition", "amount_minor": -1}],
        [{"fee_head": "Tuition", "amount_minor": 10.0}],
    ):
        assert (await issue(h, csrf, a1.admission_id, lines=lines)).status_code == 422
    for body in (
        {"admission_id": a1.admission_id, "due_date": due_in(), "lines": ITEMS},  # no key
        {
            "admission_id": a1.admission_id,
            "due_date": due_in(),
            "lines": ITEMS,
            "idempotency_key": "not-a-uuid",
        },
        {
            "admission_id": a1.admission_id,
            "due_date": due_in(),
            "lines": ITEMS,
            "idempotency_key": key(),
            "total_minor": 1,
        },
    ):
        assert (await send(h, "POST", INVOICES, csrf, body)).status_code == 422, body
    # A course without an active fee structure: nothing to bill from.
    other = await billable(h, h.world.campus_a1, prefix="GPR")
    csrf = await sign_in(h, "fiona")
    data(
        await send(
            h,
            "POST",
            f"/api/v1/fee-structures/{other.structure['id']}/status",
            csrf,
            {"status": "ARCHIVED", "version": other.structure["version"]},
        )
    )
    assert errors(await issue(h, csrf, other.admission_id)) == {
        ("admission_id", "no_active_fee_structure")
    }


async def test_one_live_invoice_per_admission_and_a_replacement_after_cancel(
    h: Harness, a1: Billable
) -> None:
    csrf = await sign_in(h, "fiona")
    first = data(await issue(h, csrf, a1.admission_id), 201)
    second = await issue(h, csrf, a1.admission_id)
    assert second.status_code == 409
    assert errors(second) == {("admission_id", "live_invoice_exists")}
    path = f"{INVOICES}/{first['id']}/cancel"
    no_reason = await send(h, "POST", path, csrf, {"reason": "  ", "version": first["version"]})
    assert errors(no_reason) == {("reason", "required")}
    stale = await send(h, "POST", path, csrf, {"reason": "Wrong course", "version": 99})
    assert stale.status_code == 409
    cancelled = await send(h, "POST", path, csrf, {"reason": "Wrong course", "version": 1})
    cancelled_invoice = data(cancelled)
    assert cancelled_invoice["status"] == "CANCELLED"
    assert cancelled_invoice["status_reason"] == "Wrong course"
    assert cancelled_invoice["balance_minor"] == 0
    (event,) = [e for e in await h.audit(cancelled) if e.event_type == "invoice.cancelled"]
    assert event.metadata == {"total_minor": ITEMS_TOTAL, "currency": "INR", "has_reason": True}
    again = await send(h, "POST", path, csrf, {"reason": "Again", "version": 2})
    assert again.status_code == 422
    replacement = data(await issue(h, csrf, a1.admission_id), 201)
    assert replacement["number"] != first["number"]
    listed = data(await h.client.get(INVOICES, params={"student_id": a1.student_id}))
    assert {(item["id"], item["status"]) for item in listed} == {
        (first["id"], "CANCELLED"),
        (replacement["id"], "ISSUED"),
    }


async def test_invoice_issue_is_idempotent(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "fiona")
    request_key = key()
    created = await issue(
        h, csrf, a1.admission_id, idempotency_key=request_key, due_date=due_in(10)
    )
    invoice = data(created, 201)
    replay = await issue(h, csrf, a1.admission_id, idempotency_key=request_key, due_date=due_in(10))
    assert data(replay, 200)["id"] == invoice["id"]
    assert data(replay, 200)["number"] == invoice["number"]
    assert await h.audit(replay) == []
    reused = await issue(h, csrf, a1.admission_id, idempotency_key=request_key, due_date=due_in(11))
    assert reused.status_code == 409
    assert errors(reused) == {("idempotency_key", "idempotency_key_reused")}
    rows = await h.owner("SELECT count(*) FROM invoices WHERE admission_id = :a", a=a1.admission_id)
    assert rows[0][0] == 1


async def test_concurrent_issues_with_one_key_make_one_invoice(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "fiona")
    request_key, results = key(), []

    async def send_once() -> None:
        response = await issue(
            h, csrf, a1.admission_id, idempotency_key=request_key, due_date=due_in(5)
        )
        results.append((response.status_code, response.json()["data"]["id"]))

    async with anyio.create_task_group() as group:
        group.start_soon(send_once)
        group.start_soon(send_once)
    assert sorted(code for code, _ in results) == [200, 201]
    assert len({invoice_id for _, invoice_id in results}) == 1


async def test_cash_upi_and_bank_transfers_are_confirmed_with_receipts(
    h: Harness, a1: Billable
) -> None:
    csrf = await sign_in(h, "farah")
    invoice = data(await issue(h, csrf, a1.admission_id), 201)
    cash = await pay(h, csrf, invoice["id"], 10_000_000)
    payment = data(cash, 201)
    assert (payment["status"], payment["method"], payment["recorded_by_me"]) == (
        "CONFIRMED",
        "CASH",
        True,
    )
    assert re.fullmatch(rf"RCT-{_label()}-\d{{5}}", payment["receipt"]["number"])
    assert payment["receipt"]["cancelled"] is False
    (event,) = [e for e in await h.audit(cash) if e.event_type == "payment.recorded"]
    assert event.metadata == {
        "amount_minor": 10_000_000,
        "currency": "INR",
        "method": "CASH",
        "status": "CONFIRMED",
    }
    current = await _invoice(h, invoice["id"])
    assert (current["status"], current["paid_minor"], current["balance_minor"]) == (
        "PARTIALLY_PAID",
        10_000_000,
        ITEMS_TOTAL - 10_000_000,
    )
    missing = await pay(h, csrf, invoice["id"], 1_000_000, method="UPI")
    assert errors(missing) == {("reference", "required")}
    upi = data(
        await pay(h, csrf, invoice["id"], 1_000_000, method="UPI", reference="UTR 4471 2290"),
        201,
    )
    assert upi["reference"] == "UTR 4471 2290"
    assert "4471" not in _audit_values(await h.audit(missing))
    future = await pay(h, csrf, invoice["id"], 1, received_on=due_in(1))
    assert errors(future) == {("received_on", "in_the_future")}
    remainder = ITEMS_TOTAL - 11_000_000
    too_much = await pay(
        h, csrf, invoice["id"], remainder + 1, method="BANK_TRANSFER", reference="NEFT 1"
    )
    assert errors(too_much) == {("amount_minor", "exceeds_balance")}
    final = data(
        await pay(h, csrf, invoice["id"], remainder, method="BANK_TRANSFER", reference="NEFT 88"),
        201,
    )
    assert final["status"] == "CONFIRMED"
    paid = await _invoice(h, invoice["id"])
    assert (paid["status"], paid["balance_minor"]) == ("PAID", 0)
    assert len(paid["payments"]) == 3
    assert [item["kind"] for item in paid["activity"]] == ["ISSUED", *["PAYMENT_RECORDED"] * 3]
    assert (await pay(h, csrf, invoice["id"], 1)).status_code == 422
    receipts = sorted(item["receipt"]["number"] for item in paid["payments"])
    counters = [int(number.rsplit("-", 1)[1]) for number in receipts]
    assert counters == list(range(counters[0], counters[0] + 3))  # gap-free
    await paid_matches_confirmed(h, invoice["id"])


async def test_cheques_and_demand_drafts_wait_for_clearance(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "farah")
    invoice = data(await issue(h, csrf, a1.admission_id), 201)
    cheque = data(
        await pay(h, csrf, invoice["id"], 20_000_000, method="CHEQUE", reference="Cheque 004512"),
        201,
    )
    assert (cheque["status"], cheque["receipt"]) == ("PENDING", None)
    pending = await _invoice(h, invoice["id"])
    assert (pending["paid_minor"], pending["pending_minor"], pending["status"]) == (
        0,
        20_000_000,
        "ISSUED",
    )
    # The pending cheque counts toward what may still be recorded.
    over = await pay(h, csrf, invoice["id"], ITEMS_TOTAL - 20_000_000 + 1, method="CASH")
    assert errors(over) == {("amount_minor", "exceeds_balance")}
    summary = data(await h.client.get(SUMMARY))
    assert (summary["pending_count"], summary["pending_minor"]) == (1, 20_000_000)

    confirmed = await _act(h, csrf, cheque, "confirm")
    cleared = data(confirmed)
    assert cleared["status"] == "CONFIRMED"
    assert re.fullmatch(rf"RCT-{_label()}-\d{{5}}", cleared["receipt"]["number"])
    assert (await _invoice(h, invoice["id"]))["paid_minor"] == 20_000_000
    assert (await _act(h, csrf, cleared, "confirm")).status_code == 422

    draft = data(
        await pay(h, csrf, invoice["id"], 1_000_000, method="DEMAND_DRAFT", reference="DD 77881"),
        201,
    )
    assert errors(await _act(h, csrf, draft, "fail", reason=" ")) == {("reason", "required")}
    failed = await _act(h, csrf, draft, "fail", reason="Not honoured by the bank")
    assert (data(failed)["status"], data(failed)["receipt"]) == ("FAILED", None)
    (event,) = await h.audit(failed)
    assert event.metadata == {
        "amount_minor": 1_000_000,
        "currency": "INR",
        "method": "DEMAND_DRAFT",
        "has_reason": True,
    }
    assert (await _act(h, csrf, data(failed), "confirm")).status_code == 422
    assert (await _invoice(h, invoice["id"]))["paid_minor"] == 20_000_000
    await paid_matches_confirmed(h, invoice["id"])


async def test_reversal_is_never_done_by_the_recorder(h: Harness, a1: Billable) -> None:
    officer = await sign_in(h, "farah")
    invoice = data(await issue(h, officer, a1.admission_id), 201)
    by_officer = data(await pay(h, officer, invoice["id"], 5_000_000), 201)
    # The officer has no payment.reverse at all.
    assert (await _act(h, officer, by_officer, "reverse", reason="x")).status_code == 403

    manager = await sign_in(h, "fiona")
    own = data(await pay(h, manager, invoice["id"], 2_000_000), 201)
    assert own["recorded_by_me"] is True
    refused = await _act(h, manager, own, "reverse", reason="Entered twice")
    assert refused.status_code == 422
    assert errors(refused) == {("payment", "recorder_cannot_reverse")}
    officers = data(await h.client.get(f"{PAYMENTS}/{by_officer['id']}"))
    assert officers["recorded_by_me"] is False

    other = await sign_in(h, "faisal")  # a second Finance manager
    assert errors(await _act(h, other, own, "reverse", reason="")) == {("reason", "required")}
    reversed_ = await _act(h, other, own, "reverse", reason="Entered twice")
    payment = data(reversed_)
    assert (payment["status"], payment["status_reason"]) == ("REVERSED", "Entered twice")
    assert payment["receipt"]["cancelled"] is True
    assert payment["recorded_by_me"] is False
    (event,) = await h.audit(reversed_)
    assert event.metadata == {
        "amount_minor": 2_000_000,
        "currency": "INR",
        "method": "CASH",
        "has_reason": True,
    }
    current = await _invoice(h, invoice["id"])
    assert (current["paid_minor"], current["status"]) == (5_000_000, "PARTIALLY_PAID")
    assert (await _act(h, other, payment, "reverse", reason="Again")).status_code == 422
    assert (await _act(h, other, own, "reverse", reason="Stale")).status_code == 409
    await paid_matches_confirmed(h, invoice["id"])


async def test_cancellation_waits_for_pending_and_confirmed_payments(
    h: Harness, a1: Billable
) -> None:
    csrf = await sign_in(h, "fiona")
    invoice = data(await issue(h, csrf, a1.admission_id), 201)
    cheque = data(
        await pay(h, csrf, invoice["id"], 1_000_000, method="CHEQUE", reference="Cheque 1"), 201
    )

    async def cancel() -> Any:
        current = await _invoice(h, invoice["id"])
        return await send(
            h,
            "POST",
            f"{INVOICES}/{invoice['id']}/cancel",
            csrf,
            {"reason": "Wrong fee structure", "version": current["version"]},
        )

    assert errors(await cancel()) == {("status", "open_payments")}  # a pending cheque
    cleared = data(await _act(h, csrf, cheque, "confirm"))
    assert errors(await cancel()) == {("status", "open_payments")}  # now confirmed
    reverser = await sign_in(h, "faisal")
    data(await _act(h, reverser, cleared, "reverse", reason="Cheque entered on the wrong fee"))
    csrf = await sign_in(h, "fiona")
    cancelled = data(await cancel())
    assert cancelled["status"] == "CANCELLED"
    assert {p["status"] for p in cancelled["payments"]} == {"REVERSED"}
    assert errors(await pay(h, csrf, invoice["id"], 1)) == {("status", "invoice_cancelled")}


async def test_payment_recording_is_idempotent(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "farah")
    invoice = data(await issue(h, csrf, a1.admission_id), 201)
    request_key = key()
    first = data(await pay(h, csrf, invoice["id"], 3_000_000, idempotency_key=request_key), 201)
    replay = await pay(h, csrf, invoice["id"], 3_000_000, idempotency_key=request_key)
    assert data(replay, 200)["id"] == first["id"]
    assert data(replay, 200)["receipt"]["number"] == first["receipt"]["number"]
    assert await h.audit(replay) == []
    reused = await pay(h, csrf, invoice["id"], 3_000_001, idempotency_key=request_key)
    assert errors(reused) == {("idempotency_key", "idempotency_key_reused")}
    current = await _invoice(h, invoice["id"])
    assert (len(current["payments"]), current["paid_minor"]) == (1, 3_000_000)

    concurrent_key, results = key(), []

    async def once() -> None:
        results.append(
            (await pay(h, csrf, invoice["id"], 1_000, idempotency_key=concurrent_key)).status_code
        )

    async with anyio.create_task_group() as group:
        group.start_soon(once)
        group.start_soon(once)
    assert sorted(results) == [200, 201]
    rows = await h.owner(
        "SELECT count(*) FROM receipts r JOIN payments p ON p.id = r.payment_id "
        "WHERE p.invoice_id = :i",
        i=invoice["id"],
    )
    assert rows[0][0] == 2
    await paid_matches_confirmed(h, invoice["id"])


async def test_concurrent_payments_never_exceed_the_total(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "fiona")
    invoice = data(await issue(h, csrf, a1.admission_id), 201)
    results: list[int] = []

    async def once() -> None:
        results.append((await pay(h, csrf, invoice["id"], ITEMS_TOTAL - 1)).status_code)

    async with anyio.create_task_group() as group:
        group.start_soon(once)
        group.start_soon(once)
    assert sorted(results) == [201, 422]
    await paid_matches_confirmed(h, invoice["id"])


async def test_campus_scope_hides_other_campuses(h: Harness, a1: Billable) -> None:
    a2 = await billable(h, h.world.campus_a2, prefix="ETO")
    manager = await sign_in(h, "fiona")
    in_a1 = data(await issue(h, manager, a1.admission_id), 201)
    in_a2 = data(await issue(h, manager, a2.admission_id), 201)
    a2_payment = data(await pay(h, manager, in_a2["id"], 1_000), 201)

    await sign_in(h, "farah")  # campus A1 only
    listed = {item["id"] for item in data(await h.client.get(INVOICES))}
    assert in_a1["id"] in listed
    assert in_a2["id"] not in listed
    assert (await h.client.get(f"{INVOICES}/{in_a2['id']}")).status_code == 404
    assert (await h.client.get(f"{PAYMENTS}/{a2_payment['id']}")).status_code == 404
    assert a2_payment["id"] not in {item["id"] for item in data(await h.client.get(PAYMENTS))}
    officer = await sign_in(h, "farah")
    assert (await pay(h, officer, in_a2["id"], 1)).status_code == 404
    assert errors(await issue(h, officer, a2.admission_id)) == {
        ("admission_id", "admission_not_available")
    }
    # Student 360 (R2): a student of another campus looks exactly like an unknown student.
    for student_id in (a2.student_id, "01a00000-0000-7000-8000-000000000000"):
        response = await h.client.get(INVOICES, params={"student_id": student_id})
        assert response.status_code == 200
        assert response.json()["data"] == []
        assert response.json()["meta"]["page"]["total"] == 0
    assert data(await h.client.get(SUMMARY))["invoice_count"] == 1
    await sign_in(h, "feroz")  # campus A2 only
    assert {item["id"] for item in data(await h.client.get(INVOICES))} == {in_a2["id"]}


async def test_finance_permissions(h: Harness, a1: Billable) -> None:
    manager = await sign_in(h, "fiona")
    invoice = data(await issue(h, manager, a1.admission_id), 201)
    payment = data(await pay(h, manager, invoice["id"], 1_000), 201)
    await sign_in(h, "ravi")  # Counsellor: fee structures only
    for path in (INVOICES, f"{INVOICES}/{invoice['id']}", PAYMENTS, SUMMARY):
        assert (await h.client.get(path)).status_code == 403, path
    admissions = await sign_in(h, "maya")  # Admissions manager: reads invoices
    assert data(await h.client.get(f"{INVOICES}/{invoice['id']}"))["id"] == invoice["id"]
    assert (await issue(h, admissions, a1.admission_id)).status_code == 403
    assert (await pay(h, admissions, invoice["id"], 1)).status_code == 403
    officer = await sign_in(h, "farah")
    cancel = await send(
        h,
        "POST",
        f"{INVOICES}/{invoice['id']}/cancel",
        officer,
        {"reason": "x", "version": invoice["version"]},
    )
    assert cancel.status_code == 403
    assert (await _act(h, officer, payment, "reverse", reason="x")).status_code == 403


async def test_lists_filter_and_summarise(h: Harness, a1: Billable) -> None:
    other = await billable(h, h.world.campus_a1, prefix="GPR")
    csrf = await sign_in(h, "fiona")
    overdue = data(await issue(h, csrf, a1.admission_id, due_date=today_ist().isoformat()), 201)
    await h.owner(  # make it overdue: the due date is in the past now
        "UPDATE invoices SET due_date = due_date - 3 WHERE id = :id", id=overdue["id"]
    )
    paid = data(await issue(h, csrf, other.admission_id), 201)
    data(await pay(h, csrf, paid["id"], ITEMS_TOTAL), 201)
    outstanding = data(await h.client.get(INVOICES, params={"outstanding": "true"}))
    assert {item["id"] for item in outstanding} == {overdue["id"]}
    late = data(await h.client.get(INVOICES, params={"overdue": "true"}))
    assert [(item["id"], item["overdue"]) for item in late] == [(overdue["id"], True)]
    by_status = data(await h.client.get(INVOICES, params={"status": "PAID"}))
    assert [item["id"] for item in by_status] == [paid["id"]]
    by_number = data(await h.client.get(INVOICES, params={"q": paid["number"]}))
    assert [item["id"] for item in by_number] == [paid["id"]]
    by_course = data(await h.client.get(INVOICES, params={"course_id": other.course["id"]}))
    assert [item["id"] for item in by_course] == [paid["id"]]
    cash = data(await h.client.get(PAYMENTS, params={"method": "CASH", "status": "CONFIRMED"}))
    assert [item["invoice"]["id"] for item in cash] == [paid["id"]]
    summary = data(await h.client.get(SUMMARY))
    assert summary == {
        "invoice_count": 2,
        "invoiced_minor": 2 * ITEMS_TOTAL,
        "collected_minor": ITEMS_TOTAL,
        "outstanding_minor": ITEMS_TOTAL,
        "outstanding_count": 1,
        "overdue_minor": ITEMS_TOTAL,
        "overdue_count": 1,
        "pending_minor": 0,
        "pending_count": 0,
        "currency": "INR",
        "as_of": today_ist().isoformat(),
    }
    assert (
        data(await h.client.get(SUMMARY, params={"campus_id": str(h.world.campus_a2)}))[
            "invoice_count"
        ]
        == 0
    )
    assert (await h.client.get(INVOICES, params={"sort": "total"})).status_code == 422
