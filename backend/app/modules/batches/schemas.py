"""Batch API contracts (Phase 02-6)."""

import uuid
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import Field, StringConstraints

from app.core.schemas import RequestModel, ResponseModel
from app.modules.batches.domain import (
    CAPACITY_MAX,
    CAPACITY_MIN,
    CODE_MAX_LENGTH,
    INTAKE_MAX_LENGTH,
    NAME_MAX_LENGTH,
    REASON_MAX_LENGTH,
    AllocationStatus,
    BatchStatus,
    EndReason,
    InvoiceState,
    PaymentBasis,
    available_seats,
    invoice_state,
    outstanding_minor,
)
from app.modules.batches.repository import AllocationRow, BatchRow, EligibleRow
from app.modules.leads.schemas import CampusRef, PersonRef

Name = Annotated[str, StringConstraints(min_length=1, max_length=NAME_MAX_LENGTH)]
Intake = Annotated[str, StringConstraints(max_length=INTAKE_MAX_LENGTH)]
Capacity = Annotated[int, Field(ge=CAPACITY_MIN, le=CAPACITY_MAX)]
Reason = Annotated[str, StringConstraints(max_length=REASON_MAX_LENGTH)]
Version = Annotated[int, Field(ge=1)]


class CourseRef(ResponseModel):
    id: uuid.UUID
    code: str
    name: str


class BatchOut(ResponseModel):
    id: uuid.UUID
    code: str
    name: str
    intake_label: str | None
    course: CourseRef
    campus: CampusRef
    start_date: date
    end_date: date
    capacity: int
    allocated_count: int
    available_seats: int
    status: BatchStatus
    status_reason: str | None
    created_at: datetime
    updated_at: datetime
    version: int


def batch_out(row: BatchRow) -> BatchOut:
    batch = row.batch
    return BatchOut(
        id=batch.id,
        code=batch.code,
        name=batch.name,
        intake_label=batch.intake_label,
        course=CourseRef(id=batch.course_id, code=row.course_code, name=row.course_name),
        campus=CampusRef(id=batch.campus_id, code=row.campus_code, name=row.campus_name),
        start_date=batch.start_date,
        end_date=batch.end_date,
        capacity=batch.capacity,
        allocated_count=batch.allocated_count,
        available_seats=available_seats(batch.capacity, batch.allocated_count),
        status=BatchStatus(batch.status),
        status_reason=batch.status_reason,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        version=batch.version,
    )


class CreateBatchRequest(RequestModel):
    course_id: uuid.UUID
    campus_id: uuid.UUID
    code: Annotated[str, StringConstraints(min_length=1, max_length=CODE_MAX_LENGTH)]
    name: Name
    intake_label: Intake | None = None
    start_date: date
    end_date: date
    capacity: Capacity


class UpdateBatchRequest(RequestModel):
    """Only the fields sent change. Course, campus, code and status cannot be set here."""

    name: Name | None = None
    intake_label: Intake | None = None
    start_date: date | None = None
    end_date: date | None = None
    capacity: Capacity | None = None
    version: Version


class BatchStatusRequest(RequestModel):
    status: BatchStatus
    reason: Reason | None = None
    version: Version


class StudentRef(ResponseModel):
    id: uuid.UUID
    number: str
    full_name: str


class PaymentOverrideOut(ResponseModel):
    reason: str
    invoice_state: InvoiceState
    outstanding_minor: int | None


class AllocationOut(ResponseModel):
    id: uuid.UUID
    batch: CourseRef
    course: CourseRef
    campus_id: uuid.UUID
    campus_name: str
    admission_id: uuid.UUID
    admission_number: str
    student: StudentRef
    status: AllocationStatus
    payment_basis: PaymentBasis
    payment_override: PaymentOverrideOut | None
    transferred_from_id: uuid.UUID | None
    transferred_from_batch_code: str | None
    transferred_to_batch_code: str | None
    allocated_at: datetime
    allocated_by: PersonRef | None
    end_reason: EndReason | None
    end_note: str | None
    ended_at: datetime | None
    ended_by: PersonRef | None
    version: int


def _person(name: str | None) -> PersonRef | None:
    return PersonRef(display_name=name) if name else None


def allocation_out(row: AllocationRow) -> AllocationOut:
    override = (
        PaymentOverrideOut(
            reason=row.override_reason,
            invoice_state=InvoiceState(row.override_invoice_state),
            outstanding_minor=row.override_outstanding_minor,
        )
        if row.override_reason is not None and row.override_invoice_state is not None
        else None
    )
    return AllocationOut(
        id=row.id,
        batch=CourseRef(id=row.batch_id, code=row.batch_code, name=row.batch_name),
        course=CourseRef(id=row.course_id, code=row.course_code, name=row.course_name),
        campus_id=row.campus_id,
        campus_name=row.campus_name,
        admission_id=row.admission_id,
        admission_number=row.admission_number,
        student=StudentRef(
            id=row.student_id, number=row.student_number, full_name=row.student_name
        ),
        status=AllocationStatus(row.status),
        payment_basis=PaymentBasis(row.payment_basis),
        payment_override=override,
        transferred_from_id=row.transferred_from_id,
        transferred_from_batch_code=row.transferred_from_batch_code,
        transferred_to_batch_code=row.transferred_to_batch_code,
        allocated_at=row.allocated_at,
        allocated_by=_person(row.allocated_by_name),
        end_reason=EndReason(row.end_reason) if row.end_reason else None,
        end_note=row.end_note,
        ended_at=row.ended_at,
        ended_by=_person(row.ended_by_name),
        version=row.version,
    )


class EligibleAdmissionOut(ResponseModel):
    admission_id: uuid.UUID
    admission_number: str
    approved_at: datetime
    student: StudentRef
    invoice_state: InvoiceState
    invoice_total_minor: int | None
    outstanding_minor: int | None
    payment_cleared: bool


def eligible_out(row: EligibleRow) -> EligibleAdmissionOut:
    state = invoice_state(row.invoice_status)
    return EligibleAdmissionOut(
        admission_id=row.admission_id,
        admission_number=row.admission_number,
        approved_at=row.approved_at,
        student=StudentRef(
            id=row.student_id, number=row.student_number, full_name=row.student_name
        ),
        invoice_state=state,
        invoice_total_minor=row.invoice_total_minor,
        outstanding_minor=outstanding_minor(row.invoice_total_minor, row.invoice_paid_minor),
        payment_cleared=state is InvoiceState.PAID,
    )


class AllocateRequest(RequestModel):
    admission_id: uuid.UUID
    override_reason: Reason | None = None
    """Required when the fee invoice is not fully paid (or none is live)."""


class TransferRequest(RequestModel):
    target_batch_id: uuid.UUID
    reason: Reason
    version: Version


class WithdrawRequest(RequestModel):
    reason: Reason
    version: Version


class BatchActivityOut(ResponseModel):
    id: uuid.UUID
    kind: str
    actor: PersonRef | None
    details: dict[str, Any]
    created_at: datetime
