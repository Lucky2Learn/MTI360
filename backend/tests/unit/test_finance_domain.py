"""Finance-lite rules (Phase 02-5; ADR-0022 §4-§7, addendum R3). Pure: no database."""

import pytest

from app.modules.finance.domain import (
    CLEARANCE_METHODS,
    FEE_STRUCTURE_TRANSITIONS,
    MAX_AMOUNT_MINOR,
    PAYMENT_TRANSITIONS,
    FeeItem,
    FeeStructureStatus,
    InvoiceLine,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
    clean_label,
    initial_payment_status,
    invoice_lines,
    invoice_status,
    is_adjusted,
    items_problems,
    lines_total,
    request_hash,
)

STRUCTURE = (
    FeeItem("Tuition", 25_000_000),
    FeeItem("Hostel", 6_000_000),
    FeeItem("Uniform", 850_000),
)


def test_unchanged_lines_copy_the_structure_and_are_not_adjusted() -> None:
    lines = invoice_lines(STRUCTURE, STRUCTURE)
    assert lines == [
        InvoiceLine(1, "Tuition", 25_000_000, 25_000_000),
        InvoiceLine(2, "Hostel", 6_000_000, 6_000_000),
        InvoiceLine(3, "Uniform", 850_000, 850_000),
    ]
    assert not is_adjusted(lines)
    assert lines_total(lines) == 31_850_000


def test_adjusted_dropped_and_added_lines_keep_the_original_amounts() -> None:
    requested = (
        FeeItem("  tuition ", 20_000_000),  # matched without regard to case or spacing
        FeeItem("Uniform", 850_000),
        FeeItem("Medical examination", 150_000),  # added at issue
    )
    lines = invoice_lines(STRUCTURE, requested)
    assert lines == [
        InvoiceLine(1, "Tuition", 20_000_000, 25_000_000),
        InvoiceLine(2, "Hostel", 0, 6_000_000),  # left out: kept at zero
        InvoiceLine(3, "Uniform", 850_000, 850_000),
        InvoiceLine(4, "Medical examination", 150_000, None),
    ]
    assert [line.adjusted for line in lines] == [True, True, False, True]
    assert is_adjusted(lines)
    assert lines_total(lines) == 21_000_000


def test_a_zero_added_line_still_counts_as_an_adjustment() -> None:
    assert is_adjusted(invoice_lines(STRUCTURE, (*STRUCTURE, FeeItem("Library", 0))))


def test_item_problems() -> None:
    assert items_problems(STRUCTURE) == []
    assert items_problems(()) == ["line_count", "total_out_of_range"]
    assert items_problems([FeeItem(f"Head {n}", 1) for n in range(31)]) == ["line_count"]
    assert items_problems((FeeItem("Tuition", 1), FeeItem("TUITION", 2))) == ["duplicate_fee_head"]
    assert items_problems((FeeItem("Tuition", -1),)) == ["amount_out_of_range"]
    assert items_problems((FeeItem("Tuition", MAX_AMOUNT_MINOR + 1),)) == ["amount_out_of_range"]
    assert items_problems((FeeItem("Tuition", 0),)) == ["total_out_of_range"]
    assert items_problems((FeeItem("A", MAX_AMOUNT_MINOR), FeeItem("B", 1))) == [
        "total_out_of_range"
    ]


@pytest.mark.parametrize(
    ("paid", "status"),
    [
        (0, InvoiceStatus.ISSUED),
        (1, InvoiceStatus.PARTIALLY_PAID),
        (9_999, InvoiceStatus.PARTIALLY_PAID),
        (10_000, InvoiceStatus.PAID),
    ],
)
def test_invoice_status_follows_the_confirmed_amount(paid: int, status: InvoiceStatus) -> None:
    assert invoice_status(10_000, paid) is status


@pytest.mark.parametrize("paid", [-1, 10_001])
def test_invoice_status_refuses_impossible_amounts(paid: int) -> None:
    with pytest.raises(ValueError, match="out of range"):
        invoice_status(10_000, paid)


def test_only_cheques_and_demand_drafts_wait_for_clearance() -> None:
    assert {PaymentMethod.CHEQUE, PaymentMethod.DEMAND_DRAFT} == CLEARANCE_METHODS
    for method in PaymentMethod:
        expected = PaymentStatus.PENDING if method in CLEARANCE_METHODS else PaymentStatus.CONFIRMED
        assert initial_payment_status(method) is expected


def test_payment_and_structure_transitions() -> None:
    allowed = {
        (PaymentStatus.PENDING, PaymentStatus.CONFIRMED),
        (PaymentStatus.PENDING, PaymentStatus.FAILED),
        (PaymentStatus.CONFIRMED, PaymentStatus.REVERSED),
    }
    for source in PaymentStatus:
        for target in PaymentStatus:
            assert PAYMENT_TRANSITIONS.allows(source, target) is ((source, target) in allowed)
    assert FEE_STRUCTURE_TRANSITIONS.targets(FeeStructureStatus.DRAFT) == {
        FeeStructureStatus.ACTIVE,
        FeeStructureStatus.ARCHIVED,
    }
    assert FEE_STRUCTURE_TRANSITIONS.targets(FeeStructureStatus.ACTIVE) == {
        FeeStructureStatus.ARCHIVED
    }
    assert FEE_STRUCTURE_TRANSITIONS.targets(FeeStructureStatus.ARCHIVED) == frozenset()


def test_labels_are_collapsed_and_bounded() -> None:
    assert clean_label("  Hostel   fee ", 100) == "Hostel fee"
    assert clean_label("   ", 100) is None
    assert clean_label("x" * 101, 100) is None


def test_the_request_hash_is_canonical_and_excludes_the_key() -> None:
    payload = {"amount_minor": 500_000, "method": "UPI", "reference": "UTR 4471"}
    first = request_hash("record_payment", payload)
    assert len(first) == 64
    assert request_hash("record_payment", dict(reversed(payload.items()))) == first
    assert request_hash("issue_invoice", payload) != first
    assert request_hash("record_payment", {**payload, "amount_minor": 500_001}) != first
    for excluded in ("idempotency_key", "version"):
        with pytest.raises(ValueError, match="excludes"):
            request_hash("record_payment", {**payload, excluded: 1})
