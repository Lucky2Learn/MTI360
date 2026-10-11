"""Financial integrity of fee invoices and payments (Phase 02-5; readiness plan §9).

Exercises the real request transactions, row locks and constraints:

* **Concurrency:** parallel confirmations of one payment take effect once;
  confirm racing fail settles on one outcome; parallel confirmations of
  different payments get unique, gap-free receipt numbers; parallel reversals
  restore the balance once; a reversal racing a payment, and a cancellation
  racing a payment, never break the balance.
* **Rollback:** a fee invoice issue or a confirmation that fails after its
  rows are flushed (a Python error or a PostgreSQL error) leaves no invoice,
  line, payment change, receipt, activity, audit event or sequence gap.
* **Invariant:** ``0 <= paid_minor <= total_minor``, ``paid_minor`` equals
  the sum of ``CONFIRMED`` payments, and the status follows ``paid_minor``
  after every payment, confirmation, failure, reversal and cancellation; the
  database refuses a ``paid_minor`` outside the range on UPDATE.

Concurrent callers who must be different members each use their own HTTP
client (own session cookie) on the same application.
"""

import dataclasses
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import partial
from typing import Any

import anyio
import pytest
from conftest import DatabaseUnderTest
from courses_leads_support import admissions_team
from finance_support import (
    INVOICES,
    ITEMS_TOTAL,
    PAYMENTS,
    Billable,
    admitted,
    billable,
    errors,
    finance_team,
    issue,
    pay,
)
from httpx import ASGITransport, AsyncClient
from identity_support import ORIGIN, Harness, auth_harness
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from tenant_admin_support import data, send, sign_in

from app.core.audit import AuditEventType, write_audit_event
from app.modules.finance import events
from app.modules.finance import invoicing as invoicing_module
from app.modules.finance.domain import InvoiceStatus, invoice_status

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        await admissions_team(harness)
        await finance_team(harness)
        yield harness


@pytest.fixture
async def a1(h: Harness) -> Billable:
    return await billable(h, h.world.campus_a1)


@asynccontextmanager
async def other_client(h: Harness) -> AsyncIterator[Harness]:
    """The same application and world behind a second HTTP client (its own session cookie)."""
    transport = ASGITransport(app=h.app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="https://testserver", headers={"Origin": ORIGIN}
    ) as client:
        yield dataclasses.replace(h, client=client)


async def in_parallel(*calls: Callable[[], Awaitable[Any]]) -> list[Any]:
    """Run ``calls`` concurrently; their responses in call order."""
    results: list[Any] = [None] * len(calls)

    async def run(index: int, call: Callable[[], Awaitable[Any]]) -> None:
        results[index] = await call()

    async with anyio.create_task_group() as group:
        for index, call in enumerate(calls):
            group.start_soon(run, index, call)
    return results


async def _act(h: Harness, csrf: str, payment: dict[str, Any], action: str, **body: Any) -> Any:
    return await send(
        h,
        "POST",
        f"{PAYMENTS}/{payment['id']}/{action}",
        csrf,
        {"version": payment["version"], **body},
    )


async def _cancel(h: Harness, csrf: str, invoice_id: str, version: int) -> Any:
    return await send(
        h,
        "POST",
        f"{INVOICES}/{invoice_id}/cancel",
        csrf,
        {"reason": "Raised on the wrong fee structure", "version": version},
    )


async def _cheque(h: Harness, csrf: str, invoice_id: str, amount: int, n: int) -> dict[str, Any]:
    response = await pay(h, csrf, invoice_id, amount, method="CHEQUE", reference=f"Cheque {n:06d}")
    return data(response, 201)  # type: ignore[no-any-return]


async def _counter(h: Harness, name: str) -> int:
    """The last number allocated in Institute A's ``name`` sequence (0 before the first)."""
    rows = await h.owner(
        "SELECT coalesce(max(last_value), 0) FROM tenant_sequences "
        "WHERE tenant_id = :t AND name = :n",
        t=h.world.tenant_a,
        n=name,
    )
    return int(rows[0][0])


async def _count(h: Harness, sql: str, **params: Any) -> int:
    return int((await h.owner(sql, **params))[0][0])


async def _activity_count(h: Harness, invoice_id: str, kind: str) -> int:
    return await _count(
        h,
        "SELECT count(*) FROM finance_activities WHERE invoice_id = :i AND kind = :k",
        i=uuid.UUID(invoice_id),
        k=kind,
    )


async def _audit_count(h: Harness, event_type: AuditEventType, target_id: str) -> int:
    return await _count(
        h,
        "SELECT count(*) FROM audit_events WHERE event_type = :e AND target_id = :t",
        e=event_type.name,
        t=uuid.UUID(target_id),
    )


async def assert_balanced(h: Harness, invoice_id: str) -> tuple[int, int, str]:
    """The invariant of one fee invoice, read as the owner; returns (paid, total, status).

    * ``0 <= paid_minor <= total_minor``;
    * ``paid_minor`` is the sum of its ``CONFIRMED`` payments;
    * the status follows ``paid_minor``; a cancelled invoice has nothing paid;
    * one receipt per payment that was ever confirmed (confirmed or reversed).
    """
    ((paid, total, status, confirmed, receipts, ever_confirmed),) = await h.owner(
        "SELECT i.paid_minor, i.total_minor, i.status, "
        "coalesce((SELECT sum(p.amount_minor) FROM payments p "
        "  WHERE p.invoice_id = i.id AND p.status = 'CONFIRMED'), 0), "
        "(SELECT count(*) FROM receipts r JOIN payments p ON p.id = r.payment_id "
        "  WHERE p.invoice_id = i.id), "
        "(SELECT count(*) FROM payments p WHERE p.invoice_id = i.id "
        "  AND p.status IN ('CONFIRMED', 'REVERSED')) "
        "FROM invoices i WHERE i.id = :id",
        id=uuid.UUID(invoice_id),
    )
    assert 0 <= paid <= total
    assert paid == confirmed
    if status == InvoiceStatus.CANCELLED.value:
        assert paid == 0
    else:
        assert status == invoice_status(total, paid).value
    assert receipts == ever_confirmed
    return paid, total, status


# --- Concurrency ---------------------------------------------------------------------------


async def test_parallel_confirmations_of_one_payment_take_effect_once(
    h: Harness, a1: Billable
) -> None:
    csrf = await sign_in(h, "farah")
    invoice = data(await issue(h, csrf, a1.admission_id), 201)
    cheque = await _cheque(h, csrf, invoice["id"], 12_000_000, 1)
    receipts_before = await _counter(h, "RECEIPT")

    responses = await in_parallel(*(lambda: _act(h, csrf, cheque, "confirm") for _ in range(3)))

    codes = sorted(response.status_code for response in responses)
    assert codes == [200, 409, 409], [response.text for response in responses]
    (winner,) = [response for response in responses if response.status_code == 200]
    assert data(winner)["status"] == "CONFIRMED"
    assert await _counter(h, "RECEIPT") == receipts_before + 1
    assert (
        await _count(
            h, "SELECT count(*) FROM receipts WHERE payment_id = :p", p=uuid.UUID(cheque["id"])
        )
        == 1
    )
    assert await _activity_count(h, invoice["id"], "PAYMENT_CONFIRMED") == 1
    assert await _audit_count(h, events.PAYMENT_CONFIRMED, cheque["id"]) == 1
    paid, _, status = await assert_balanced(h, invoice["id"])
    assert (paid, status) == (12_000_000, "PARTIALLY_PAID")


async def test_confirm_racing_fail_settles_on_one_outcome(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "farah")
    invoice = data(await issue(h, csrf, a1.admission_id), 201)
    for n in range(1, 4):  # repeat: either order may win
        draft = data(
            await pay(
                h, csrf, invoice["id"], 1_000_000, method="DEMAND_DRAFT", reference=f"DD {n}"
            ),
            201,
        )
        confirm, fail = await in_parallel(
            partial(_act, h, csrf, draft, "confirm"),
            partial(_act, h, csrf, draft, "fail", reason="Not honoured by the bank"),
        )
        assert sorted((confirm.status_code, fail.status_code)) == [200, 409]
        rows = await h.owner(
            "SELECT p.status, (SELECT count(*) FROM receipts r WHERE r.payment_id = p.id) "
            "FROM payments p WHERE p.id = :p",
            p=uuid.UUID(draft["id"]),
        )
        status, receipts = rows[0]
        expected = "CONFIRMED" if confirm.status_code == 200 else "FAILED"
        assert (status, receipts) == (expected, 1 if expected == "CONFIRMED" else 0)
        await assert_balanced(h, invoice["id"])


async def test_parallel_confirmations_get_unique_gap_free_receipts(
    h: Harness, a1: Billable
) -> None:
    second = await admitted(h, course=a1.course, campus=h.world.campus_a1, full_name="Rohan Iyer")
    csrf = await sign_in(h, "farah")
    first_invoice = data(await issue(h, csrf, a1.admission_id), 201)
    second_invoice = data(await issue(h, csrf, str(second["id"])), 201)
    quarter = ITEMS_TOTAL // 4
    cheques = [await _cheque(h, csrf, first_invoice["id"], quarter, n) for n in range(1, 4)]
    cheques.append(
        await _cheque(h, csrf, first_invoice["id"], ITEMS_TOTAL - 3 * quarter, 4)
    )  # the four settle the first invoice exactly
    cheques += [await _cheque(h, csrf, second_invoice["id"], 2_500_000, n) for n in (5, 6)]
    before = await _counter(h, "RECEIPT")

    responses = await in_parallel(
        *(lambda cheque=cheque: _act(h, csrf, cheque, "confirm") for cheque in cheques)
    )

    assert [response.status_code for response in responses] == [200] * 6
    numbers = [data(response)["receipt"]["number"] for response in responses]
    assert len(set(numbers)) == 6
    counters = sorted(int(number.rsplit("-", 1)[1]) for number in numbers)
    assert counters == list(range(before + 1, before + 7))  # unique and gap-free
    assert await _counter(h, "RECEIPT") == before + 6
    assert await assert_balanced(h, first_invoice["id"]) == (ITEMS_TOTAL, ITEMS_TOTAL, "PAID")
    assert (await assert_balanced(h, second_invoice["id"]))[0] == 5_000_000


async def test_parallel_reversals_restore_the_balance_once(h: Harness, a1: Billable) -> None:
    officer = await sign_in(h, "farah")
    invoice = data(await issue(h, officer, a1.admission_id), 201)
    data(await pay(h, officer, invoice["id"], 7_000_000), 201)  # stays confirmed
    reversed_ = data(await pay(h, officer, invoice["id"], 4_000_000), 201)

    async with other_client(h) as h2:
        fiona = await sign_in(h, "fiona")
        faisal = await sign_in(h2, "faisal")
        responses = await in_parallel(
            lambda: _act(h, fiona, reversed_, "reverse", reason="Entered twice"),
            lambda: _act(h2, faisal, reversed_, "reverse", reason="Entered twice"),
        )

    assert sorted(response.status_code for response in responses) == [200, 409]
    # A double reversal would leave 3_000_000, which the range CHECK alone would not catch.
    paid, _, status = await assert_balanced(h, invoice["id"])
    assert (paid, status) == (7_000_000, "PARTIALLY_PAID")
    assert await _audit_count(h, events.PAYMENT_REVERSED, reversed_["id"]) == 1
    assert await _activity_count(h, invoice["id"], "PAYMENT_REVERSED") == 1


async def test_a_reversal_racing_a_payment_never_overcollects(h: Harness, a1: Billable) -> None:
    officer = await sign_in(h, "farah")
    invoice = data(await issue(h, officer, a1.admission_id), 201)
    first = data(await pay(h, officer, invoice["id"], 10_000_000), 201)
    data(await pay(h, officer, invoice["id"], ITEMS_TOTAL - 10_000_000), 201)
    assert (await assert_balanced(h, invoice["id"]))[2] == "PAID"

    async with other_client(h) as h2:
        manager = await sign_in(h2, "faisal")
        payment, reversal = await in_parallel(
            lambda: pay(h, officer, invoice["id"], 10_000_000, method="UPI", reference="UTR 9001"),
            lambda: _act(h2, manager, first, "reverse", reason="Paid by the wrong student"),
        )

    assert reversal.status_code == 200
    paid, total, status = await assert_balanced(h, invoice["id"])
    if payment.status_code == 201:  # the reversal freed the headroom first
        assert (paid, status) == (total, "PAID")
    else:  # the payment came first, while the invoice was still fully paid
        assert errors(payment) == {("amount_minor", "exceeds_balance")}
        assert (paid, status) == (total - 10_000_000, "PARTIALLY_PAID")


async def test_a_cancellation_racing_a_payment_leaves_no_paid_cancelled_invoice(
    h: Harness, a1: Billable
) -> None:
    async with other_client(h) as h2:
        officer = await sign_in(h, "farah")
        manager = await sign_in(h2, "fiona")
        for _ in range(3):  # repeat: either order may win
            current = data(await issue(h, officer, a1.admission_id), 201)
            payment, cancel = await in_parallel(
                partial(pay, h, officer, current["id"], 2_000_000),
                partial(_cancel, h2, manager, current["id"], current["version"]),
            )
            paid, _, status = await assert_balanced(h, current["id"])
            if cancel.status_code == 200:
                assert status == "CANCELLED"
                assert payment.status_code == 422
                assert errors(payment) == {("status", "invoice_cancelled")}
                assert paid == 0
            else:
                # The payment changed the invoice first: the stale version or open payment refuses.
                assert payment.status_code == 201
                assert cancel.status_code in {409, 422}
                assert (paid, status) == (2_000_000, "PARTIALLY_PAID")
                # Settle it (reverse, cancel) so the admission can take the next round's invoice.
                data(await _act(h2, manager, data(payment, 201), "reverse", reason="Next round"))
                latest = data(await h2.client.get(f"{INVOICES}/{current['id']}"))
                data(await _cancel(h2, manager, current["id"], latest["version"]))


# --- Rollback ------------------------------------------------------------------------------


def _fail_on(
    monkeypatch: pytest.MonkeyPatch, event_type: AuditEventType, *, in_database: bool
) -> list[AuditEventType]:
    """Make ``event_type``'s audit write — the last step of its command — fail.

    ``in_database``: a PostgreSQL error (division by zero) that aborts the
    transaction; otherwise a Python error. Returns the events that failed.
    """
    failed: list[AuditEventType] = []

    async def failing(db: AsyncSession, event: AuditEventType, **kwargs: Any) -> None:
        if event != event_type:
            await write_audit_event(db, event, **kwargs)
            return
        failed.append(event)
        if in_database:
            await db.execute(text("SELECT 1 / 0"))
        raise RuntimeError("injected failure after the command's rows were flushed")

    monkeypatch.setattr(invoicing_module, "write_audit_event", failing)
    return failed


@pytest.mark.parametrize("in_database", [False, True], ids=["python-error", "database-error"])
async def test_a_failed_issue_rolls_back_everything(
    h: Harness, a1: Billable, monkeypatch: pytest.MonkeyPatch, in_database: bool
) -> None:
    csrf = await sign_in(h, "farah")
    before = await _counter(h, "INVOICE")
    failed = _fail_on(monkeypatch, events.INVOICE_ISSUED, in_database=in_database)

    response = await issue(h, csrf, a1.admission_id)

    assert failed == [events.INVOICE_ISSUED]  # it failed after the invoice and lines were flushed
    assert response.status_code == 500
    body = response.text.lower()
    for internal in ("division", "injected", "traceback"):
        assert internal not in body
    admission = uuid.UUID(a1.admission_id)
    assert (
        await _count(h, "SELECT count(*) FROM invoices WHERE admission_id = :a", a=admission) == 0
    )
    assert (
        await _count(
            h,
            "SELECT count(*) FROM invoice_lines l JOIN invoices i ON i.id = l.invoice_id "
            "WHERE i.admission_id = :a",
            a=admission,
        )
        == 0
    )
    assert (
        await _count(
            h,
            "SELECT count(*) FROM finance_activities f JOIN invoices i ON i.id = f.invoice_id "
            "WHERE i.admission_id = :a",
            a=admission,
        )
        == 0
    )
    assert await h.audit(response) == []
    assert await _counter(h, "INVOICE") == before  # the number was not consumed

    monkeypatch.undo()
    invoice = data(await issue(h, csrf, a1.admission_id), 201)  # the admission is not locked
    assert int(invoice["number"].rsplit("-", 1)[1]) == before + 1  # no gap
    await assert_balanced(h, invoice["id"])


@pytest.mark.parametrize("in_database", [False, True], ids=["python-error", "database-error"])
async def test_a_failed_confirmation_rolls_back_everything(
    h: Harness, a1: Billable, monkeypatch: pytest.MonkeyPatch, in_database: bool
) -> None:
    csrf = await sign_in(h, "farah")
    invoice = data(await issue(h, csrf, a1.admission_id), 201)
    cheque = await _cheque(h, csrf, invoice["id"], 9_000_000, 1)
    before = await _counter(h, "RECEIPT")
    failed = _fail_on(monkeypatch, events.PAYMENT_CONFIRMED, in_database=in_database)

    response = await _act(h, csrf, cheque, "confirm")

    assert failed == [events.PAYMENT_CONFIRMED]
    assert response.status_code == 500
    current = data(await h.client.get(f"{PAYMENTS}/{cheque['id']}"))
    assert (current["status"], current["version"], current["receipt"]) == (
        "PENDING",
        cheque["version"],
        None,
    )
    assert await _counter(h, "RECEIPT") == before
    assert await h.audit(response) == []
    assert await assert_balanced(h, invoice["id"]) == (0, ITEMS_TOTAL, "ISSUED")

    monkeypatch.undo()
    confirmed = data(await _act(h, csrf, cheque, "confirm"))
    assert int(confirmed["receipt"]["number"].rsplit("-", 1)[1]) == before + 1
    assert (await assert_balanced(h, invoice["id"]))[0] == 9_000_000


# --- Invariant -----------------------------------------------------------------------------


async def test_paid_stays_within_the_total_through_every_transition(
    h: Harness, a1: Billable
) -> None:
    officer = await sign_in(h, "farah")
    invoice = data(await issue(h, officer, a1.admission_id), 201)
    invoice_id = invoice["id"]
    seen: list[tuple[int, str]] = []

    async def check(step: str) -> None:
        paid, _, status = await assert_balanced(h, invoice_id)
        seen.append((paid, status))
        assert paid >= 0, step

    await check("issued")
    cash = data(await pay(h, officer, invoice_id, 8_000_000), 201)
    await check("cash")
    cheque = await _cheque(h, officer, invoice_id, 6_000_000, 1)
    await check("pending cheque: no balance change")
    over = await pay(h, officer, invoice_id, ITEMS_TOTAL - 14_000_000 + 1)
    assert errors(over) == {("amount_minor", "exceeds_balance")}
    await check("overpayment refused")
    data(await _act(h, officer, cheque, "confirm"))
    await check("cheque confirmed")
    draft = data(
        await pay(h, officer, invoice_id, 1_000_000, method="DEMAND_DRAFT", reference="DD 1"), 201
    )
    data(await _act(h, officer, draft, "fail", reason="Not honoured by the bank"))
    await check("draft failed")
    rest = data(
        await pay(h, officer, invoice_id, ITEMS_TOTAL - 14_000_000, method="UPI", reference="U1"),
        201,
    )
    await check("fully paid")
    assert errors(await pay(h, officer, invoice_id, 1)) == {("amount_minor", "exceeds_balance")}
    await check("payment on a paid invoice refused")

    manager = await sign_in(h, "fiona")
    for payment in (cash, rest):
        data(await _act(h, manager, payment, "reverse", reason="Recorded on the wrong invoice"))
        await check("reversed")
    cleared = data(await h.client.get(f"{PAYMENTS}/{cheque['id']}"))
    data(await _act(h, manager, cleared, "reverse", reason="Recorded on the wrong invoice"))
    await check("all reversed")
    latest = data(await h.client.get(f"{INVOICES}/{invoice_id}"))
    data(await _cancel(h, manager, invoice_id, latest["version"]))
    await check("cancelled")
    officer = await sign_in(h, "farah")
    assert errors(await pay(h, officer, invoice_id, 1)) == {("status", "invoice_cancelled")}
    await check("payment on a cancelled invoice refused")

    assert seen == [
        (0, "ISSUED"),
        (8_000_000, "PARTIALLY_PAID"),
        (8_000_000, "PARTIALLY_PAID"),
        (8_000_000, "PARTIALLY_PAID"),
        (14_000_000, "PARTIALLY_PAID"),
        (14_000_000, "PARTIALLY_PAID"),
        (ITEMS_TOTAL, "PAID"),
        (ITEMS_TOTAL, "PAID"),
        (ITEMS_TOTAL - 8_000_000, "PARTIALLY_PAID"),
        (6_000_000, "PARTIALLY_PAID"),
        (0, "ISSUED"),
        (0, "CANCELLED"),
        (0, "CANCELLED"),
    ]


async def test_the_database_refuses_paid_outside_the_total(h: Harness, a1: Billable) -> None:
    csrf = await sign_in(h, "farah")
    invoice = data(await issue(h, csrf, a1.admission_id), 201)
    invoice_id = uuid.UUID(invoice["id"])
    for paid, status in (
        (ITEMS_TOTAL + 1, "PAID"),
        (ITEMS_TOTAL + 1, "PARTIALLY_PAID"),
        (-1, "ISSUED"),
        (-1, "PARTIALLY_PAID"),
    ):
        with pytest.raises(DBAPIError) as refused:
            await h.owner(
                "UPDATE invoices SET paid_minor = :p, status = :s WHERE id = :id",
                p=paid,
                s=status,
                id=invoice_id,
            )
        message = str(refused.value)
        assert "ck_invoices_paid_minor" in message or "ck_invoices_status_paid" in message
    assert await assert_balanced(h, invoice["id"]) == (0, ITEMS_TOTAL, "ISSUED")
