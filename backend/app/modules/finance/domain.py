"""Finance-lite rules (Phase 02-5; ADR-0022). Pure: no I/O, no framework imports.

* Amounts are **integer paise** (``*_minor``), currency ``INR`` only (§6).
  Totals and balances are computed here, never accepted from a client.
* Fee invoices are **non-tax** (§2). Lines are copied from the course's
  active fee structure at issue and may be adjusted; an adjusted invoice
  needs a reason, and a structure line left out is kept at zero (§7).
* Payments: cash, UPI and bank transfer are confirmed when recorded;
  cheques and demand drafts are ``PENDING`` until cleared (§4). Only
  ``CONFIRMED`` payments count toward ``paid_minor``.
* The idempotency request hash covers the normalised business payload, never
  the key itself (addendum R3).
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from app.core.transitions import TransitionTable

CURRENCY: Final = "INR"
MAX_AMOUNT_MINOR: Final = 100_000_000_000
"""₹1,00,00,00,000.00 per line, invoice or payment: far above any fee, JavaScript-safe."""
NAME_MAX_LENGTH: Final = 200
FEE_HEAD_MAX_LENGTH: Final = 100
REASON_MAX_LENGTH: Final = 500
REFERENCE_MAX_LENGTH: Final = 100
LINES_MAX: Final = 30
REQUEST_HASH_LENGTH: Final = 64


class FeeStructureStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class InvoiceStatus(StrEnum):
    ISSUED = "ISSUED"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class PaymentMethod(StrEnum):
    CASH = "CASH"
    UPI = "UPI"
    BANK_TRANSFER = "BANK_TRANSFER"
    CHEQUE = "CHEQUE"
    DEMAND_DRAFT = "DEMAND_DRAFT"


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class ActivityKind(StrEnum):
    ISSUED = "ISSUED"
    CANCELLED = "CANCELLED"
    PAYMENT_RECORDED = "PAYMENT_RECORDED"
    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAYMENT_REVERSED = "PAYMENT_REVERSED"


CLEARANCE_METHODS: Final = frozenset({PaymentMethod.CHEQUE, PaymentMethod.DEMAND_DRAFT})
"""Recorded ``PENDING``; confirmed after clearance or failed with a reason (§4)."""
OPEN_PAYMENT_STATUSES: Final = frozenset({PaymentStatus.PENDING, PaymentStatus.CONFIRMED})
"""A fee invoice with a payment in either status cannot be cancelled (§5)."""

FEE_STRUCTURE_TRANSITIONS: Final = TransitionTable[FeeStructureStatus](
    {
        FeeStructureStatus.DRAFT: {FeeStructureStatus.ACTIVE, FeeStructureStatus.ARCHIVED},
        FeeStructureStatus.ACTIVE: {FeeStructureStatus.ARCHIVED},
    }
)
PAYMENT_TRANSITIONS: Final = TransitionTable[PaymentStatus](
    {
        PaymentStatus.PENDING: {PaymentStatus.CONFIRMED, PaymentStatus.FAILED},
        PaymentStatus.CONFIRMED: {PaymentStatus.REVERSED},
    }
)


def initial_payment_status(method: PaymentMethod) -> PaymentStatus:
    return PaymentStatus.PENDING if method in CLEARANCE_METHODS else PaymentStatus.CONFIRMED


def invoice_status(total_minor: int, paid_minor: int) -> InvoiceStatus:
    """The status of a live fee invoice, from what has been confirmed (never set by hand)."""
    if not 0 <= paid_minor <= total_minor:
        raise ValueError("paid amount out of range")
    if paid_minor == 0:
        return InvoiceStatus.ISSUED
    if paid_minor < total_minor:
        return InvoiceStatus.PARTIALLY_PAID
    return InvoiceStatus.PAID


# --- Text ----------------------------------------------------------------------------------


def clean_label(raw: str, max_length: int) -> str | None:
    """Whitespace-collapsed text of 1..``max_length`` characters, or ``None``."""
    value = " ".join(raw.split())
    return value if 0 < len(value) <= max_length else None


def head_key(fee_head: str) -> str:
    """Fee heads are matched without regard to case or spacing."""
    return " ".join(fee_head.split()).casefold()


def valid_amount(value: int, *, positive: bool) -> bool:
    return (value > 0 if positive else value >= 0) and value <= MAX_AMOUNT_MINOR


# --- Fee structure items and invoice lines -----------------------------------------------


@dataclass(frozen=True, slots=True)
class FeeItem:
    fee_head: str
    amount_minor: int


@dataclass(frozen=True, slots=True)
class InvoiceLine:
    position: int
    fee_head: str
    amount_minor: int
    structure_amount_minor: int | None
    """The fee structure's amount; ``None`` for a line added at issue."""

    @property
    def adjusted(self) -> bool:
        return self.structure_amount_minor != self.amount_minor


def items_problems(items: Sequence[FeeItem]) -> list[str]:
    """Problem codes of a fee structure's (or an invoice's requested) lines; empty when valid."""
    problems: list[str] = []
    if not 1 <= len(items) <= LINES_MAX:
        problems.append("line_count")
    if len({head_key(item.fee_head) for item in items}) != len(items):
        problems.append("duplicate_fee_head")
    if not all(valid_amount(item.amount_minor, positive=False) for item in items):
        problems.append("amount_out_of_range")
    elif not valid_amount(sum(item.amount_minor for item in items), positive=True):
        problems.append("total_out_of_range")
    return problems


def invoice_lines(structure: Sequence[FeeItem], requested: Sequence[FeeItem]) -> list[InvoiceLine]:
    """The lines of a fee invoice: every structure line (left out → zero), then added lines.

    A requested line matches a structure line by fee head (case and spacing
    ignored) and keeps the structure's spelling. Structure order first, so the
    original stays readable; added lines follow in request order.
    """
    wanted = {head_key(item.fee_head): item for item in requested}
    lines: list[InvoiceLine] = []
    for item in structure:
        match = wanted.pop(head_key(item.fee_head), None)
        amount = match.amount_minor if match is not None else 0
        lines.append(InvoiceLine(len(lines) + 1, item.fee_head, amount, item.amount_minor))
    for item in wanted.values():
        lines.append(InvoiceLine(len(lines) + 1, item.fee_head, item.amount_minor, None))
    return lines


IssuedLine = InvoiceLine
"""The domain line, named apart from the ``invoice_lines`` model where both are used."""


def lines_total(lines: Sequence[InvoiceLine]) -> int:
    return sum(line.amount_minor for line in lines)


def is_adjusted(lines: Sequence[InvoiceLine]) -> bool:
    return any(line.adjusted for line in lines)


# --- Idempotency (addendum R3) ------------------------------------------------------------


def request_hash(operation: str, payload: Mapping[str, object]) -> str:
    """SHA-256 of the canonical JSON of the normalised business payload.

    The caller passes only cleaned business values (strings, integers, lists
    and mappings of them): never the idempotency key or the version.
    """
    if "idempotency_key" in payload or "version" in payload:
        raise ValueError("the request hash excludes the idempotency key and the version")
    canonical = json.dumps(
        {"operation": operation, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
