"""Development seed contract for batches (Phase 02-6; ADR-0025).

The committed file covers the demo (an open batch with seats, a full one, a
closed one, several students, payment overrides, a transfer), and the batches
section is refused, before anything is written, wherever the API would refuse
the same history: active course, campus, code, capacity, permissions and campus
scope, the admission's course and campus, one allocation per admission, seats
(transfers included), the payment gate (decision B), cancelling with students.
"""

import copy
from collections import Counter
from typing import Any

import pytest

from app.modules.batches.domain import BatchStatus, InvoiceState
from app.seed import DEFAULT_SEED_FILE, SeedError, load_seed, parse_seed

OWNER = "owner@malabar-seafarers.example"
MANAGER = "admissions@malabar-seafarers.example"  # Admissions manager, all campuses
FINANCE = "accounts@malabar-seafarers.example"
COUNSELLOR = "counsellor@malabar-seafarers.example"  # KOC only, reads batches
COORDINATOR = "coordinator@malabar-seafarers.example"  # Administrator, CLT only


def _member(email: str, role: str, campuses: list[str] | None = None) -> dict[str, Any]:
    member: dict[str, Any] = {"email": email, "display_name": "Fictitious Person", "role": role}
    if campuses:
        member |= {"campus_scope": "SELECTED", "campuses": campuses}
    return member


def _application(key: str, campus: str, mobile: str, course: str = "DNS") -> dict[str, Any]:
    return {
        "key": key,
        "course": course,
        "campus": campus,
        "created_by": OWNER,
        "reviewed_by": OWNER,
        "status": "ADMITTED",
        "full_name": "Fictitious Cadet",
        "mobile": f"+91 90000 10{mobile}",
        "date_of_birth": "2007-01-01",
        "highest_qualification": "12th PCM, 2025",
        "declared": True,
        "documents": [{"type": "PASSPORT", "status": "VERIFIED"}],
    }


def _batch(key: str, campus: str = "KOC", **changes: Any) -> dict[str, Any]:
    return {
        "key": key,
        "code": f"DNS-{key}",
        "course": "DNS",
        "campus": campus,
        "name": f"DNS Batch {key}",
        "starts_in_days": 30,
        "duration_days": 364,
        "capacity": 2,
        "status": "OPEN",
        "created_by": MANAGER,
        **changes,
    }


def _document() -> dict[str, Any]:
    """A1 (KOC) has a fully paid invoice, A2 (KOC) none, A3 (CLT) none."""
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
                    _member(MANAGER, "ADMISSIONS_MANAGER"),
                    _member(FINANCE, "FINANCE_MANAGER"),
                    _member(COUNSELLOR, "COUNSELLOR", ["KOC"]),
                    _member(COORDINATOR, "ADMIN", ["CLT"]),
                ],
                "courses": [
                    {
                        "code": "DNS",
                        "name": "Diploma in Nautical Science",
                        "category": "PRE_SEA",
                        "status": "ACTIVE",
                    },
                    {
                        "code": "AFF",
                        "name": "Fire Fighting",
                        "category": "POST_SEA",
                        "status": "DRAFT",
                    },
                ],
                "applications": [
                    _application("A1", "KOC", "901"),
                    _application("A2", "KOC", "902"),
                    _application("A3", "CLT", "903"),
                ],
                "fee_structures": [
                    {
                        "key": "DNS",
                        "course": "DNS",
                        "name": "DNS fees 2026-27",
                        "status": "ACTIVE",
                        "created_by": FINANCE,
                        "items": [{"fee_head": "Tuition", "amount_minor": 10_000_000}],
                    }
                ],
                "invoices": [
                    {
                        "key": "I1",
                        "application": "A1",
                        "structure": "DNS",
                        "due_in_days": 30,
                        "issued_by": FINANCE,
                        "payments": [
                            {
                                "amount_minor": 10_000_000,
                                "method": "CASH",
                                "received_days_ago": 1,
                                "recorded_by": FINANCE,
                                "status": "CONFIRMED",
                            }
                        ],
                    }
                ],
                "batches": [_batch("K1"), _batch("K2"), _batch("C1", "CLT")],
                "allocations": [
                    {"batch": "K1", "application": "A1", "allocated_by": MANAGER},
                    {
                        "batch": "K1",
                        "application": "A2",
                        "allocated_by": MANAGER,
                        "override_reason": "Scholarship approved by the principal.",
                        "transfer": {"to": "K2", "reason": "Evening batch.", "by": MANAGER},
                    },
                ],
            }
        ]
    }


def _institute(document: dict[str, Any]) -> dict[str, Any]:
    return document["institutes"][0]  # type: ignore[no-any-return]


def test_the_minimal_document_is_valid() -> None:
    (institute,) = parse_seed(_document())
    paid, overridden = institute.batches.allocations
    assert (paid.invoice_state, paid.override_reason) == (InvoiceState.PAID, None)
    assert (overridden.invoice_state, overridden.outstanding_minor) == (
        InvoiceState.NO_INVOICE,
        None,
    )
    assert overridden.transfer is not None
    assert overridden.transfer.to == "K2"


def test_the_committed_seed_covers_the_batch_demo() -> None:
    konkan, coromandel = load_seed(DEFAULT_SEED_FILE)
    batches = {b.key: b for b in konkan.batches.batches}
    seats = Counter(
        (a.transfer.to if a.transfer else a.batch)
        for a in konkan.batches.allocations
        if a.withdraw is None
    )
    statuses = Counter(b.status for b in batches.values())
    assert statuses[BatchStatus.OPEN] >= 2
    assert statuses[BatchStatus.CLOSED] >= 1
    # An open batch with free seats and an open batch at full capacity.
    assert any(
        b.status is BatchStatus.OPEN and 0 < seats[k] < b.capacity for k, b in batches.items()
    )
    assert any(b.status is BatchStatus.OPEN and seats[k] == b.capacity for k, b in batches.items())
    allocations = konkan.batches.allocations
    assert len(allocations) >= 4
    assert any(a.override_reason is None for a in allocations)  # paid in full
    states = {a.invoice_state for a in allocations if a.override_reason}
    assert {InvoiceState.PARTIALLY_PAID, InvoiceState.NO_INVOICE} <= states
    assert any(a.transfer is not None for a in allocations)
    # Admitted students left unallocated for a live allocation demo.
    admitted = {a.key for a in konkan.applications if a.status.value == "ADMITTED"}
    assert admitted - {a.application for a in allocations}
    assert coromandel.batches.allocations


def _broken(change: Any) -> dict[str, Any]:
    document = copy.deepcopy(_document())
    change(_institute(document))
    return document


def _set(path: tuple[str, int], **values: Any) -> Any:
    def change(institute: dict[str, Any]) -> None:
        if values.pop("_delete", None):
            for key in list(values):
                institute[path[0]][path[1]].pop(key, None)
        else:
            institute[path[0]][path[1]].update(values)

    return change


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (_set(("batches", 0), course="AFF"), r"ACTIVE course"),
        (_set(("batches", 0), campus="TVM"), r"campus of the institute"),
        (_set(("batches", 1), code="dns-k1"), r"unique batch code"),
        (_set(("batches", 0), capacity=0), r"from 1 to 500"),
        (_set(("batches", 0), capacity=501), r"from 1 to 500"),
        (_set(("batches", 0), created_by=COUNSELLOR), r"needs batch.manage"),
        (_set(("batches", 0), created_by=COORDINATOR), r"needs batch.manage at KOC"),
        (_set(("allocations", 0), batch="C1"), r"course and campus must be the batch's"),
        (_set(("allocations", 0), application="A9"), r"ADMITTED application"),
        (_set(("allocations", 0), allocated_by=COUNSELLOR), r"needs batch.allocate"),
        (_set(("allocations", 0), override_reason="Not needed"), r"fees are paid"),
        (_set(("allocations", 1), _delete=True, override_reason=None), r"override reason"),
        (_set(("allocations", 1), transfer={"to": "C1", "reason": "x", "by": MANAGER}), "same"),
        (_set(("allocations", 1), transfer={"to": "K2", "by": MANAGER}), r"reason"),
        (_set(("batches", 0), status="CANCELLED"), r"cancelled with students"),
        (
            lambda i: i["allocations"].append(
                {"batch": "K2", "application": "A1", "allocated_by": MANAGER}
            ),
            r"allocated once only",
        ),
        (
            lambda i: i["batches"][1].update(capacity=1) or i["batches"][0].update(capacity=1),
            r"is full",
        ),
    ],
)
def test_invalid_batches_are_refused(change: Any, message: str) -> None:
    with pytest.raises(SeedError, match=message):
        parse_seed(_broken(change))


def test_a_withdrawal_frees_the_seat_and_a_cancelled_empty_batch_is_allowed() -> None:
    document = _document()
    institute = _institute(document)
    institute["batches"][0]["capacity"] = 1
    institute["allocations"][0]["withdraw"] = {"reason": "Left the course.", "by": MANAGER}
    institute["batches"].append(_batch("K3", status="CANCELLED", status_reason="Too few"))
    (parsed,) = parse_seed(document)
    assert parsed.batches.allocations[0].withdraw is not None
