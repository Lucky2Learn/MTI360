"""Cross-tenant isolation of every Finance-lite route (Phase 02-5; ADR-0022, tenancy.md §8).

Institute B (Carol, its owner) owns a course with an active and a draft fee
structure, an admitted student, and a fee invoice with a confirmed cash
payment (and receipt) and a pending cheque. Alice, the owner of institute A
with every permission, calls every route with B's identifiers: reads and
changes are **not found** (404, the same answer as for a missing row), lists
and the summary contain none of B's rows, B's references are refused in A's
writes with the answer given for an unknown row, and B's rows are unchanged
afterwards. Each test is named in ``tests/cross_tenant_registry.py``; the
meta-test keeps the two in step.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import pytest
from conftest import DatabaseUnderTest
from finance_support import (
    FEE_STRUCTURES,
    INVOICES,
    ITEMS,
    PAYMENTS,
    SUMMARY,
    Billable,
    billable,
    errors,
    issue,
    new_structure,
    pay,
    today_ist,
)
from identity_support import Harness, auth_harness
from tenant_admin_support import data, send, sign_in

pytestmark = [pytest.mark.anyio, pytest.mark.integration]
UNKNOWN = "01a00000-0000-7000-8000-000000000000"


@dataclass
class Other:
    """Institute B's rows, seen from institute A."""

    billable: Billable
    draft: dict[str, Any]
    invoice: dict[str, Any]
    payment: dict[str, Any]
    cheque: dict[str, Any]

    @property
    def course(self) -> dict[str, Any]:
        return self.billable.course

    @property
    def structure(self) -> dict[str, Any]:
        return self.billable.structure


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        yield harness


@pytest.fixture
async def b(h: Harness) -> Other:
    other = await billable(h, h.world.campus_b1, prefix="B", admissions="carol", finance="carol")
    csrf = await sign_in(h, "carol")
    draft = await new_structure(h, csrf, other.course["id"], activate=False, name="B draft fees")
    invoice = data(await issue(h, csrf, other.admission_id), 201)
    payment = data(await pay(h, csrf, invoice["id"], 1_000_000), 201)
    cheque = data(
        await pay(h, csrf, invoice["id"], 2_000_000, method="CHEQUE", reference="Cheque 7"), 201
    )
    invoice = data(await h.client.get(f"{INVOICES}/{invoice['id']}"))
    return Other(other, draft, invoice, payment, cheque)


async def _alice(h: Harness) -> str:
    return await sign_in(h, "alice")


async def _unchanged(h: Harness, table: str, row: dict[str, Any]) -> None:
    rows = await h.owner(f"SELECT version FROM {table} WHERE id = :id", id=row["id"])  # noqa: S608
    assert rows[0][0] == row["version"], table


def _ids(response: Any) -> set[str]:
    return {item["id"] for item in data(response)}


# --- Fee structures ------------------------------------------------------------------------


async def test_fee_structure_list_holds_no_other_tenant_structure(h: Harness, b: Other) -> None:
    await _alice(h)
    assert not _ids(await h.client.get(FEE_STRUCTURES)) & {b.structure["id"], b.draft["id"]}
    for params in ({"course_id": b.course["id"]}, {"q": "Fees"}, {"q": b.course["code"]}):
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


# --- Fee invoices ----------------------------------------------------------------------------


async def test_invoice_list_holds_no_other_tenant_invoice(h: Harness, b: Other) -> None:
    await _alice(h)
    assert b.invoice["id"] not in _ids(await h.client.get(INVOICES))
    for params in (
        {"q": b.invoice["number"]},
        {"q": b.billable.admission["admission_number"]},
        {"course_id": b.course["id"]},
        {"campus_id": str(h.world.campus_b1)},
        {"outstanding": "true"},
    ):
        assert _ids(await h.client.get(INVOICES, params=params)) == set(), params
    # Student 360 (R2): another tenant's student answers exactly like an unknown one.
    answers = []
    for student_id in (b.billable.student_id, UNKNOWN):
        response = await h.client.get(INVOICES, params={"student_id": student_id})
        assert response.status_code == 200
        answers.append(response.json()["data"])
    assert answers == [[], []]


async def test_invoice_issue_refuses_other_tenant_admissions(h: Harness, b: Other) -> None:
    csrf = await _alice(h)
    answers = [
        errors(await issue(h, csrf, admission)) for admission in (b.billable.admission_id, UNKNOWN)
    ]
    assert answers[0] == answers[1] == {("admission_id", "admission_not_available")}
    rows = await h.owner("SELECT count(*) FROM invoices WHERE tenant_id = :t", t=h.world.tenant_a)
    assert rows[0][0] == 0


async def test_other_tenant_invoice_reads_are_not_found(h: Harness, b: Other) -> None:
    await _alice(h)
    response = await h.client.get(f"{INVOICES}/{b.invoice['id']}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_other_tenant_invoice_changes_are_not_found(h: Harness, b: Other) -> None:
    csrf = await _alice(h)
    cancel = await send(
        h,
        "POST",
        f"{INVOICES}/{b.invoice['id']}/cancel",
        csrf,
        {"reason": "Taken over", "version": b.invoice["version"]},
    )
    assert cancel.status_code == 404
    recorded = await pay(h, csrf, b.invoice["id"], 1_000)
    assert recorded.status_code == 404
    await _unchanged(h, "invoices", b.invoice)
    rows = await h.owner("SELECT count(*) FROM payments WHERE invoice_id = :i", i=b.invoice["id"])
    assert rows[0][0] == 2


# --- Payments ------------------------------------------------------------------------------


async def test_payment_list_holds_no_other_tenant_payment(h: Harness, b: Other) -> None:
    await _alice(h)
    theirs = {b.payment["id"], b.cheque["id"]}
    assert not _ids(await h.client.get(PAYMENTS)) & theirs
    for params in (
        {"q": b.payment["receipt"]["number"]},
        {"q": "Cheque 7"},
        {"campus_id": str(h.world.campus_b1)},
        {"status": "PENDING"},
    ):
        assert _ids(await h.client.get(PAYMENTS, params=params)) == set(), params


async def test_other_tenant_payment_reads_are_not_found(h: Harness, b: Other) -> None:
    await _alice(h)
    for payment in (b.payment, b.cheque):
        response = await h.client.get(f"{PAYMENTS}/{payment['id']}")
        assert response.status_code == 404


async def test_other_tenant_payment_changes_are_not_found(h: Harness, b: Other) -> None:
    csrf = await _alice(h)
    for payment, action, body in (
        (b.cheque, "confirm", {}),
        (b.cheque, "fail", {"reason": "Taken over"}),
        (b.payment, "reverse", {"reason": "Taken over"}),
    ):
        response = await send(
            h,
            "POST",
            f"{PAYMENTS}/{payment['id']}/{action}",
            csrf,
            {"version": payment["version"], **body},
        )
        assert response.status_code == 404, action
    await _unchanged(h, "payments", b.payment)
    await _unchanged(h, "payments", b.cheque)
    await _unchanged(h, "invoices", b.invoice)


async def test_finance_summary_counts_no_other_tenant_invoice(h: Harness, b: Other) -> None:
    await _alice(h)
    for params in ({}, {"campus_id": str(h.world.campus_b1)}):
        summary = data(await h.client.get(SUMMARY, params=params))
        assert summary == {
            "invoice_count": 0,
            "invoiced_minor": 0,
            "collected_minor": 0,
            "outstanding_minor": 0,
            "outstanding_count": 0,
            "overdue_minor": 0,
            "overdue_count": 0,
            "pending_minor": 0,
            "pending_count": 0,
            "currency": "INR",
            "as_of": today_ist().isoformat(),
        }, params
    assert b.invoice["paid_minor"] == 1_000_000  # B's own figures are untouched
