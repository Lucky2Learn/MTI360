"""Fee invoice, payment, receipt and summary models (Phase 02-5; ADR-0022, addendum R1-R3).

Fee invoices are **non-tax** (ADR-0022 §2). Amounts are integer paise in
INR; the server computes every total and balance. ``idempotency_key`` travels
in the JSON body (R3); ``recorded_by_me`` lets the UI hide or explain
Reverse, which the service refuses for the recorder regardless (R1).
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import Field, StringConstraints

from app.core.schemas import RequestModel, ResponseModel
from app.modules.finance.domain import (
    CURRENCY,
    MAX_AMOUNT_MINOR,
    REASON_MAX_LENGTH,
    REFERENCE_MAX_LENGTH,
    ActivityKind,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
)
from app.modules.finance.invoice_repository import InvoiceRow, PaymentRow, Summary
from app.modules.finance.invoicing import InvoiceDetail
from app.modules.finance.schemas import LINES_ACCEPTED, CourseRefOut, FeeItemIn, Version

PositiveAmount = Annotated[int, Field(strict=True, gt=0, le=MAX_AMOUNT_MINOR)]
"""A JSON integer of paise above zero: strings and floats are refused."""
Reason = Annotated[str, StringConstraints(max_length=REASON_MAX_LENGTH)]
Reference = Annotated[str, StringConstraints(max_length=REFERENCE_MAX_LENGTH)]


class StudentRefOut(ResponseModel):
    id: uuid.UUID
    number: str
    full_name: str


class NumberRefOut(ResponseModel):
    """An admission or a fee invoice by ID and number."""

    id: uuid.UUID
    number: str


class CampusRefOut(ResponseModel):
    id: uuid.UUID
    code: str


class InvoiceOut(ResponseModel):
    id: uuid.UUID
    number: str
    status: InvoiceStatus
    admission: NumberRefOut
    student: StudentRefOut
    course: CourseRefOut
    campus: CampusRefOut
    total_minor: int
    paid_minor: int
    balance_minor: int
    currency: str
    due_date: date
    overdue: bool
    adjusted: bool
    issued_at: datetime
    version: int


class InvoiceLineOut(ResponseModel):
    position: int
    fee_head: str
    amount_minor: int
    structure_amount_minor: int | None
    """The fee structure's amount; ``None`` for a line added at issue."""
    adjusted: bool


class ReceiptOut(ResponseModel):
    id: uuid.UUID
    number: str
    issued_at: datetime
    cancelled: bool
    """The payment was reversed: the receipt stays, shown as cancelled."""


class PaymentOut(ResponseModel):
    id: uuid.UUID
    invoice: NumberRefOut
    student: StudentRefOut
    amount_minor: int
    currency: str
    method: PaymentMethod
    reference: str | None
    received_on: date
    status: PaymentStatus
    status_reason: str | None
    recorded_by: str | None
    recorded_by_me: bool
    recorded_at: datetime
    confirmed_at: datetime | None
    closed_at: datetime | None
    receipt: ReceiptOut | None
    version: int


class FinanceActivityOut(ResponseModel):
    id: uuid.UUID
    kind: ActivityKind
    actor: str | None
    details: dict[str, Any]
    created_at: datetime


class FeeStructureRefOut(ResponseModel):
    id: uuid.UUID
    name: str
    version: int


class InvoiceDetailOut(InvoiceOut):
    fee_structure: FeeStructureRefOut
    structure_total_minor: int
    adjustment_reason: str | None
    status_reason: str | None
    cancelled_at: datetime | None
    pending_minor: int
    lines: list[InvoiceLineOut]
    payments: list[PaymentOut]
    activity: list[FinanceActivityOut]


class IssueInvoiceRequest(RequestModel):
    admission_id: uuid.UUID
    due_date: date
    lines: Annotated[list[FeeItemIn], Field(max_length=LINES_ACCEPTED)]
    adjustment_reason: Reason | None = None
    idempotency_key: uuid.UUID
    """Created once per form and reused on retry (addendum R3)."""


class CancelInvoiceRequest(RequestModel):
    reason: Reason
    version: Version


class RecordPaymentRequest(RequestModel):
    amount_minor: PositiveAmount
    method: PaymentMethod
    reference: Reference | None = None
    received_on: date
    idempotency_key: uuid.UUID


class PaymentVersionRequest(RequestModel):
    version: Version


class PaymentReasonRequest(RequestModel):
    reason: Reason
    version: Version


class SummaryOut(ResponseModel):
    """Live fee invoices the caller may see; ``as_of`` is today's date in IST."""

    invoice_count: int
    invoiced_minor: int
    collected_minor: int
    outstanding_minor: int
    outstanding_count: int
    overdue_minor: int
    overdue_count: int
    pending_minor: int
    pending_count: int
    currency: str
    as_of: date


def _invoice_fields(row: InvoiceRow) -> dict[str, Any]:
    invoice = row.invoice
    cancelled = invoice.status == InvoiceStatus.CANCELLED.value
    return {
        "id": invoice.id,
        "number": invoice.number,
        "status": InvoiceStatus(invoice.status),
        "admission": NumberRefOut(id=invoice.admission_id, number=row.admission_number),
        "student": StudentRefOut(
            id=invoice.student_id, number=row.student_number, full_name=row.student_name
        ),
        "course": CourseRefOut(id=invoice.course_id, code=row.course_code, name=row.course_name),
        "campus": CampusRefOut(id=invoice.campus_id, code=row.campus_code),
        "total_minor": invoice.total_minor,
        "paid_minor": invoice.paid_minor,
        "balance_minor": 0 if cancelled else invoice.total_minor - invoice.paid_minor,
        "currency": invoice.currency,
        "due_date": invoice.due_date,
        "overdue": row.overdue,
        "adjusted": invoice.adjusted,
        "issued_at": invoice.issued_at,
        "version": invoice.version,
    }


def invoice_out(row: InvoiceRow) -> InvoiceOut:
    return InvoiceOut(**_invoice_fields(row))


def payment_out(row: PaymentRow, membership_id: uuid.UUID) -> PaymentOut:
    payment = row.payment
    receipt = row.receipt
    return PaymentOut(
        id=payment.id,
        invoice=NumberRefOut(id=payment.invoice_id, number=row.invoice_number),
        student=StudentRefOut(
            id=payment.student_id, number=row.student_number, full_name=row.student_name
        ),
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        method=PaymentMethod(payment.method),
        reference=payment.reference,
        received_on=payment.received_on,
        status=PaymentStatus(payment.status),
        status_reason=payment.status_reason,
        recorded_by=row.recorded_by_name,
        recorded_by_me=payment.recorded_by_membership_id == membership_id,
        recorded_at=payment.created_at,
        confirmed_at=payment.confirmed_at,
        closed_at=payment.closed_at,
        receipt=(
            ReceiptOut(
                id=receipt.id,
                number=receipt.number,
                issued_at=receipt.issued_at,
                cancelled=payment.status == PaymentStatus.REVERSED.value,
            )
            if receipt is not None
            else None
        ),
        version=payment.version,
    )


def invoice_detail_out(detail: InvoiceDetail) -> InvoiceDetailOut:
    invoice = detail.row.invoice
    return InvoiceDetailOut(
        **_invoice_fields(detail.row),
        fee_structure=FeeStructureRefOut(
            id=invoice.fee_structure_id,
            name=detail.structure_name,
            version=invoice.fee_structure_version,
        ),
        structure_total_minor=invoice.structure_total_minor,
        adjustment_reason=invoice.adjustment_reason,
        status_reason=invoice.status_reason,
        cancelled_at=invoice.cancelled_at,
        pending_minor=detail.pending_minor,
        lines=[
            InvoiceLineOut(
                position=line.position,
                fee_head=line.fee_head,
                amount_minor=line.amount_minor,
                structure_amount_minor=line.structure_amount_minor,
                adjusted=line.structure_amount_minor != line.amount_minor,
            )
            for line in detail.lines
        ],
        payments=[payment_out(row, detail.membership_id) for row in detail.payments],
        activity=[
            FinanceActivityOut(
                id=item.activity.id,
                kind=ActivityKind(item.activity.kind),
                actor=item.actor_name,
                details=item.activity.details,
                created_at=item.activity.created_at,
            )
            for item in detail.activity
        ],
    )


def summary_out(summary: Summary) -> SummaryOut:
    return SummaryOut(
        invoice_count=summary.invoice_count,
        invoiced_minor=summary.invoiced_minor,
        collected_minor=summary.collected_minor,
        outstanding_minor=summary.outstanding_minor,
        outstanding_count=summary.outstanding_count,
        overdue_minor=summary.overdue_minor,
        overdue_count=summary.overdue_count,
        pending_minor=summary.pending_minor,
        pending_count=summary.pending_count,
        currency=CURRENCY,
        as_of=summary.as_of,
    )
