"""Fee invoices, payments and receipts (Phase 02-5; ADR-0022 §2-§10, addendum R1-R3).

* **Issue** (``invoice.issue``): one non-tax fee invoice for an admission the
  caller may see. The lines are the course's active fee structure with any
  adjustment (reason required; dropped lines kept at zero). The admission row
  is locked, so issue for one admission is serialised: the idempotency key is
  checked first (a replay returns the original), then the one live invoice.
* **Record** (``payment.record``): cash, UPI and bank transfer are confirmed
  at once (receipt, balance); cheques and demand drafts are ``PENDING``. The
  invoice row is locked; overpayment, counting pending amounts, is refused.
* **Confirm / fail** a pending payment (``payment.record``); **reverse** a
  confirmed one (``payment.reverse``) — never by its recorder (422
  ``recorder_cannot_reverse``, after the permission and campus checks).
* **Cancel** (``invoice.cancel``): only without ``PENDING`` or ``CONFIRMED``
  payments; a replacement gets a new number.

Locks are taken in one order: admission, invoice, payment. ``paid_minor``
always equals the sum of ``CONFIRMED`` payments. Numbers come from the
financial-year sequences in the same transaction (gap-free). Every command
writes the finance activity and a ``domain`` audit event (amounts, methods,
statuses and flags; never names, references or reason text).
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import cast

from sqlalchemy import Table, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.activity import record_activity
from app.core.audit import AuditTarget, write_audit_event
from app.core.authz import Permission, authorize, campus_visible
from app.core.errors import (
    ConflictError,
    ErrorDetail,
    NotFoundError,
    RateLimitedError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.core.pagination import PageParams, SortField
from app.core.ratelimit import (
    Limit,
    RateLimiter,
    RateLimiterUnavailableError,
    RateLimitExceededError,
)
from app.core.sequences import SequenceName, next_number
from app.modules.finance import events
from app.modules.finance import invoice_repository as repo
from app.modules.finance.domain import (
    CURRENCY,
    LINES_MAX,
    MAX_AMOUNT_MINOR,
    PAYMENT_TRANSITIONS,
    REASON_MAX_LENGTH,
    REFERENCE_MAX_LENGTH,
    ActivityKind,
    FeeItem,
    InvoiceStatus,
    IssuedLine,
    PaymentMethod,
    PaymentStatus,
    clean_label,
    initial_payment_status,
    invoice_lines,
    invoice_status,
    is_adjusted,
    lines_total,
    request_hash,
)
from app.modules.finance.models import (
    FeeStructure,
    FinanceActivity,
    Invoice,
    InvoiceLine,
    Payment,
    Receipt,
)
from app.modules.finance.permissions import (
    INVOICE_CANCEL,
    INVOICE_ISSUE,
    INVOICE_READ,
    PAYMENT_RECORD,
    PAYMENT_REVERSE,
)
from app.modules.finance.repository import FeeStructureRepository
from app.modules.finance.service import clean_items, invalid_transition, structure_items
from app.modules.leads.service import Caller, caller

INVOICE_STALE = "This fee invoice was changed by someone else. Reload and try again."
PAYMENT_STALE = "This payment was changed by someone else. Reload and try again."
KEY_REUSED = ErrorDetail(
    field="idempotency_key",
    code="idempotency_key_reused",
    message="This request key was already used for a different request.",
)
PAYMENT_LIMIT = Limit(attempts=60, window_seconds=600)
"""Payments recorded per member per 10 minutes (readiness plan §7)."""
ACTIVITIES = cast(Table, FinanceActivity.__table__)


@dataclass(frozen=True, slots=True)
class InvoiceResource:
    tenant_id: uuid.UUID
    campus_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class IssueRequest:
    admission_id: uuid.UUID
    due_date: date
    lines: Sequence[FeeItem]
    adjustment_reason: str | None
    idempotency_key: uuid.UUID


@dataclass(frozen=True, slots=True)
class PaymentRequest:
    amount_minor: int
    method: PaymentMethod
    reference: str | None
    received_on: date
    idempotency_key: uuid.UUID


@dataclass(frozen=True, slots=True)
class Outcome:
    """The record a command produced (or, for a replay, produced before)."""

    id: uuid.UUID
    created: bool


def _detail(field: str, code: str, message: str) -> ErrorDetail:
    return ErrorDetail(field=field, code=code, message=message)


def _invalid(*details: ErrorDetail) -> ValidationFailedError:
    return ValidationFailedError(details=list(details))


def _reason(raw: str | None, field: str = "reason") -> str:
    reason = clean_label(raw or "", REASON_MAX_LENGTH)
    if reason is None:
        raise _invalid(_detail(field, "required", "Give a reason of up to 500 characters."))
    return reason


async def _activity(
    db: AsyncSession,
    who: Caller,
    invoice_id: uuid.UUID,
    kind: ActivityKind,
    details: dict[str, object],
) -> None:
    await record_activity(
        db,
        ACTIVITIES,
        subject_column="invoice_id",
        subject_id=invoice_id,
        kind=kind.value,
        actor_membership_id=who.membership_id,
        details=details,
    )


async def _visible_invoice(
    db: AsyncSession, who: Caller, invoice_id: uuid.UUID, permission: Permission
) -> Invoice:
    """The fee invoice, if it exists in the tenant and its campus is the caller's (404)."""
    found = await repo.invoice(db, who.tenant_id, invoice_id)
    if found is None:
        raise NotFoundError()
    authorize(who.context, permission, InvoiceResource(found.tenant_id, found.campus_id))
    return found


async def _locked_invoice(
    db: AsyncSession, who: Caller, invoice_id: uuid.UUID, permission: Permission
) -> Invoice:
    await _visible_invoice(db, who, invoice_id, permission)
    locked = await repo.invoice(db, who.tenant_id, invoice_id, lock=True)
    if locked is None:  # pragma: no cover - never deleted
        raise NotFoundError()
    return locked


async def _locked_payment(
    db: AsyncSession, who: Caller, payment_id: uuid.UUID, permission: Permission
) -> tuple[Payment, Invoice]:
    """The payment and its invoice, authorized by the invoice's campus, locked in order."""
    found = await repo.payment(db, who.tenant_id, payment_id)
    if found is None:
        raise NotFoundError()
    authorize(who.context, permission, InvoiceResource(found.tenant_id, found.campus_id))
    invoice = await repo.invoice(db, who.tenant_id, found.invoice_id, lock=True)
    payment = await repo.payment(db, who.tenant_id, payment_id, lock=True)
    if invoice is None or payment is None:  # pragma: no cover - never deleted
        raise NotFoundError()
    return payment, invoice


def _set_paid(invoice: Invoice, paid_minor: int) -> None:
    invoice.paid_minor = paid_minor
    invoice.status = invoice_status(invoice.total_minor, paid_minor).value


async def _issue_receipt(
    db: AsyncSession, who: Caller, invoice: Invoice, payment: Payment
) -> Receipt:
    """Confirm ``payment`` into the invoice's balance and issue its receipt (§3, §4)."""
    _set_paid(invoice, invoice.paid_minor + payment.amount_minor)
    receipt = Receipt(
        tenant_id=who.tenant_id,
        number=await next_number(db, SequenceName.RECEIPT),
        payment_id=payment.id,
        invoice_number=invoice.number,
        student_number=await repo.student_number(db, who.tenant_id, invoice.student_id),
        amount_minor=payment.amount_minor,
        currency=CURRENCY,
        method=payment.method,
    )
    db.add(receipt)
    await db.flush()
    return receipt


# --- Fee invoices ------------------------------------------------------------------------


async def issue_invoice(db: AsyncSession, request: IssueRequest) -> Outcome:
    who = await caller(db, INVOICE_ISSUE)
    requested, problems = clean_items(request.lines, "lines")
    reason: str | None = None
    if request.adjustment_reason is not None:
        reason = clean_label(request.adjustment_reason, REASON_MAX_LENGTH)
        if reason is None:
            problems.append(
                _detail("adjustment_reason", "invalid", "Give a reason of up to 500 characters.")
            )
    if request.due_date < await repo.today(db):
        problems.append(_detail("due_date", "in_the_past", "Choose today or a later due date."))
    if problems:
        raise _invalid(*problems)
    not_available = _detail(
        "admission_id", "admission_not_available", "Choose an admitted student of your campuses."
    )
    found = await repo.admission(db, who.tenant_id, request.admission_id, lock=False)
    if found is None or not campus_visible(found.campus_id, who.context):
        raise _invalid(not_available)
    admission = await repo.admission(db, who.tenant_id, request.admission_id, lock=True)
    if admission is None:  # pragma: no cover - never deleted
        raise _invalid(not_available)

    digest = request_hash(
        "issue_invoice",
        {
            "admission_id": str(admission.id),
            "due_date": request.due_date.isoformat(),
            "lines": [[item.fee_head, item.amount_minor] for item in requested],
            "adjustment_reason": reason,
        },
    )
    existing = await repo.invoice_by_key(db, who.tenant_id, request.idempotency_key)
    if existing is not None:
        if existing.request_hash != digest:
            raise ConflictError(details=[KEY_REUSED])
        return Outcome(existing.id, created=False)

    structure = await FeeStructureRepository(db).active_for(admission.course_id)
    if structure is None:
        raise _invalid(
            _detail(
                "admission_id",
                "no_active_fee_structure",
                "Activate a fee structure for this course first.",
            )
        )
    lines = invoice_lines(structure_items(structure), requested)
    total = lines_total(lines)
    if len(lines) > LINES_MAX:
        raise _invalid(_detail("lines", "line_count", "Use at most 30 lines."))
    if not 0 < total <= MAX_AMOUNT_MINOR:
        raise _invalid(_detail("lines", "total_out_of_range", "The total must be more than ₹0."))
    adjusted = is_adjusted(lines)
    if adjusted and reason is None:
        raise _invalid(
            _detail(
                "adjustment_reason",
                "required",
                "Give the reason for changing the fee structure's amounts.",
            )
        )
    if not adjusted and reason is not None:
        raise _invalid(
            _detail(
                "adjustment_reason",
                "not_adjusted",
                "Remove the reason: the lines match the fee structure.",
            )
        )
    if await repo.live_invoice_of(db, who.tenant_id, admission.id) is not None:
        raise ConflictError(
            details=[
                _detail(
                    "admission_id",
                    "live_invoice_exists",
                    "This admission already has a fee invoice. Cancel it to issue a new one.",
                )
            ]
        )
    invoice = await _new_invoice(db, who, admission, structure, request, lines, reason, digest)
    await _activity(
        db,
        who,
        invoice.id,
        ActivityKind.ISSUED,
        {
            "number": invoice.number,
            "total_minor": total,
            "structure_total_minor": structure.total_minor,
            "adjusted": adjusted,
            "line_count": len(lines),
            # Each line's structure and issued amounts are in the insert-only invoice_lines.
            "adjusted_fee_heads": [line.fee_head for line in lines if line.adjusted],
        },
    )
    await write_audit_event(
        db,
        events.INVOICE_ISSUED,
        target=AuditTarget("invoice", invoice.id),
        metadata={
            "total_minor": total,
            "structure_total_minor": structure.total_minor,
            "currency": CURRENCY,
            "adjusted": adjusted,
            "adjusted_line_count": sum(1 for line in lines if line.adjusted),
        },
    )
    return Outcome(invoice.id, created=True)


async def _new_invoice(
    db: AsyncSession,
    who: Caller,
    admission: repo.AdmissionRef,
    structure: FeeStructure,
    request: IssueRequest,
    built: Sequence[IssuedLine],
    reason: str | None,
    digest: str,
) -> Invoice:
    invoice = Invoice(
        tenant_id=who.tenant_id,
        number=await next_number(db, SequenceName.INVOICE),
        admission_id=admission.id,
        student_id=admission.student_id,
        course_id=admission.course_id,
        campus_id=admission.campus_id,
        fee_structure_id=structure.id,
        fee_structure_version=structure.version,
        structure_total_minor=structure.total_minor,
        total_minor=lines_total(built),
        paid_minor=0,
        currency=CURRENCY,
        due_date=request.due_date,
        adjusted=is_adjusted(built),
        adjustment_reason=reason,
        status=InvoiceStatus.ISSUED.value,
        issued_by_membership_id=who.membership_id,
        idempotency_key=request.idempotency_key,
        request_hash=digest,
    )
    db.add(invoice)
    try:
        await db.flush()
    except IntegrityError:  # a backstop: the admission lock serialises issue
        raise ConflictError(details=[KEY_REUSED]) from None
    for line in built:
        db.add(
            InvoiceLine(
                tenant_id=who.tenant_id,
                invoice_id=invoice.id,
                position=line.position,
                fee_head=line.fee_head,
                amount_minor=line.amount_minor,
                structure_amount_minor=line.structure_amount_minor,
            )
        )
    await db.flush()
    return invoice


async def cancel_invoice(
    db: AsyncSession, invoice_id: uuid.UUID, *, reason: str | None, version: int
) -> None:
    who = await caller(db, INVOICE_CANCEL)
    invoice = await _locked_invoice(db, who, invoice_id, INVOICE_CANCEL)
    if invoice.version != version:
        raise ConflictError(INVOICE_STALE)
    if invoice.status == InvoiceStatus.CANCELLED.value:
        raise invalid_transition("This fee invoice is already cancelled.")
    if await repo.open_payments(db, who.tenant_id, invoice.id):
        raise _invalid(
            _detail(
                "status",
                "open_payments",
                "Resolve the payments first: fail or confirm each pending cheque or demand "
                "draft, and reverse each confirmed payment.",
            )
        )
    clean = _reason(reason)
    invoice.status = InvoiceStatus.CANCELLED.value
    invoice.status_reason = clean
    invoice.cancelled_at = func.now()
    invoice.cancelled_by_membership_id = who.membership_id
    await db.flush()
    await _activity(db, who, invoice.id, ActivityKind.CANCELLED, {"reason": clean})
    await write_audit_event(
        db,
        events.INVOICE_CANCELLED,
        target=AuditTarget("invoice", invoice.id),
        metadata={"total_minor": invoice.total_minor, "currency": CURRENCY, "has_reason": True},
    )


# --- Payments ------------------------------------------------------------------------------


async def record_payment(
    db: AsyncSession, invoice_id: uuid.UUID, request: PaymentRequest, limiter: RateLimiter
) -> Outcome:
    who = await caller(db, PAYMENT_RECORD)
    try:
        await limiter.hit("membership", "payment_record", str(who.membership_id), PAYMENT_LIMIT)
    except RateLimitExceededError as error:
        raise RateLimitedError(retry_after=error.retry_after) from None
    except RateLimiterUnavailableError:
        raise ServiceUnavailableError() from None
    reference = (
        clean_label(request.reference, REFERENCE_MAX_LENGTH)
        if request.reference is not None
        else None
    )
    problems: list[ErrorDetail] = []
    if request.reference is not None and reference is None:
        problems.append(_detail("reference", "invalid", "Use up to 100 characters."))
    elif reference is None and request.method is not PaymentMethod.CASH:
        problems.append(
            _detail(
                "reference",
                "required",
                "Enter the UPI, bank, cheque or demand draft reference.",
            )
        )
    if request.received_on > await repo.today(db):
        problems.append(
            _detail("received_on", "in_the_future", "Enter the date the money was received.")
        )
    if problems:
        raise _invalid(*problems)
    invoice = await _locked_invoice(db, who, invoice_id, PAYMENT_RECORD)

    digest = request_hash(
        "record_payment",
        {
            "invoice_id": str(invoice.id),
            "amount_minor": request.amount_minor,
            "method": request.method.value,
            "reference": reference,
            "received_on": request.received_on.isoformat(),
        },
    )
    existing = await repo.payment_by_key(db, who.tenant_id, request.idempotency_key)
    if existing is not None:
        if existing.request_hash != digest:
            raise ConflictError(details=[KEY_REUSED])
        return Outcome(existing.id, created=False)

    if invoice.status == InvoiceStatus.CANCELLED.value:
        raise _invalid(_detail("status", "invoice_cancelled", "This fee invoice is cancelled."))
    pending = (await repo.open_payments(db, who.tenant_id, invoice.id)).get(
        PaymentStatus.PENDING, (0, 0)
    )[1]
    if request.amount_minor > invoice.total_minor - invoice.paid_minor - pending:
        raise _invalid(
            _detail(
                "amount_minor",
                "exceeds_balance",
                "The amount is more than the balance still to be collected "
                "(pending cheques and demand drafts included).",
            )
        )
    status = initial_payment_status(request.method)
    confirmed = status is PaymentStatus.CONFIRMED
    payment = Payment(
        tenant_id=who.tenant_id,
        invoice_id=invoice.id,
        student_id=invoice.student_id,
        campus_id=invoice.campus_id,
        amount_minor=request.amount_minor,
        currency=CURRENCY,
        method=request.method.value,
        reference=reference,
        received_on=request.received_on,
        status=status.value,
        recorded_by_membership_id=who.membership_id,
        confirmed_at=func.now() if confirmed else None,
        confirmed_by_membership_id=who.membership_id if confirmed else None,
        idempotency_key=request.idempotency_key,
        request_hash=digest,
    )
    db.add(payment)
    try:
        await db.flush()
    except IntegrityError:  # a backstop: the invoice lock serialises one invoice's payments
        raise ConflictError(details=[KEY_REUSED]) from None
    receipt = await _issue_receipt(db, who, invoice, payment) if confirmed else None
    await _activity(
        db,
        who,
        invoice.id,
        ActivityKind.PAYMENT_RECORDED,
        {
            "payment_id": str(payment.id),
            "amount_minor": payment.amount_minor,
            "method": payment.method,
            "status": status.value,
            "receipt_number": receipt.number if receipt else None,
        },
    )
    await write_audit_event(
        db,
        events.PAYMENT_RECORDED,
        target=AuditTarget("payment", payment.id),
        metadata={
            "amount_minor": payment.amount_minor,
            "currency": CURRENCY,
            "method": payment.method,
            "status": status.value,
        },
    )
    return Outcome(payment.id, created=True)


async def confirm_payment(db: AsyncSession, payment_id: uuid.UUID, *, version: int) -> None:
    """``PENDING`` → ``CONFIRMED`` after clearance: the receipt and the balance (§4)."""
    who = await caller(db, PAYMENT_RECORD)
    payment, invoice = await _locked_payment(db, who, payment_id, PAYMENT_RECORD)
    if payment.version != version:
        raise ConflictError(PAYMENT_STALE)
    if not PAYMENT_TRANSITIONS.allows(PaymentStatus(payment.status), PaymentStatus.CONFIRMED):
        raise invalid_transition("Only a pending cheque or demand draft can be confirmed.")
    if payment.amount_minor > invoice.total_minor - invoice.paid_minor:
        raise _invalid(
            _detail(
                "amount_minor",
                "exceeds_balance",
                "Confirming this payment would collect more than the fee invoice's total.",
            )
        )
    payment.status = PaymentStatus.CONFIRMED.value
    payment.confirmed_at = func.now()
    payment.confirmed_by_membership_id = who.membership_id
    await db.flush()
    receipt = await _issue_receipt(db, who, invoice, payment)
    await _activity(
        db,
        who,
        invoice.id,
        ActivityKind.PAYMENT_CONFIRMED,
        {
            "payment_id": str(payment.id),
            "amount_minor": payment.amount_minor,
            "method": payment.method,
            "receipt_number": receipt.number,
        },
    )
    await write_audit_event(
        db,
        events.PAYMENT_CONFIRMED,
        target=AuditTarget("payment", payment.id),
        metadata={
            "amount_minor": payment.amount_minor,
            "currency": CURRENCY,
            "method": payment.method,
        },
    )


async def fail_payment(
    db: AsyncSession, payment_id: uuid.UUID, *, reason: str | None, version: int
) -> None:
    """``PENDING`` → ``FAILED`` (not honoured): no receipt, the balance is unchanged."""
    who = await caller(db, PAYMENT_RECORD)
    payment, invoice = await _locked_payment(db, who, payment_id, PAYMENT_RECORD)
    if payment.version != version:
        raise ConflictError(PAYMENT_STALE)
    if not PAYMENT_TRANSITIONS.allows(PaymentStatus(payment.status), PaymentStatus.FAILED):
        raise invalid_transition("Only a pending cheque or demand draft can fail.")
    clean = _reason(reason)
    payment.status = PaymentStatus.FAILED.value
    payment.status_reason = clean
    payment.closed_at = func.now()
    payment.closed_by_membership_id = who.membership_id
    await db.flush()
    await _activity(
        db,
        who,
        invoice.id,
        ActivityKind.PAYMENT_FAILED,
        {
            "payment_id": str(payment.id),
            "amount_minor": payment.amount_minor,
            "method": payment.method,
            "reason": clean,
        },
    )
    await write_audit_event(
        db,
        events.PAYMENT_FAILED,
        target=AuditTarget("payment", payment.id),
        metadata={
            "amount_minor": payment.amount_minor,
            "currency": CURRENCY,
            "method": payment.method,
            "has_reason": True,
        },
    )


async def reverse_payment(
    db: AsyncSession, payment_id: uuid.UUID, *, reason: str | None, version: int
) -> None:
    """``CONFIRMED`` → ``REVERSED``: the balance is restored, the receipt shown as cancelled."""
    who = await caller(db, PAYMENT_REVERSE)
    payment, invoice = await _locked_payment(db, who, payment_id, PAYMENT_REVERSE)
    if payment.version != version:
        raise ConflictError(PAYMENT_STALE)
    if not PAYMENT_TRANSITIONS.allows(PaymentStatus(payment.status), PaymentStatus.REVERSED):
        raise invalid_transition("Only a confirmed payment can be reversed.")
    if payment.recorded_by_membership_id == who.membership_id:
        raise _invalid(
            _detail(
                "payment",
                "recorder_cannot_reverse",
                "A payment is reversed by someone other than the person who recorded it.",
            )
        )
    clean = _reason(reason)
    payment.status = PaymentStatus.REVERSED.value
    payment.status_reason = clean
    payment.closed_at = func.now()
    payment.closed_by_membership_id = who.membership_id
    _set_paid(invoice, invoice.paid_minor - payment.amount_minor)
    await db.flush()
    receipt = await repo.receipt_of(db, who.tenant_id, payment.id)
    await _activity(
        db,
        who,
        invoice.id,
        ActivityKind.PAYMENT_REVERSED,
        {
            "payment_id": str(payment.id),
            "amount_minor": payment.amount_minor,
            "method": payment.method,
            "receipt_number": receipt.number if receipt else None,
            "reason": clean,
        },
    )
    await write_audit_event(
        db,
        events.PAYMENT_REVERSED,
        target=AuditTarget("payment", payment.id),
        metadata={
            "amount_minor": payment.amount_minor,
            "currency": CURRENCY,
            "method": payment.method,
            "has_reason": True,
        },
    )


# --- Reads ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class InvoiceDetail:
    row: repo.InvoiceRow
    structure_name: str
    lines: list[InvoiceLine]
    payments: list[repo.PaymentRow]
    activity: list[repo.ActivityRow]
    pending_minor: int
    membership_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PaymentDetail:
    row: repo.PaymentRow
    membership_id: uuid.UUID


async def list_invoices(
    db: AsyncSession, filters: repo.InvoiceFilters, page: PageParams, sort: Sequence[SortField]
) -> tuple[list[repo.InvoiceRow], int]:
    who = await caller(db, INVOICE_READ)
    return await repo.search_invoices(db, who.context, who.tenant_id, filters, page, sort)


async def get_invoice(db: AsyncSession, invoice_id: uuid.UUID) -> InvoiceDetail:
    who = await caller(db, INVOICE_READ)
    await _visible_invoice(db, who, invoice_id, INVOICE_READ)
    return await invoice_detail(db, who, invoice_id)


async def invoice_detail(db: AsyncSession, who: Caller, invoice_id: uuid.UUID) -> InvoiceDetail:
    row = await repo.invoice_view(db, who.tenant_id, invoice_id)
    if row is None:  # pragma: no cover - authorized just before
        raise NotFoundError()
    structure = await FeeStructureRepository(db).find(row.invoice.fee_structure_id)
    open_payments = await repo.open_payments(db, who.tenant_id, invoice_id)
    return InvoiceDetail(
        row=row,
        structure_name=structure.name if structure else "",
        lines=await repo.lines_of(db, who.tenant_id, invoice_id),
        payments=await repo.payments_of(db, who.tenant_id, invoice_id),
        activity=await repo.activity_of(db, who.tenant_id, invoice_id),
        pending_minor=open_payments.get(PaymentStatus.PENDING, (0, 0))[1],
        membership_id=who.membership_id,
    )


async def list_payments(
    db: AsyncSession, filters: repo.PaymentFilters, page: PageParams, sort: Sequence[SortField]
) -> tuple[list[repo.PaymentRow], uuid.UUID, int]:
    who = await caller(db, INVOICE_READ)
    rows, total = await repo.search_payments(db, who.context, who.tenant_id, filters, page, sort)
    return rows, who.membership_id, total


async def get_payment(db: AsyncSession, payment_id: uuid.UUID) -> PaymentDetail:
    who = await caller(db, INVOICE_READ)
    found = await repo.payment(db, who.tenant_id, payment_id)
    if found is None:
        raise NotFoundError()
    authorize(who.context, INVOICE_READ, InvoiceResource(found.tenant_id, found.campus_id))
    return await payment_detail(db, who, payment_id)


async def payment_detail(db: AsyncSession, who: Caller, payment_id: uuid.UUID) -> PaymentDetail:
    row = await repo.payment_view(db, who.tenant_id, payment_id)
    if row is None:  # pragma: no cover - authorized just before
        raise NotFoundError()
    return PaymentDetail(row, who.membership_id)


async def summary(db: AsyncSession, campus_id: uuid.UUID | None) -> repo.Summary:
    who = await caller(db, INVOICE_READ)
    return await repo.summary(db, who.context, who.tenant_id, campus_id)


async def reader(db: AsyncSession, permission: Permission) -> Caller:
    """The caller of a command, for building its response after the command."""
    return await caller(db, permission)
