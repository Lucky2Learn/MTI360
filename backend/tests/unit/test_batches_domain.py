"""Batch and allocation rules (Phase 02-6): pure functions and the status table."""

from datetime import date

import pytest

from app.modules.batches.domain import (
    BATCH_TRANSITIONS,
    STUDENT_TIMELINE_KINDS,
    ActivityKind,
    BatchStatus,
    InvoiceState,
    available_seats,
    capacity_valid,
    clean_name,
    clean_reason,
    dates_valid,
    invoice_state,
    normalize_code,
    outstanding_minor,
)

OPEN, C, X = BatchStatus.OPEN, BatchStatus.CLOSED, BatchStatus.CANCELLED


@pytest.mark.parametrize(
    ("source", "target", "allowed"),
    [
        (OPEN, C, True),
        (OPEN, X, True),
        (C, OPEN, True),
        (C, X, True),
        (X, OPEN, False),
        (X, C, False),
        (OPEN, OPEN, False),
    ],
)
def test_batch_transitions(source: BatchStatus, target: BatchStatus, allowed: bool) -> None:
    assert BATCH_TRANSITIONS.allows(source, target) is allowed


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (" dns-2026-b ", "DNS-2026-B"),
        ("STCW7", "STCW7"),
        ("-DNS", None),
        ("DNS 2026", None),
        ("", None),
        ("A" * 33, None),
    ],
)
def test_codes(raw: str, code: str | None) -> None:
    assert normalize_code(raw) == code


def test_capacity_dates_and_seats() -> None:
    assert [capacity_valid(n) for n in (0, 1, 500, 501)] == [False, True, True, False]
    assert dates_valid(date(2026, 7, 1), date(2026, 7, 1))
    assert not dates_valid(date(2026, 7, 2), date(2026, 7, 1))
    assert available_seats(24, 18) == 6
    assert available_seats(24, 30) == 0


def test_text_cleaning() -> None:
    assert clean_name("  DNS   Batch  ") == "DNS Batch"
    assert clean_name("   ") is None
    assert clean_name("x" * 101, 100) is None
    assert clean_reason("  Sponsor letter  ") == "Sponsor letter"
    assert clean_reason("   ") is None
    assert clean_reason(None) is None
    assert clean_reason("x" * 501) is None


def test_the_payment_position() -> None:
    # A missing or cancelled invoice is never paid.
    assert invoice_state(None) is InvoiceState.NO_INVOICE
    assert invoice_state("CANCELLED") is InvoiceState.NO_INVOICE
    assert invoice_state("PAID") is InvoiceState.PAID
    assert invoice_state("PARTIALLY_PAID") is InvoiceState.PARTIALLY_PAID
    assert invoice_state("ISSUED") is InvoiceState.ISSUED
    assert outstanding_minor(None, None) is None
    assert outstanding_minor(31_850_000, 10_000_000) == 21_850_000
    assert outstanding_minor(31_850_000, 31_850_000) == 0


def test_the_student_timeline_shows_each_move_once() -> None:
    assert ActivityKind.TRANSFERRED_OUT not in STUDENT_TIMELINE_KINDS
    assert set(STUDENT_TIMELINE_KINDS) == {
        ActivityKind.ALLOCATED,
        ActivityKind.TRANSFERRED_IN,
        ActivityKind.WITHDRAWN,
    }
