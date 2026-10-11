"""Development seed contract for Finance-lite (Phase 02-5; readiness plan §8).

The committed file covers the demo the plan asks for, and the finance section
is refused, before anything is written, wherever the API would refuse the
same history: permissions and campus scope, one live fee invoice per
admission, the fee structure, adjustments, overpayment (pending included),
the recorder never reversing, cancellation with open payments.
"""

import copy
from collections import Counter
from typing import Any

import pytest

from app.modules.courses.domain import CourseStatus
from app.modules.finance.domain import (
    FeeStructureStatus,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
)
from app.seed import DEFAULT_SEED_FILE, SeedError, load_seed, parse_seed

OWNER = "owner@malabar-seafarers.example"
MANAGER = "accounts@malabar-seafarers.example"
SECOND_MANAGER = "bursar@malabar-seafarers.example"
OFFICER = "fees.kochi@malabar-seafarers.example"  # Finance officer, KOC only
COUNSELLOR = "counsellor@malabar-seafarers.example"
ITEMS = [
    {"fee_head": "Tuition", "amount_minor": 20_000_000},
    {"fee_head": "Hostel and mess", "amount_minor": 5_000_000},
]
TOTAL = 25_000_000


def _member(email: str, role: str, campuses: list[str] | None = None) -> dict[str, Any]:
    member: dict[str, Any] = {"email": email, "display_name": "Fictitious Person", "role": role}
    if campuses:
        member |= {"campus_scope": "SELECTED", "campuses": campuses}
    return member


def _application(key: str, campus: str, mobile: str, status: str = "ADMITTED") -> dict[str, Any]:
    return {
        "key": key,
        "course": "DNS",
        "campus": campus,
        "created_by": OWNER,
        "reviewed_by": OWNER,  # ADMITTED and APPROVED are decided
        "status": status,
        "full_name": "Fictitious Cadet",
        "mobile": f"+91 90000 10{mobile}",
        "date_of_birth": "2007-01-01",
        "highest_qualification": "12th PCM, 2025",
        "declared": True,
        "documents": [{"type": "PASSPORT", "status": "VERIFIED"}],
    }


def _document() -> dict[str, Any]:
    """A valid institute with one fee structure and one partly paid fee invoice."""
    return {
        "institutes": [
            {
                "name": "Malabar Seafarers Institute",
                "status": "ACTIVE",
                "campuses": [
                    {"code": "KOC", "name": "Kochi Campus"},
                    {"code": "CLT", "name": "Kozhikode Campus"},
                ],
                "members": [
                    _member(OWNER, "INSTITUTE_OWNER"),
                    _member(MANAGER, "FINANCE_MANAGER"),
                    _member(SECOND_MANAGER, "FINANCE_MANAGER"),
                    _member(OFFICER, "FINANCE_OFFICER", ["KOC"]),
                    _member(COUNSELLOR, "COUNSELLOR", ["KOC"]),
                ],
                "courses": [
                    {
                        "code": "DNS",
                        "name": "Diploma in Nautical Science",
                        "category": "PRE_SEA",
                        "status": "ACTIVE",
                    },
                    {"code": "GPR", "name": "GP Rating", "category": "PRE_SEA", "status": "ACTIVE"},
                ],
                "applications": [
                    _application("A1", "KOC", "901"),
                    _application("A2", "CLT", "902"),
                    _application("A3", "KOC", "903", status="APPROVED"),
                ],
                "fee_structures": [
                    {
                        "key": "DNS",
                        "course": "DNS",
                        "name": "DNS fees 2026-27",
                        "status": "ACTIVE",
                        "created_by": MANAGER,
                        "items": copy.deepcopy(ITEMS),
                    },
                    {
                        "key": "GPR",
                        "course": "GPR",
                        "name": "GP Rating fees 2026-27",
                        "status": "ACTIVE",
                        "created_by": MANAGER,
                        "items": [{"fee_head": "Tuition", "amount_minor": 18_000_000}],
                    },
                ],
                "invoices": [
                    {
                        "key": "I1",
                        "application": "A1",
                        "structure": "DNS",
                        "due_in_days": 30,
                        "issued_by": OFFICER,
                        "payments": [
                            {
                                "amount_minor": 5_000_000,
                                "method": "CASH",
                                "received_days_ago": 1,
                                "recorded_by": OFFICER,
                                "status": "CONFIRMED",
                            }
                        ],
                    }
                ],
            }
        ]
    }


def _institute(document: dict[str, Any]) -> dict[str, Any]:
    return document["institutes"][0]  # type: ignore[no-any-return]


def _invoice(document: dict[str, Any]) -> dict[str, Any]:
    return _institute(document)["invoices"][0]  # type: ignore[no-any-return]


def _payment(document: dict[str, Any]) -> dict[str, Any]:
    return _invoice(document)["payments"][0]  # type: ignore[no-any-return]


def test_the_minimal_document_is_valid() -> None:
    (institute,) = parse_seed(_document())
    (invoice,) = institute.finance.invoices
    assert (invoice.status, invoice.total_minor, invoice.paid_minor) == (
        InvoiceStatus.PARTIALLY_PAID,
        TOTAL,
        5_000_000,
    )


def test_the_committed_seed_covers_the_finance_demo() -> None:
    """Readiness plan §8: Konkan covers every state; Coromandel one invoice and one payment."""
    konkan, coromandel = load_seed(DEFAULT_SEED_FILE)
    finance = konkan.finance
    admitted = [a for a in konkan.applications if a.status.value == "ADMITTED"]
    assert len(admitted) >= 7  # Sandeep Patil and about six more
    assert {a.course for a in admitted} == {
        c.code for c in konkan.courses if c.status is CourseStatus.ACTIVE
    }
    assert {a.campus for a in admitted} == {code for code, _ in konkan.campuses}

    statuses = Counter(s.status for s in finance.fee_structures)
    assert statuses[FeeStructureStatus.DRAFT] >= 1
    assert statuses[FeeStructureStatus.ARCHIVED] >= 1
    active = {s.course for s in finance.fee_structures if s.status is FeeStructureStatus.ACTIVE}
    assert active == {c.code for c in konkan.courses if c.status is CourseStatus.ACTIVE}

    invoices = finance.invoices
    assert {i.status for i in invoices} == set(InvoiceStatus)
    assert any(i.status is InvoiceStatus.ISSUED and i.due_in_days < 0 for i in invoices)
    assert any(i.status is InvoiceStatus.PARTIALLY_PAID and i.due_in_days < 0 for i in invoices)
    assert any(i.adjustment_reason for i in invoices)
    assert {i.application for i in invoices if i.status is InvoiceStatus.CANCELLED} <= {
        i.application for i in invoices if i.status is not InvoiceStatus.CANCELLED
    }  # cancelled and replaced
    assert {a.key for a in admitted} - {i.application for i in invoices}  # one left to bill
    payments = [(p.method, p.status) for i in invoices for p in i.payments]
    assert (PaymentMethod.CHEQUE, PaymentStatus.PENDING) in payments
    assert (PaymentMethod.DEMAND_DRAFT, PaymentStatus.FAILED) in payments
    assert any(status is PaymentStatus.REVERSED for _, status in payments)

    (only,) = coromandel.finance.invoices
    assert len(only.payments) == 1


def test_the_committed_seed_reverses_only_by_someone_else_and_uses_finance_roles() -> None:
    for institute in load_seed(DEFAULT_SEED_FILE):
        for invoice in institute.finance.invoices:
            for payment in invoice.payments:
                if payment.status is PaymentStatus.REVERSED:
                    assert payment.closed_by != payment.recorded_by
    konkan = load_seed(DEFAULT_SEED_FILE)[0]
    roles = {m.email: m.role.value for m in konkan.members}
    actors = {i.issued_by for i in konkan.finance.invoices} | {
        p.recorded_by for i in konkan.finance.invoices for p in i.payments
    }
    assert {roles[a] for a in actors} <= {"FINANCE_MANAGER", "FINANCE_OFFICER"}


def _set(path: str, value: Any) -> Any:
    def change(document: dict[str, Any]) -> None:
        *parents, last = path.split(".")
        target: Any = {
            "institute": _institute(document),
            "invoice": _invoice(document),
            "payment": _payment(document),
            "structure": _institute(document)["fee_structures"][0],
        }[parents[0]]
        for parent in parents[1:]:
            target = target[parent]
        if value is _DELETE:
            del target[last]
        else:
            target[last] = value

    return change


_DELETE = object()


def _add_payment(**payment: Any) -> Any:
    def change(document: dict[str, Any]) -> None:
        _invoice(document)["payments"].append(
            {"received_days_ago": 0, "recorded_by": OFFICER} | payment
        )

    return change


def _add_invoice(**invoice: Any) -> Any:
    def change(document: dict[str, Any]) -> None:
        _institute(document)["invoices"].append(
            {"key": "I2", "structure": "DNS", "due_in_days": 10, "issued_by": MANAGER} | invoice
        )

    return change


def _cancel(document: dict[str, Any]) -> None:
    _invoice(document)["cancelled"] = {"by": MANAGER, "reason": "Raised on the wrong course"}


def _then(*changes: Any) -> Any:
    """Apply ``changes`` in order."""

    def change(document: dict[str, Any]) -> None:
        for each in changes:
            each(document)

    return change


@pytest.mark.parametrize(
    ("change", "message"),
    [
        # Fee structures
        (_set("structure.created_by", OFFICER), "fee_structure.manage for all campuses"),
        (_set("structure.course", "XYZ"), "seed course"),
        (_set("structure.items", [{"fee_head": "Tuition", "amount_minor": 1.5}]), "integer"),
        (
            _set("structure.items", [*ITEMS, {"fee_head": "tuition", "amount_minor": 1}]),
            "duplicate_fee_head",
        ),
        (
            lambda d: _institute(d)["fee_structures"].append(
                _institute(d)["fee_structures"][0] | {"key": "DNS-again"}
            ),
            "one ACTIVE fee structure per course",
        ),
        # Fee invoices
        (_set("invoice.application", "A9"), "ADMITTED seed application"),
        (_set("invoice.application", "A3"), "ADMITTED seed application"),  # only approved
        (_set("invoice.structure", "GPR"), "fee structure of the admission's course"),
        (_set("structure.status", "DRAFT"), "issued from the course's ACTIVE structure"),
        (_set("structure.status", "ARCHIVED"), "issued from the course's ACTIVE structure"),
        (_set("invoice.issued_by", COUNSELLOR), "does not hold invoice.issue"),
        (_add_invoice(application="A2", issued_by=OFFICER), "invoice.issue for campus CLT"),
        (_add_invoice(application="A1"), "must be cancelled first"),
        (
            _set("invoice.lines", [{"fee_head": "Tuition", "amount_minor": 1}]),
            "adjustment_reason: required for adjusted lines only",
        ),
        (_set("invoice.adjustment_reason", "Scholarship"), "required for adjusted lines only"),
        (_set("invoice.due_in_days", True), "integer"),
        # Payments
        (_set("payment.amount_minor", TOTAL + 1), "more than the balance"),
        (_set("payment.amount_minor", 0), "more than 0"),
        (_set("payment.status", "PENDING"), "confirmed on record"),
        (_set("payment.method", "UPI"), "reference: required except for cash"),
        (_set("payment.received_days_ago", -1), "received, not due"),
        (_set("payment.recorded_by", COUNSELLOR), "does not hold payment.record"),
        (_set("payment.confirmed_by", MANAGER), "confirmed on record by its recorder"),
        (_set("payment.status", "REVERSED"), "reason: required for failed and reversed"),
        (
            lambda d: _payment(d).update(
                status="REVERSED", reason="Entered twice", closed_by=OFFICER
            ),
            "does not hold payment.reverse",
        ),
        (
            lambda d: _payment(d).update(
                status="REVERSED", reason="Entered twice", recorded_by=MANAGER, closed_by=MANAGER
            ),
            "never reversed by its recorder",
        ),
        (_set("payment.closed_by", MANAGER), "for failed or reversed payments only"),
        (
            _add_payment(
                amount_minor=TOTAL - 5_000_000,
                method="CHEQUE",
                reference="Cheque 1",
                status="PENDING",
            ),
            None,  # fits exactly: valid
        ),
        (
            _then(
                _add_payment(
                    amount_minor=TOTAL - 5_000_000,
                    method="CHEQUE",
                    reference="Cheque 1",
                    status="PENDING",
                ),
                _add_payment(amount_minor=1, method="CASH", status="CONFIRMED"),
            ),
            "more than the balance",  # the pending cheque counts
        ),
        (
            _add_payment(amount_minor=1, method="DEMAND_DRAFT", reference="DD 1", status="FAILED"),
            "reason: required",
        ),
        # Cancellation
        (_cancel, "fail or reverse every payment first"),
        (
            _then(
                _cancel,
                lambda d: _payment(d).update(
                    status="REVERSED", reason="Entered twice", closed_by=MANAGER
                ),
                lambda d: _invoice(d)["cancelled"].update(by=OFFICER),
            ),
            "does not hold invoice.cancel",
        ),
    ],
)
def test_invalid_finance_is_refused(change: Any, message: str | None) -> None:
    document = _document()
    change(document)
    if message is None:
        parse_seed(document)
        return
    with pytest.raises(SeedError, match=message):
        parse_seed(document)


def test_a_cancelled_invoice_may_be_replaced_and_name_an_archived_structure() -> None:
    document = _document()
    institute = _institute(document)
    institute["fee_structures"].insert(
        0,
        {
            "key": "DNS-old",
            "course": "DNS",
            "name": "DNS fees 2025-26",
            "status": "ARCHIVED",
            "created_by": MANAGER,
            "items": [{"fee_head": "Tuition", "amount_minor": 19_000_000}],
        },
    )
    first = _invoice(document)
    first |= {"structure": "DNS-old", "payments": []}
    first["cancelled"] = {"by": MANAGER, "reason": "Issued on last year's fee structure"}
    institute["invoices"].append(
        {"key": "I2", "application": "A1", "structure": "DNS", "due_in_days": 10}
        | {"issued_by": MANAGER}
    )
    (parsed,) = parse_seed(document)
    assert [i.status for i in parsed.finance.invoices] == [
        InvoiceStatus.CANCELLED,
        InvoiceStatus.ISSUED,
    ]
    # Dropped structure lines are kept at zero; the reason is then required.
    institute["invoices"][1]["lines"] = [{"fee_head": "Tuition", "amount_minor": 20_000_000}]
    with pytest.raises(SeedError, match="adjustment_reason"):
        parse_seed(document)
    institute["invoices"][1]["adjustment_reason"] = "Day scholar: no hostel and mess"
    (parsed,) = parse_seed(document)
    replacement = parsed.finance.invoices[1]
    assert [(line.fee_head, line.amount_minor) for line in replacement.lines] == [
        ("Tuition", 20_000_000),
        ("Hostel and mess", 0),
    ]
