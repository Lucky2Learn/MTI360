"""Batch data access (Phase 02-6).

The trusted tenant is stated in every statement, added again by the ORM tenant
filter and enforced by Row-Level Security. Lists apply the campus visibility
predicate, so a restricted member never receives a row that ``authorize()``
would answer with 404.

Lock order (deadlock-free): allocation → admission → batches by ascending ID.
Every command takes its locks in that order.
"""

import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from sqlalchemy import ColumnElement, and_, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.authz import campus_visibility
from app.core.context import RequestContext
from app.core.pagination import PageParams, SortField
from app.core.search import escape_like
from app.modules.batches.domain import AllocationStatus, BatchStatus
from app.modules.batches.models import Batch, BatchActivity, BatchAllocation
from app.modules.courses.models import Course
from app.modules.finance.models import Invoice
from app.modules.identity.models import TenantMembership, User
from app.modules.institute.models import Campus
from app.modules.students.domain import AdmissionStatus, StudentStatus
from app.modules.students.models import Admission, Student

SORT_COLUMNS: Final = ("start_date", "code", "name", "created_at")
AllocatorMembership = aliased(TenantMembership, name="allocator_membership")
AllocatorUser = aliased(User, name="allocator_user")
EnderMembership = aliased(TenantMembership, name="ender_membership")
EnderUser = aliased(User, name="ender_user")
FromAllocation = aliased(BatchAllocation, name="from_allocation")
FromBatch = aliased(Batch, name="from_batch")
NextAllocation = aliased(BatchAllocation, name="next_allocation")
NextBatch = aliased(Batch, name="next_batch")


# --- Single rows (commands) -----------------------------------------------------------------


async def batch(
    db: AsyncSession, tenant_id: uuid.UUID, batch_id: uuid.UUID, *, lock: bool = False
) -> Batch | None:
    statement = select(Batch).where(Batch.tenant_id == tenant_id, Batch.id == batch_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    found: Batch | None = await db.scalar(statement)
    return found


async def lock_batches(
    db: AsyncSession, tenant_id: uuid.UUID, batch_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, Batch]:
    """Lock several batches in ascending ID order (one statement, deterministic order)."""
    statement = (
        select(Batch)
        .where(Batch.tenant_id == tenant_id, Batch.id.in_(sorted(batch_ids)))
        .order_by(Batch.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return {found.id: found for found in await db.scalars(statement)}


async def refresh_batch(db: AsyncSession, found: Batch) -> None:
    """Re-read a batch after the seat-count trigger changed it."""
    await db.refresh(found)


async def code_taken(db: AsyncSession, tenant_id: uuid.UUID, code: str) -> bool:
    found = await db.scalar(
        select(Batch.id).where(Batch.tenant_id == tenant_id, Batch.code == code)
    )
    return found is not None


async def course_status(db: AsyncSession, tenant_id: uuid.UUID, course_id: uuid.UUID) -> str | None:
    found: str | None = await db.scalar(
        select(Course.status).where(Course.tenant_id == tenant_id, Course.id == course_id)
    )
    return found


async def campus_exists(db: AsyncSession, tenant_id: uuid.UUID, campus_id: uuid.UUID) -> bool:
    found = await db.scalar(
        select(Campus.id).where(Campus.tenant_id == tenant_id, Campus.id == campus_id)
    )
    return found is not None


async def admission(
    db: AsyncSession, tenant_id: uuid.UUID, admission_id: uuid.UUID, *, lock: bool = False
) -> Admission | None:
    statement = select(Admission).where(
        Admission.tenant_id == tenant_id, Admission.id == admission_id
    )
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    found: Admission | None = await db.scalar(statement)
    return found


async def student_status(
    db: AsyncSession, tenant_id: uuid.UUID, student_id: uuid.UUID
) -> str | None:
    found: str | None = await db.scalar(
        select(Student.status).where(Student.tenant_id == tenant_id, Student.id == student_id)
    )
    return found


@dataclass(frozen=True, slots=True)
class LiveInvoice:
    status: str
    total_minor: int
    paid_minor: int


async def live_invoice(
    db: AsyncSession, tenant_id: uuid.UUID, admission_id: uuid.UUID
) -> LiveInvoice | None:
    """The admission's live (not cancelled) fee invoice, if any (at most one exists)."""
    row = (
        await db.execute(
            select(Invoice.status, Invoice.total_minor, Invoice.paid_minor).where(
                Invoice.tenant_id == tenant_id,
                Invoice.admission_id == admission_id,
                Invoice.status != "CANCELLED",
            )
        )
    ).one_or_none()
    return LiveInvoice(row[0], row[1], row[2]) if row else None


async def allocation(
    db: AsyncSession, tenant_id: uuid.UUID, allocation_id: uuid.UUID, *, lock: bool = False
) -> BatchAllocation | None:
    statement = select(BatchAllocation).where(
        BatchAllocation.tenant_id == tenant_id, BatchAllocation.id == allocation_id
    )
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    found: BatchAllocation | None = await db.scalar(statement)
    return found


# --- Batch lists and views --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BatchFilters:
    search: str | None = None
    statuses: Collection[BatchStatus] = ()
    course_id: uuid.UUID | None = None
    campus_id: uuid.UUID | None = None
    has_seats: bool | None = None


@dataclass(frozen=True, slots=True)
class BatchRow:
    batch: Batch
    course_code: str
    course_name: str
    campus_code: str
    campus_name: str


def _batch_select() -> Any:
    return (
        select(Batch, Course.code, Course.name, Campus.code, Campus.name)
        .join(Course, and_(Course.tenant_id == Batch.tenant_id, Course.id == Batch.course_id))
        .join(Campus, and_(Campus.tenant_id == Batch.tenant_id, Campus.id == Batch.campus_id))
    )


def _batch_conditions(
    tenant_id: uuid.UUID, context: RequestContext, filters: BatchFilters
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = [
        Batch.tenant_id == tenant_id,
        campus_visibility(Batch.campus_id, context),
    ]
    if filters.search:
        pattern = f"%{escape_like(filters.search)}%"
        conditions.append(
            or_(
                Batch.code.ilike(pattern, escape="\\"),
                Batch.name.ilike(pattern, escape="\\"),
                Batch.intake_label.ilike(pattern, escape="\\"),
            )
        )
    if filters.statuses:
        conditions.append(Batch.status.in_(sorted(s.value for s in filters.statuses)))
    if filters.course_id is not None:
        conditions.append(Batch.course_id == filters.course_id)
    if filters.campus_id is not None:
        conditions.append(Batch.campus_id == filters.campus_id)
    if filters.has_seats is True:
        conditions.append(Batch.allocated_count < Batch.capacity)
    elif filters.has_seats is False:
        conditions.append(Batch.allocated_count >= Batch.capacity)
    return conditions


async def search_batches(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    context: RequestContext,
    filters: BatchFilters,
    page: PageParams,
    sort: Sequence[SortField],
) -> tuple[list[BatchRow], int]:
    conditions = _batch_conditions(tenant_id, context, filters)
    total = await db.scalar(select(func.count()).select_from(Batch).where(*conditions))
    columns = {
        "start_date": Batch.start_date,
        "code": Batch.code,
        "name": func.lower(Batch.name),
        "created_at": Batch.created_at,
    }
    order = [columns[f.name].desc() if f.descending else columns[f.name].asc() for f in sort]
    statement = (
        _batch_select()
        .where(*conditions)
        .order_by(*order, Batch.id)
        .limit(page.limit)
        .offset(page.offset)
    )
    rows = [BatchRow(*row) for row in (await db.execute(statement)).all()]
    return rows, int(total or 0)


async def batch_view(
    db: AsyncSession, tenant_id: uuid.UUID, batch_id: uuid.UUID
) -> BatchRow | None:
    statement = (
        _batch_select()
        .where(Batch.tenant_id == tenant_id, Batch.id == batch_id)
        .execution_options(populate_existing=True)
    )
    row = (await db.execute(statement)).one_or_none()
    return BatchRow(*row) if row else None


# --- Allocations ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AllocationRow:
    id: uuid.UUID
    batch_id: uuid.UUID
    batch_code: str
    batch_name: str
    course_id: uuid.UUID
    course_code: str
    course_name: str
    campus_id: uuid.UUID
    campus_name: str
    admission_id: uuid.UUID
    admission_number: str
    admission_status: str
    student_id: uuid.UUID
    student_number: str
    student_name: str
    status: str
    payment_basis: str
    override_reason: str | None
    override_invoice_state: str | None
    override_outstanding_minor: int | None
    transferred_from_id: uuid.UUID | None
    transferred_from_batch_code: str | None
    transferred_to_batch_code: str | None
    allocated_at: datetime
    allocated_by_name: str | None
    end_reason: str | None
    end_note: str | None
    ended_at: datetime | None
    ended_by_name: str | None
    version: int


def _allocation_select() -> Any:
    return (
        select(
            BatchAllocation.id,
            BatchAllocation.batch_id,
            Batch.code.label("batch_code"),
            Batch.name.label("batch_name"),
            BatchAllocation.course_id,
            Course.code.label("course_code"),
            Course.name.label("course_name"),
            BatchAllocation.campus_id,
            Campus.name.label("campus_name"),
            BatchAllocation.admission_id,
            Admission.admission_number,
            Admission.status.label("admission_status"),
            BatchAllocation.student_id,
            Student.student_number,
            Student.full_name.label("student_name"),
            BatchAllocation.status,
            BatchAllocation.payment_basis,
            BatchAllocation.override_reason,
            BatchAllocation.override_invoice_state,
            BatchAllocation.override_outstanding_minor,
            BatchAllocation.transferred_from_id,
            FromBatch.code.label("transferred_from_batch_code"),
            NextBatch.code.label("transferred_to_batch_code"),
            BatchAllocation.allocated_at,
            AllocatorUser.display_name.label("allocated_by_name"),
            BatchAllocation.end_reason,
            BatchAllocation.end_note,
            BatchAllocation.ended_at,
            EnderUser.display_name.label("ended_by_name"),
            BatchAllocation.version,
        )
        .join(
            Batch,
            and_(
                Batch.tenant_id == BatchAllocation.tenant_id, Batch.id == BatchAllocation.batch_id
            ),
        )
        .join(
            Course,
            and_(
                Course.tenant_id == BatchAllocation.tenant_id,
                Course.id == BatchAllocation.course_id,
            ),
        )
        .join(
            Campus,
            and_(
                Campus.tenant_id == BatchAllocation.tenant_id,
                Campus.id == BatchAllocation.campus_id,
            ),
        )
        .join(
            Admission,
            and_(
                Admission.tenant_id == BatchAllocation.tenant_id,
                Admission.id == BatchAllocation.admission_id,
            ),
        )
        .join(
            Student,
            and_(
                Student.tenant_id == BatchAllocation.tenant_id,
                Student.id == BatchAllocation.student_id,
            ),
        )
        .outerjoin(
            FromAllocation,
            and_(
                FromAllocation.tenant_id == BatchAllocation.tenant_id,
                FromAllocation.id == BatchAllocation.transferred_from_id,
            ),
        )
        .outerjoin(
            FromBatch,
            and_(
                FromBatch.tenant_id == FromAllocation.tenant_id,
                FromBatch.id == FromAllocation.batch_id,
            ),
        )
        .outerjoin(
            NextAllocation,
            and_(
                NextAllocation.tenant_id == BatchAllocation.tenant_id,
                NextAllocation.transferred_from_id == BatchAllocation.id,
            ),
        )
        .outerjoin(
            NextBatch,
            and_(
                NextBatch.tenant_id == NextAllocation.tenant_id,
                NextBatch.id == NextAllocation.batch_id,
            ),
        )
        .outerjoin(
            AllocatorMembership,
            and_(
                AllocatorMembership.tenant_id == BatchAllocation.tenant_id,
                AllocatorMembership.id == BatchAllocation.allocated_by_membership_id,
            ),
        )
        .outerjoin(AllocatorUser, AllocatorUser.id == AllocatorMembership.user_id)
        .outerjoin(
            EnderMembership,
            and_(
                EnderMembership.tenant_id == BatchAllocation.tenant_id,
                EnderMembership.id == BatchAllocation.ended_by_membership_id,
            ),
        )
        .outerjoin(EnderUser, EnderUser.id == EnderMembership.user_id)
    )


@dataclass(frozen=True, slots=True)
class AllocationFilters:
    batch_id: uuid.UUID | None = None
    student_id: uuid.UUID | None = None
    statuses: Collection[AllocationStatus] = ()
    search: str | None = None


async def search_allocations(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    context: RequestContext,
    filters: AllocationFilters,
    page: PageParams,
) -> tuple[list[AllocationRow], int]:
    conditions: list[ColumnElement[bool]] = [
        BatchAllocation.tenant_id == tenant_id,
        campus_visibility(BatchAllocation.campus_id, context),
    ]
    if filters.batch_id is not None:
        conditions.append(BatchAllocation.batch_id == filters.batch_id)
    if filters.student_id is not None:
        conditions.append(BatchAllocation.student_id == filters.student_id)
    if filters.statuses:
        conditions.append(BatchAllocation.status.in_(sorted(s.value for s in filters.statuses)))
    count = select(func.count()).select_from(BatchAllocation)
    if filters.search:
        pattern = f"%{escape_like(filters.search)}%"
        conditions.append(
            or_(
                Student.full_name.ilike(pattern, escape="\\"),
                Student.student_number.ilike(pattern, escape="\\"),
            )
        )
        count = count.join(
            Student,
            and_(
                Student.tenant_id == BatchAllocation.tenant_id,
                Student.id == BatchAllocation.student_id,
            ),
        )
    total = await db.scalar(count.where(*conditions))
    statement = (
        _allocation_select()
        .where(*conditions)
        .order_by(
            (BatchAllocation.status == AllocationStatus.ACTIVE.value).desc(),
            BatchAllocation.allocated_at.desc(),
            BatchAllocation.id.desc(),
        )
        .limit(page.limit)
        .offset(page.offset)
    )
    rows = [AllocationRow(**row._mapping) for row in await db.execute(statement)]
    return rows, int(total or 0)


async def allocation_view(
    db: AsyncSession, tenant_id: uuid.UUID, allocation_id: uuid.UUID
) -> AllocationRow | None:
    row = (
        await db.execute(
            _allocation_select().where(
                BatchAllocation.tenant_id == tenant_id, BatchAllocation.id == allocation_id
            )
        )
    ).one_or_none()
    return AllocationRow(**row._mapping) if row else None


async def current_batches(
    db: AsyncSession, tenant_id: uuid.UUID, admission_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, tuple[uuid.UUID, str, str]]:
    """Active allocation per admission: admission → (batch ID, code, name)."""
    if not admission_ids:
        return {}
    statement = (
        select(BatchAllocation.admission_id, Batch.id, Batch.code, Batch.name)
        .join(
            Batch,
            and_(
                Batch.tenant_id == BatchAllocation.tenant_id, Batch.id == BatchAllocation.batch_id
            ),
        )
        .where(
            BatchAllocation.tenant_id == tenant_id,
            BatchAllocation.admission_id.in_(sorted(admission_ids)),
            BatchAllocation.status == AllocationStatus.ACTIVE.value,
        )
    )
    return {row[0]: (row[1], row[2], row[3]) for row in await db.execute(statement)}


# --- Eligible admissions ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EligibleRow:
    admission_id: uuid.UUID
    admission_number: str
    admission_version: int
    approved_at: datetime
    student_id: uuid.UUID
    student_number: str
    student_name: str
    invoice_status: str | None
    invoice_total_minor: int | None
    invoice_paid_minor: int | None


async def eligible_admissions(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    found: Batch,
    *,
    search: str | None,
    page: PageParams,
) -> tuple[list[EligibleRow], int]:
    """ADMITTED admissions of the batch's course and campus, active student, no active
    allocation; with the live fee invoice's position (the payment gate)."""
    active = (
        select(BatchAllocation.id)
        .where(
            BatchAllocation.tenant_id == Admission.tenant_id,
            BatchAllocation.admission_id == Admission.id,
            BatchAllocation.status == AllocationStatus.ACTIVE.value,
        )
        .exists()
    )
    conditions: list[ColumnElement[bool]] = [
        Admission.tenant_id == tenant_id,
        Admission.course_id == found.course_id,
        Admission.campus_id == found.campus_id,
        Admission.status == AdmissionStatus.ADMITTED.value,
        Student.status == StudentStatus.ACTIVE.value,
        ~active,
    ]
    if search:
        pattern = f"%{escape_like(search)}%"
        conditions.append(
            or_(
                Student.full_name.ilike(pattern, escape="\\"),
                Student.student_number.ilike(pattern, escape="\\"),
                Admission.admission_number.ilike(pattern, escape="\\"),
            )
        )
    base = (
        select(literal(1))
        .select_from(Admission)
        .join(
            Student,
            and_(Student.tenant_id == Admission.tenant_id, Student.id == Admission.student_id),
        )
    )
    total = await db.scalar(select(func.count()).select_from(base.where(*conditions).subquery()))
    statement = (
        select(
            Admission.id.label("admission_id"),
            Admission.admission_number,
            Admission.version.label("admission_version"),
            Admission.approved_at,
            Student.id.label("student_id"),
            Student.student_number,
            Student.full_name.label("student_name"),
            Invoice.status.label("invoice_status"),
            Invoice.total_minor.label("invoice_total_minor"),
            Invoice.paid_minor.label("invoice_paid_minor"),
        )
        .select_from(Admission)
        .join(
            Student,
            and_(Student.tenant_id == Admission.tenant_id, Student.id == Admission.student_id),
        )
        .outerjoin(
            Invoice,
            and_(
                Invoice.tenant_id == Admission.tenant_id,
                Invoice.admission_id == Admission.id,
                Invoice.status != "CANCELLED",
            ),
        )
        .where(*conditions)
        .order_by(Admission.approved_at.asc(), Admission.id)
        .limit(page.limit)
        .offset(page.offset)
    )
    rows = [EligibleRow(**row._mapping) for row in await db.execute(statement)]
    return rows, int(total or 0)


# --- Activity ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ActivityRow:
    id: uuid.UUID
    kind: str
    actor_membership_id: uuid.UUID | None
    details: dict[str, Any]
    body: str | None
    created_at: datetime


async def activity_of_batch(
    db: AsyncSession, tenant_id: uuid.UUID, batch_id: uuid.UUID, page: PageParams
) -> tuple[list[ActivityRow], int]:
    conditions = [BatchActivity.tenant_id == tenant_id, BatchActivity.batch_id == batch_id]
    total = await db.scalar(select(func.count()).select_from(BatchActivity).where(*conditions))
    statement = (
        select(
            BatchActivity.id,
            BatchActivity.kind,
            BatchActivity.actor_membership_id,
            BatchActivity.details,
            literal(None).label("body"),
            BatchActivity.created_at,
        )
        .where(*conditions)
        .order_by(BatchActivity.created_at.desc(), BatchActivity.id.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    rows = [ActivityRow(**row._mapping) for row in await db.execute(statement)]
    return rows, int(total or 0)
