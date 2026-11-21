"""Batches and student allocation (Phase 02-6).

Authorization: every batch permission is campus-scoped and a batch has one
campus. A batch or allocation outside the caller's campuses is **not found**
(404); an admission or target batch named in a request body that the caller
may not use is a 422 ``*_not_available`` (the same answer as an unknown ID).

Every command runs in the request transaction, locks what it changes in the
repository's lock order (allocation → admission → batches by ID), checks the
optimistic ``version`` where the client sends one (409 when stale), records a
``batch_activities`` row and a ``domain`` audit event. The database backs
every rule that matters under concurrency: the seat-count trigger and the
capacity CHECK (no over-filled batch), the partial unique index (one active
allocation per admission) and the composite keys (no cross-course, -campus or
-tenant allocation).

Error semantics:

* 404 ``NOT_FOUND`` — batch / allocation unknown, other tenant or campus;
* 409 ``CONFLICT`` — stale ``version``, duplicate batch code, an allocation
  that ended or an admission allocated concurrently;
* 422 ``VALIDATION_ERROR`` — a business rule, with a detail code:
  ``course_not_active``, ``campus_not_available``, ``invalid_dates``,
  ``capacity_below_allocated``, ``batch_cancelled``, ``invalid_transition``,
  ``batch_has_allocations``, ``admission_not_available``,
  ``admission_not_admitted``, ``already_allocated``, ``student_not_active``,
  ``course_mismatch``, ``campus_mismatch``, ``batch_not_open``, ``batch_full``,
  ``payment_required``, ``reason_required``, ``same_batch``,
  ``target_not_available``.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

from sqlalchemy import Table, func, insert
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.activity import activity_details
from app.core.audit import AuditTarget, write_audit_event
from app.core.authz import Permission, authorize, campus_visible
from app.core.errors import ConflictError, ErrorDetail, NotFoundError, ValidationFailedError
from app.core.ids import new_id
from app.core.pagination import PageParams, SortField
from app.modules.batches import events
from app.modules.batches import repository as repo
from app.modules.batches.domain import (
    BATCH_TRANSITIONS,
    INITIAL_STATUS,
    INTAKE_MAX_LENGTH,
    ActivityKind,
    AllocationStatus,
    BatchStatus,
    EndReason,
    InvoiceState,
    PaymentBasis,
    capacity_valid,
    clean_name,
    clean_reason,
    dates_valid,
    invoice_state,
    normalize_code,
    outstanding_minor,
)
from app.modules.batches.models import Batch, BatchActivity, BatchAllocation
from app.modules.batches.permissions import BATCH_ALLOCATE, BATCH_MANAGE, BATCH_READ
from app.modules.courses.domain import CourseStatus
from app.modules.leads import follow_ups
from app.modules.leads.service import Caller, caller
from app.modules.students.domain import AdmissionStatus, StudentStatus
from app.modules.students.models import Admission

ACTIVITIES = cast(Table, BatchActivity.__table__)
STALE_BATCH = "This batch was changed by someone else. Reload and try again."
STALE_ALLOCATION = "This allocation was changed by someone else. Reload and try again."
ALREADY_ALLOCATED_CONFLICT = "This student was allocated to a batch a moment ago. Reload."
CODE_TAKEN = "A batch with this code already exists."
EDITABLE_FIELDS = ("name", "intake_label", "start_date", "end_date", "capacity")


@dataclass(frozen=True, slots=True)
class BatchResource:
    """A batch (or allocation) as an authorization resource: its campus."""

    tenant_id: uuid.UUID
    campus_id: uuid.UUID | None


def _detail(field: str, code: str, message: str) -> ErrorDetail:
    return ErrorDetail(field=field, code=code, message=message)


def _invalid(*details: ErrorDetail) -> ValidationFailedError:
    return ValidationFailedError(details=list(details))


COURSE_NOT_ACTIVE = _detail("course_id", "course_not_active", "Choose an active course.")
CAMPUS_NOT_AVAILABLE = _detail("campus_id", "campus_not_available", "Choose one of your campuses.")
INVALID_DATES = _detail("end_date", "invalid_dates", "The end date can't be before the start date.")
INVALID_CAPACITY = _detail("capacity", "invalid", "Enter a capacity from 1 to 500.")
BATCH_CANCELLED = _detail("status", "batch_cancelled", "A cancelled batch can't be changed.")
ADMISSION_NOT_AVAILABLE = _detail(
    "admission_id", "admission_not_available", "Choose an admitted student you can see."
)
REASON_REQUIRED = _detail("reason", "reason_required", "Enter a reason of up to 500 characters.")


def _visible(who: Caller, found: Batch | BatchAllocation, permission: Permission) -> None:
    authorize(who.context, permission, BatchResource(found.tenant_id, found.campus_id))


async def _authorized_batch(
    db: AsyncSession, who: Caller, batch_id: uuid.UUID, permission: Permission, *, lock: bool
) -> Batch:
    found = await repo.batch(db, who.tenant_id, batch_id, lock=lock)
    if found is None:
        raise NotFoundError()
    _visible(who, found, permission)
    return found


async def _activity(
    db: AsyncSession,
    who: Caller,
    batch_id: uuid.UUID,
    kind: ActivityKind,
    details: Mapping[str, object] | None = None,
    *,
    allocation_id: uuid.UUID | None = None,
) -> None:
    """One append-only ``batch_activities`` row in the request transaction (the
    :mod:`app.core.activity` contract, plus the allocation the row is about)."""
    await db.execute(
        insert(ACTIVITIES).values(
            id=new_id(),
            tenant_id=who.tenant_id,
            batch_id=batch_id,
            allocation_id=allocation_id,
            kind=kind.value,
            actor_membership_id=who.membership_id,
            details=activity_details(details or {}),
        )
    )


async def _view(db: AsyncSession, who: Caller, batch_id: uuid.UUID) -> repo.BatchRow:
    row = await repo.batch_view(db, who.tenant_id, batch_id)
    if row is None:  # pragma: no cover - read in this transaction
        raise NotFoundError()
    return row


async def _allocation_view(
    db: AsyncSession, who: Caller, allocation_id: uuid.UUID
) -> repo.AllocationRow:
    row = await repo.allocation_view(db, who.tenant_id, allocation_id)
    if row is None:  # pragma: no cover - written in this transaction
        raise NotFoundError()
    return row


# --- Batch reads ---------------------------------------------------------------------------


async def list_batches(
    db: AsyncSession, filters: repo.BatchFilters, page: PageParams, sort: tuple[SortField, ...]
) -> tuple[list[repo.BatchRow], int]:
    who = await caller(db, BATCH_READ)
    return await repo.search_batches(db, who.tenant_id, who.context, filters, page, sort)


async def get_batch(db: AsyncSession, batch_id: uuid.UUID) -> repo.BatchRow:
    who = await caller(db, BATCH_READ)
    await _authorized_batch(db, who, batch_id, BATCH_READ, lock=False)
    return await _view(db, who, batch_id)


async def batch_activity(
    db: AsyncSession, batch_id: uuid.UUID, page: PageParams
) -> tuple[list[follow_ups.ActivityView], int]:
    who = await caller(db, BATCH_READ)
    await _authorized_batch(db, who, batch_id, BATCH_READ, lock=False)
    rows, total = await repo.activity_of_batch(db, who.tenant_id, batch_id, page)
    return await follow_ups.activity_views(db, who, rows), total


# --- Batch commands -----------------------------------------------------------------------


def _clean(values: Mapping[str, Any]) -> tuple[dict[str, Any], list[ErrorDetail]]:
    cleaned: dict[str, Any] = {}
    problems: list[ErrorDetail] = []
    if "name" in values:
        name = clean_name(values["name"] or "")
        if name is None:
            problems.append(_detail("name", "invalid", "Enter a name of up to 200 characters."))
        cleaned["name"] = name
    if "intake_label" in values:
        raw = values["intake_label"]
        label = clean_name(raw, INTAKE_MAX_LENGTH) if raw and raw.strip() else None
        if raw and raw.strip() and label is None:
            problems.append(_detail("intake_label", "invalid", "Use at most 100 characters."))
        cleaned["intake_label"] = label
    for field in ("start_date", "end_date"):
        if field in values:
            if values[field] is None:
                problems.append(_detail(field, "required", "Enter a date."))
            cleaned[field] = values[field]
    if "capacity" in values:
        if values["capacity"] is None or not capacity_valid(values["capacity"]):
            problems.append(INVALID_CAPACITY)
        cleaned["capacity"] = values["capacity"]
    return cleaned, problems


async def create_batch(
    db: AsyncSession,
    *,
    course_id: uuid.UUID,
    campus_id: uuid.UUID,
    code: str,
    values: Mapping[str, Any],
) -> repo.BatchRow:
    """A new ``OPEN`` batch at one of the caller's campuses, for an ``ACTIVE`` course."""
    who = await caller(db, BATCH_MANAGE)
    cleaned, problems = _clean({field: values.get(field) for field in EDITABLE_FIELDS})
    clean_code = normalize_code(code)
    if clean_code is None:
        problems.insert(
            0,
            _detail(
                "code",
                "invalid",
                "Use up to 32 letters, digits or hyphens, starting with a letter or digit.",
            ),
        )
    if not campus_visible(campus_id, who.context) or not await repo.campus_exists(
        db, who.tenant_id, campus_id
    ):
        problems.append(CAMPUS_NOT_AVAILABLE)
    if await repo.course_status(db, who.tenant_id, course_id) != CourseStatus.ACTIVE.value:
        problems.append(COURSE_NOT_ACTIVE)
    start, end = cleaned.get("start_date"), cleaned.get("end_date")
    if isinstance(start, date) and isinstance(end, date) and not dates_valid(start, end):
        problems.append(INVALID_DATES)
    if problems or clean_code is None:
        raise _invalid(*problems)
    authorize(who.context, BATCH_MANAGE, BatchResource(who.tenant_id, campus_id))
    if await repo.code_taken(db, who.tenant_id, clean_code):
        raise ConflictError(CODE_TAKEN)
    batch = Batch(
        tenant_id=who.tenant_id,
        course_id=course_id,
        campus_id=campus_id,
        code=clean_code,
        status=INITIAL_STATUS.value,
        allocated_count=0,
        created_by_membership_id=who.membership_id,
        **cleaned,
    )
    db.add(batch)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:  # the same code, created concurrently
        raise ConflictError(CODE_TAKEN) from None
    await _activity(db, who, batch.id, ActivityKind.CREATED, {"code": clean_code})
    await write_audit_event(
        db,
        events.BATCH_CREATED,
        target=AuditTarget("batch", batch.id),
        metadata={"code": clean_code, "capacity": batch.capacity},
    )
    return await _view(db, who, batch.id)


async def update_batch(
    db: AsyncSession, batch_id: uuid.UUID, *, changes: Mapping[str, Any], version: int
) -> repo.BatchRow:
    """Edit name, intake, dates and capacity. Course and campus never change; capacity
    never drops below the active allocations."""
    who = await caller(db, BATCH_MANAGE)
    batch = await _authorized_batch(db, who, batch_id, BATCH_MANAGE, lock=True)
    if batch.version != version:
        raise ConflictError(STALE_BATCH)
    if batch.status == BatchStatus.CANCELLED.value:
        raise _invalid(BATCH_CANCELLED)
    cleaned, problems = _clean(changes)
    start = cleaned.get("start_date", batch.start_date)
    end = cleaned.get("end_date", batch.end_date)
    if isinstance(start, date) and isinstance(end, date) and not dates_valid(start, end):
        problems.append(INVALID_DATES)
    capacity = cleaned.get("capacity")
    if isinstance(capacity, int) and capacity_valid(capacity) and capacity < batch.allocated_count:
        problems.append(
            _detail(
                "capacity",
                "capacity_below_allocated",
                f"{batch.allocated_count} students are allocated. "
                "Capacity can't be lower than that.",
            )
        )
    if problems:
        raise _invalid(*problems)
    changed = sorted(field for field, new in cleaned.items() if getattr(batch, field) != new)
    if not changed:
        return await _view(db, who, batch.id)
    for field in changed:
        setattr(batch, field, cleaned[field])
    await db.flush()
    await _activity(db, who, batch.id, ActivityKind.UPDATED, {"changed_fields": changed})
    await write_audit_event(
        db,
        events.BATCH_UPDATED,
        target=AuditTarget("batch", batch.id),
        metadata={"changed_fields": changed},
    )
    return await _view(db, who, batch.id)


async def change_status(
    db: AsyncSession,
    batch_id: uuid.UUID,
    *,
    status: BatchStatus,
    reason: str | None,
    version: int,
) -> repo.BatchRow:
    """Close, reopen or cancel (``BATCH_TRANSITIONS``); cancel only an empty batch."""
    who = await caller(db, BATCH_MANAGE)
    batch = await _authorized_batch(db, who, batch_id, BATCH_MANAGE, lock=True)
    if batch.version != version:
        raise ConflictError(STALE_BATCH)
    current = BatchStatus(batch.status)
    if not BATCH_TRANSITIONS.allows(current, status):
        raise _invalid(
            _detail("status", "invalid_transition", "This batch can't move to that status.")
        )
    kept_reason = clean_reason(reason) if reason and reason.strip() else None
    if reason and reason.strip() and kept_reason is None:
        raise _invalid(REASON_REQUIRED)
    if status is BatchStatus.CANCELLED and batch.allocated_count > 0:
        raise _invalid(
            _detail(
                "status",
                "batch_has_allocations",
                "Withdraw or transfer every allocated student before cancelling this batch.",
            )
        )
    batch.status = status.value
    batch.status_reason = kept_reason
    await db.flush()
    await _activity(
        db,
        who,
        batch.id,
        ActivityKind.STATUS_CHANGED,
        {"from": current.value, "to": status.value, "has_reason": kept_reason is not None},
    )
    await write_audit_event(
        db,
        events.BATCH_STATUS_CHANGED,
        target=AuditTarget("batch", batch.id),
        metadata={"from": current.value, "to": status.value},
    )
    return await _view(db, who, batch.id)


# --- Allocation reads ---------------------------------------------------------------------


async def list_allocations(
    db: AsyncSession,
    filters: repo.AllocationFilters,
    page: PageParams,
) -> tuple[list[repo.AllocationRow], int]:
    """Allocations in the caller's campuses; a named batch must be visible (404)."""
    who = await caller(db, BATCH_READ)
    if filters.batch_id is not None:
        await _authorized_batch(db, who, filters.batch_id, BATCH_READ, lock=False)
    return await repo.search_allocations(db, who.tenant_id, who.context, filters, page)


async def eligible_admissions(
    db: AsyncSession, batch_id: uuid.UUID, *, search: str | None, page: PageParams
) -> tuple[repo.BatchRow, list[repo.EligibleRow], int]:
    who = await caller(db, BATCH_ALLOCATE)
    batch = await _authorized_batch(db, who, batch_id, BATCH_ALLOCATE, lock=False)
    rows, total = await repo.eligible_admissions(db, who.tenant_id, batch, search=search, page=page)
    return await _view(db, who, batch.id), rows, total


async def current_batches(
    db: AsyncSession, who: Caller, admission_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[uuid.UUID, str, str]]:
    """For Student 360 / admissions: the current batch of each admission (``batch.read``)."""
    if BATCH_READ.code not in who.context.permissions:
        return {}
    return await repo.current_batches(db, who.tenant_id, admission_ids)


# --- Allocation commands ------------------------------------------------------------------


def _seat_problems(batch: Batch, *, field: str) -> list[ErrorDetail]:
    if batch.status != BatchStatus.OPEN.value:
        return [_detail(field, "batch_not_open", "Students are allocated only to an open batch.")]
    if batch.allocated_count >= batch.capacity:
        return [_detail(field, "batch_full", "This batch is full.")]
    return []


async def _insert_allocation(db: AsyncSession, allocation: BatchAllocation) -> None:
    """Insert; the trigger counts the seat. A database refusal here means a concurrent
    change the locks did not cover (a backstop): duplicate → 409, seat or status → 422."""
    db.add(allocation)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as error:
        if "uq_batch_allocations_tenant_id_admission_id_active" in str(error.orig):
            raise ConflictError(ALREADY_ALLOCATED_CONFLICT) from None
        raise _invalid(_detail("batch_id", "batch_full", "This batch is full.")) from None
    except DBAPIError:
        raise _invalid(
            _detail("batch_id", "batch_not_open", "Students are allocated only to an open batch.")
        ) from None


@dataclass(frozen=True, slots=True)
class _Payment:
    basis: PaymentBasis
    state: InvoiceState
    outstanding: int | None


async def _payment(
    db: AsyncSession, who: Caller, admission_id: uuid.UUID, override_reason: str | None
) -> tuple[_Payment, str | None]:
    """The payment gate (decision B): PAID passes; otherwise an override reason is needed."""
    invoice = await repo.live_invoice(db, who.tenant_id, admission_id)
    state = invoice_state(invoice.status if invoice else None)
    owed = outstanding_minor(
        invoice.total_minor if invoice else None, invoice.paid_minor if invoice else None
    )
    if state is InvoiceState.PAID:
        return _Payment(PaymentBasis.PAID, state, None), None
    reason = clean_reason(override_reason)
    if reason is None:
        message = (
            "No fee invoice has been issued for this admission. Issue and collect the fees, "
            "or allocate with a payment override reason."
            if state is InvoiceState.NO_INVOICE
            else "Fees are outstanding for this admission. Collect them, or allocate with a "
            "payment override reason."
        )
        raise _invalid(_detail("override_reason", "payment_required", message))
    return _Payment(PaymentBasis.OVERRIDE, state, owed), reason


async def allocate(
    db: AsyncSession,
    batch_id: uuid.UUID,
    *,
    admission_id: uuid.UUID,
    override_reason: str | None,
) -> repo.AllocationRow:
    """``ADMITTED`` → ``ENROLLED``: one allocation of an eligible admission to an open batch
    with a free seat, after the payment gate."""
    who = await caller(db, BATCH_ALLOCATE)
    # The batch in the path first (404), without a lock; locks follow the repository order.
    await _authorized_batch(db, who, batch_id, BATCH_ALLOCATE, lock=False)
    admission = await repo.admission(db, who.tenant_id, admission_id, lock=True)
    if admission is None or not campus_visible(admission.campus_id, who.context):
        raise _invalid(ADMISSION_NOT_AVAILABLE)
    batch = await _authorized_batch(db, who, batch_id, BATCH_ALLOCATE, lock=True)
    problems: list[ErrorDetail] = []
    if admission.status == AdmissionStatus.ENROLLED.value:
        problems.append(
            _detail(
                "admission_id",
                "already_allocated",
                "This student is already allocated to a batch. Transfer them instead.",
            )
        )
    elif admission.status != AdmissionStatus.ADMITTED.value:
        problems.append(
            _detail("admission_id", "admission_not_admitted", "Only admitted students.")
        )
    if await repo.student_status(db, who.tenant_id, admission.student_id) != (
        StudentStatus.ACTIVE.value
    ):
        problems.append(
            _detail("admission_id", "student_not_active", "This student is not active.")
        )
    if admission.course_id != batch.course_id:
        problems.append(
            _detail(
                "admission_id", "course_mismatch", "This student was admitted to another course."
            )
        )
    if admission.campus_id != batch.campus_id:
        problems.append(
            _detail(
                "admission_id", "campus_mismatch", "This student was admitted at another campus."
            )
        )
    problems.extend(_seat_problems(batch, field="batch_id"))
    if problems:
        raise _invalid(*problems)
    payment, reason = await _payment(db, who, admission.id, override_reason)
    allocation = BatchAllocation(
        tenant_id=who.tenant_id,
        batch_id=batch.id,
        course_id=batch.course_id,
        campus_id=batch.campus_id,
        admission_id=admission.id,
        student_id=admission.student_id,
        status=AllocationStatus.ACTIVE.value,
        payment_basis=payment.basis.value,
        override_reason=reason,
        override_invoice_state=payment.state.value if reason else None,
        override_outstanding_minor=payment.outstanding if reason else None,
        allocated_by_membership_id=who.membership_id,
    )
    await _insert_allocation(db, allocation)
    admission.status = AdmissionStatus.ENROLLED.value
    await db.flush()
    overridden = payment.basis is PaymentBasis.OVERRIDE
    await _activity(
        db,
        who,
        batch.id,
        ActivityKind.ALLOCATED,
        {
            "batch_code": batch.code,
            "admission_number": admission.admission_number,
            "payment_basis": payment.basis.value,
            "invoice_state": payment.state.value if overridden else None,
            "outstanding_minor": payment.outstanding if overridden else None,
        },
        allocation_id=allocation.id,
    )
    await write_audit_event(
        db,
        events.STUDENT_ALLOCATED,
        target=AuditTarget("batch_allocation", allocation.id),
        metadata={"batch_code": batch.code, "payment_basis": payment.basis.value},
    )
    if overridden:
        await write_audit_event(
            db,
            events.PAYMENT_OVERRIDDEN,
            target=AuditTarget("batch_allocation", allocation.id),
            metadata={
                "invoice_state": payment.state.value,
                "outstanding_minor": payment.outstanding,
            },
        )
    return await _allocation_view(db, who, allocation.id)


async def _locked_allocation(
    db: AsyncSession, who: Caller, allocation_id: uuid.UUID, version: int
) -> tuple[BatchAllocation, Admission]:
    found = await repo.allocation(db, who.tenant_id, allocation_id, lock=True)
    if found is None:
        raise NotFoundError()
    _visible(who, found, BATCH_ALLOCATE)
    if found.version != version or found.status != AllocationStatus.ACTIVE.value:
        raise ConflictError(STALE_ALLOCATION)
    admission = await repo.admission(db, who.tenant_id, found.admission_id, lock=True)
    if admission is None:  # pragma: no cover - the composite key guarantees it
        raise NotFoundError()
    return found, admission


def _end(found: BatchAllocation, who: Caller, reason: EndReason, note: str) -> None:
    found.status = AllocationStatus.ENDED.value
    found.end_reason = reason.value
    found.end_note = note
    found.ended_at = func.now()
    found.ended_by_membership_id = who.membership_id


async def transfer(
    db: AsyncSession,
    allocation_id: uuid.UUID,
    *,
    target_batch_id: uuid.UUID,
    reason: str | None,
    version: int,
) -> repo.AllocationRow:
    """Move an enrolled student to another open batch of the same course (and campus, which
    the admission fixes), keeping history: the old allocation ends ``TRANSFERRED`` and a new
    one starts, atomically. The admission stays ``ENROLLED``."""
    who = await caller(db, BATCH_ALLOCATE)
    note = clean_reason(reason)
    found, admission = await _locked_allocation(db, who, allocation_id, version)
    if note is None:
        raise _invalid(REASON_REQUIRED)
    if target_batch_id == found.batch_id:
        raise _invalid(_detail("target_batch_id", "same_batch", "Choose a different batch."))
    batches = await repo.lock_batches(db, who.tenant_id, {found.batch_id, target_batch_id})
    source, target = batches[found.batch_id], batches.get(target_batch_id)
    if target is None or not campus_visible(target.campus_id, who.context):
        raise _invalid(
            _detail("target_batch_id", "target_not_available", "Choose a batch you can see.")
        )
    problems: list[ErrorDetail] = []
    if target.course_id != found.course_id:
        problems.append(
            _detail("target_batch_id", "course_mismatch", "Choose a batch of the same course.")
        )
    if target.campus_id != found.campus_id:
        problems.append(
            _detail("target_batch_id", "campus_mismatch", "Choose a batch at the same campus.")
        )
    problems.extend(_seat_problems(target, field="target_batch_id"))
    if problems:
        raise _invalid(*problems)
    _end(found, who, EndReason.TRANSFERRED, note)
    await db.flush()
    new = BatchAllocation(
        tenant_id=who.tenant_id,
        batch_id=target.id,
        course_id=target.course_id,
        campus_id=target.campus_id,
        admission_id=found.admission_id,
        student_id=found.student_id,
        status=AllocationStatus.ACTIVE.value,
        payment_basis=PaymentBasis.TRANSFER.value,
        transferred_from_id=found.id,
        allocated_by_membership_id=who.membership_id,
    )
    await _insert_allocation(db, new)
    details = {
        "from_batch_code": source.code,
        "to_batch_code": target.code,
        "admission_number": admission.admission_number,
    }
    await _activity(
        db, who, source.id, ActivityKind.TRANSFERRED_OUT, details, allocation_id=found.id
    )
    await _activity(db, who, target.id, ActivityKind.TRANSFERRED_IN, details, allocation_id=new.id)
    await write_audit_event(
        db,
        events.STUDENT_TRANSFERRED,
        target=AuditTarget("batch_allocation", new.id),
        metadata={"from_batch_code": source.code, "to_batch_code": target.code},
    )
    return await _allocation_view(db, who, new.id)


async def withdraw(
    db: AsyncSession, allocation_id: uuid.UUID, *, reason: str | None, version: int
) -> repo.AllocationRow:
    """End the active allocation (``WITHDRAWN``) and return the admission to ``ADMITTED``."""
    who = await caller(db, BATCH_ALLOCATE)
    note = clean_reason(reason)
    found, admission = await _locked_allocation(db, who, allocation_id, version)
    if note is None:
        raise _invalid(REASON_REQUIRED)
    batches = await repo.lock_batches(db, who.tenant_id, {found.batch_id})
    batch = batches[found.batch_id]
    _end(found, who, EndReason.WITHDRAWN, note)
    await db.flush()
    admission.status = AdmissionStatus.ADMITTED.value
    await db.flush()
    await _activity(
        db,
        who,
        batch.id,
        ActivityKind.WITHDRAWN,
        {"batch_code": batch.code, "admission_number": admission.admission_number},
        allocation_id=found.id,
    )
    await write_audit_event(
        db,
        events.STUDENT_WITHDRAWN,
        target=AuditTarget("batch_allocation", found.id),
        metadata={"batch_code": batch.code},
    )
    return await _allocation_view(db, who, found.id)
