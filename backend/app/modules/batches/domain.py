"""Batch and allocation rules (Phase 02-6). Pure: no I/O, no framework imports.

* A **batch** is one intake of one course at one campus. Course and campus are
  fixed at creation. New batches are ``OPEN``; ``CLOSED`` batches may reopen;
  ``CANCELLED`` is final and allowed only without active allocations.
* An **allocation** places one admission in one batch. At most one allocation
  per admission is ``ACTIVE``; history is never deleted (``ENDED`` rows keep
  their end reason). Allocation moves the admission ``ADMITTED → ENROLLED``;
  withdrawal moves it back; a transfer keeps it ``ENROLLED``.
* Payment gate (approved decision B): a normal allocation needs the
  admission's live fee invoice to be ``PAID``. Otherwise an allocator may
  override with a reason; the override records the outstanding amount. A
  missing or cancelled invoice is never treated as paid.
"""

import re
from datetime import date
from enum import StrEnum
from typing import Final

from app.core.transitions import TransitionTable

CODE_PATTERN: Final = "^[A-Z0-9][A-Z0-9-]*$"
CODE_MAX_LENGTH: Final = 32
NAME_MAX_LENGTH: Final = 200
INTAKE_MAX_LENGTH: Final = 100
REASON_MAX_LENGTH: Final = 500
CAPACITY_MIN: Final = 1
CAPACITY_MAX: Final = 500
_CODE = re.compile(CODE_PATTERN)


class BatchStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class AllocationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"


class EndReason(StrEnum):
    TRANSFERRED = "TRANSFERRED"
    WITHDRAWN = "WITHDRAWN"


class PaymentBasis(StrEnum):
    """Why the allocation was allowed with respect to fees."""

    PAID = "PAID"
    """The live fee invoice was fully paid."""
    OVERRIDE = "OVERRIDE"
    """Fees outstanding; an allocator overrode the gate with a reason."""
    TRANSFER = "TRANSFER"
    """A transfer: the gate was decided by the first allocation."""


class InvoiceState(StrEnum):
    """The admission's fee position at allocation time (recorded with an override)."""

    PAID = "PAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    ISSUED = "ISSUED"
    NO_INVOICE = "NO_INVOICE"
    """No live invoice: none issued, or only cancelled ones."""


class ActivityKind(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    ALLOCATED = "ALLOCATED"
    TRANSFERRED_OUT = "TRANSFERRED_OUT"
    TRANSFERRED_IN = "TRANSFERRED_IN"
    WITHDRAWN = "WITHDRAWN"


STUDENT_TIMELINE_KINDS: Final = (
    ActivityKind.ALLOCATED,
    ActivityKind.TRANSFERRED_IN,
    ActivityKind.WITHDRAWN,
)
"""Allocation activity shown on Student 360 (``TRANSFERRED_OUT`` duplicates ``_IN``)."""

INITIAL_STATUS: Final = BatchStatus.OPEN

BATCH_TRANSITIONS: Final = TransitionTable[BatchStatus](
    {
        BatchStatus.OPEN: {BatchStatus.CLOSED, BatchStatus.CANCELLED},
        BatchStatus.CLOSED: {BatchStatus.OPEN, BatchStatus.CANCELLED},
        BatchStatus.CANCELLED: set(),
    }
)


def normalize_code(raw: str) -> str | None:
    """The canonical batch code (trimmed, upper case), or ``None`` when the format is wrong."""
    code = raw.strip().upper()
    if not code or len(code) > CODE_MAX_LENGTH or not _CODE.fullmatch(code):
        return None
    return code


def clean_name(raw: str, limit: int = NAME_MAX_LENGTH) -> str | None:
    """Whitespace-collapsed text of 1..``limit`` characters, or ``None``."""
    name = " ".join(raw.split())
    return name if 0 < len(name) <= limit else None


def clean_reason(raw: str | None) -> str | None:
    """A trimmed reason of 1-500 characters, or ``None``."""
    if raw is None:
        return None
    text = raw.strip()
    return text if 0 < len(text) <= REASON_MAX_LENGTH else None


def dates_valid(start: date, end: date) -> bool:
    return end >= start


def capacity_valid(capacity: int) -> bool:
    return CAPACITY_MIN <= capacity <= CAPACITY_MAX


def available_seats(capacity: int, allocated: int) -> int:
    return max(capacity - allocated, 0)


def invoice_state(status: str | None) -> InvoiceState:
    """The fee position from the live invoice's status (``None``: no live invoice)."""
    if status is None or status == "CANCELLED":
        return InvoiceState.NO_INVOICE
    return InvoiceState(status)


def outstanding_minor(total_minor: int | None, paid_minor: int | None) -> int | None:
    """What is still owed on the live invoice; ``None`` when there is no invoice."""
    if total_minor is None:
        return None
    return max(total_minor - (paid_minor or 0), 0)
