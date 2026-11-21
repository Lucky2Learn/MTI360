"""Development seed: batches, allocations, transfers and withdrawals (Phase 02-6; ADR-0025).

Part of ``app.seed``: development only, fictitious people. Rows go through the
same tables, keys, CHECKs and seat-count trigger as the API and carry what the
API would have written for the same history: batches start ``OPEN``; each
allocation moves its admission to ``ENROLLED``; a transfer ends the earlier
allocation (``TRANSFERRED``) and starts one with basis ``TRANSFER``; a
withdrawal ends it (``WITHDRAWN``) and returns the admission to ``ADMITTED``;
a batch's final status (``CLOSED`` or ``CANCELLED``) is applied last; the
batch activity timeline (and so Student 360's history) records every step.

Before anything is written, the file is checked against the API's rules:
active course; campus of the institute; unique code; capacity 1-500; the
actor holds ``batch.manage`` / ``batch.allocate`` for the batch's campus; the
admission is admitted to the batch's course at its campus and allocated at
most once; seats are never exceeded (transfers included); a transfer goes to
another batch of the same course and campus; the payment gate (decision B):
a fully paid live fee invoice allocates without a reason, anything else
(outstanding, no invoice, only a cancelled one) needs an override reason.

Dates are relative to the database's IST date when the seed runs
(``starts_in_days``, ``duration_days``); codes, statuses and allocations are
the same on every run. A second run is refused by ``app.seed`` (``--tag``
loads an independent copy).
"""

import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final, cast

from sqlalchemy import Table, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.activity import activity_details
from app.modules.batches.domain import (
    INTAKE_MAX_LENGTH,
    REASON_MAX_LENGTH,
    ActivityKind,
    AllocationStatus,
    BatchStatus,
    EndReason,
    InvoiceState,
    PaymentBasis,
    capacity_valid,
    clean_name,
    clean_reason,
    normalize_code,
)
from app.modules.batches.models import Batch, BatchActivity, BatchAllocation
from app.modules.batches.permissions import BATCH_ALLOCATE, BATCH_MANAGE
from app.modules.courses.domain import CourseStatus
from app.modules.finance.invoice_repository import today
from app.modules.students.domain import AdmissionStatus
from app.modules.students.models import Admission
from app.seed_finance import Actor, SeededAdmission, SeedFinance

BATCHES = cast(Table, Batch.__table__)
ALLOCATIONS = cast(Table, BatchAllocation.__table__)
ACTIVITIES = cast(Table, BatchActivity.__table__)
ADMISSIONS = cast(Table, Admission.__table__)
MAX_DAYS: Final = 3650


class BatchSeedError(ValueError):
    """An invalid batches section of the seed file; the message is safe to print."""


@dataclass(frozen=True, slots=True)
class SeedBatch:
    key: str
    code: str
    course: str
    campus: str
    name: str
    intake_label: str | None
    starts_in_days: int
    duration_days: int
    capacity: int
    status: BatchStatus
    status_reason: str | None
    created_by: str


@dataclass(frozen=True, slots=True)
class SeedMove:
    """A transfer (``to`` set) or a withdrawal (``to`` ``None``) of an allocation."""

    to: str | None
    reason: str
    by: str


@dataclass(frozen=True, slots=True)
class SeedAllocation:
    batch: str
    application: str
    allocated_by: str
    override_reason: str | None
    invoice_state: InvoiceState
    outstanding_minor: int | None
    transfer: SeedMove | None
    withdraw: SeedMove | None


@dataclass(frozen=True, slots=True)
class SeedBatches:
    batches: tuple[SeedBatch, ...] = ()
    allocations: tuple[SeedAllocation, ...] = ()


# --- Parsing --------------------------------------------------------------------------------


def _int(item: Mapping[str, Any], key: str, at: str, *, low: int, high: int) -> int:
    value = item.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise BatchSeedError(f"{at}.{key}: an integer from {low} to {high} is required")
    return value


def _actor(actors: Mapping[str, Actor], email: Any, at: str) -> str:
    if not isinstance(email, str) or email not in actors:
        raise BatchSeedError(f"{at}: a member of the institute is required")
    return email


def _payment(finance: SeedFinance, application: str) -> tuple[InvoiceState, int | None]:
    """The live fee invoice's position (the API's gate): cancelled ones do not count."""
    live = [i for i in finance.invoices if i.application == application and i.cancel_reason is None]
    if not live:
        return InvoiceState.NO_INVOICE, None
    invoice = live[-1]
    state = InvoiceState(invoice.status.value)
    return state, max(invoice.total_minor - invoice.paid_minor, 0)


def parse_batches(
    raw_batches: Sequence[Mapping[str, Any]],
    where: str,
    *,
    courses: Mapping[str, CourseStatus],
    campuses: set[str],
    actors: Mapping[str, Actor],
) -> tuple[SeedBatch, ...]:
    batches: list[SeedBatch] = []
    keys: set[str] = set()
    codes: set[str] = set()
    for index, item in enumerate(raw_batches):
        at = f"{where}.batches[{index}]"
        key = item.get("key")
        if not isinstance(key, str) or not key or key in keys:
            raise BatchSeedError(f"{at}.key: a unique key is required")
        keys.add(key)
        code = normalize_code(str(item.get("code", "")))
        if code is None or code in codes:
            raise BatchSeedError(f"{at}.code: a unique batch code is required")
        codes.add(code)
        course = item.get("course")
        if courses.get(str(course)) is not CourseStatus.ACTIVE:
            raise BatchSeedError(f"{at}.course: an ACTIVE course of the institute is required")
        campus = item.get("campus")
        if campus not in campuses:
            raise BatchSeedError(f"{at}.campus: a campus of the institute is required")
        name = clean_name(str(item.get("name", "")))
        if name is None:
            raise BatchSeedError(f"{at}.name: 1-200 characters are required")
        raw_intake = item.get("intake_label")
        intake = clean_name(str(raw_intake), INTAKE_MAX_LENGTH) if raw_intake else None
        if raw_intake and intake is None:
            raise BatchSeedError(f"{at}.intake_label: at most 100 characters")
        capacity = _int(item, "capacity", at, low=0, high=1000)
        if not capacity_valid(capacity):
            raise BatchSeedError(f"{at}.capacity: from 1 to 500")
        try:
            status = BatchStatus(item.get("status", BatchStatus.OPEN.value))
        except ValueError:
            raise BatchSeedError(f"{at}.status: OPEN, CLOSED or CANCELLED") from None
        raw_reason = item.get("status_reason")
        status_reason = clean_reason(str(raw_reason)) if raw_reason else None
        if raw_reason and status_reason is None:
            raise BatchSeedError(f"{at}.status_reason: at most {REASON_MAX_LENGTH} characters")
        created_by = _actor(actors, item.get("created_by"), f"{at}.created_by")
        if not actors[created_by].may(BATCH_MANAGE.code, str(campus)):
            raise BatchSeedError(f"{at}.created_by: needs batch.manage at {campus}")
        batches.append(
            SeedBatch(
                key=key,
                code=code,
                course=str(course),
                campus=str(campus),
                name=name,
                intake_label=intake,
                starts_in_days=_int(item, "starts_in_days", at, low=-MAX_DAYS, high=MAX_DAYS),
                duration_days=_int(item, "duration_days", at, low=0, high=MAX_DAYS),
                capacity=capacity,
                status=status,
                status_reason=status_reason,
                created_by=created_by,
            )
        )
    return tuple(batches)


def _move(raw: Any, at: str, actors: Mapping[str, Actor], *, transfer: bool) -> SeedMove | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise BatchSeedError(f"{at}: an object is required")
    reason = clean_reason(str(raw.get("reason", "")))
    if reason is None:
        raise BatchSeedError(f"{at}.reason: a reason of up to 500 characters is required")
    to = raw.get("to") if transfer else None
    if transfer and not isinstance(to, str):
        raise BatchSeedError(f"{at}.to: the key of the batch to move to is required")
    return SeedMove(to, reason, _actor(actors, raw.get("by"), f"{at}.by"))


def parse_allocations(
    raw_allocations: Sequence[Mapping[str, Any]],
    where: str,
    *,
    batches: Sequence[SeedBatch],
    admitted: Mapping[str, tuple[str, str]],
    finance: SeedFinance,
    actors: Mapping[str, Actor],
) -> tuple[SeedAllocation, ...]:
    """Validate allocations in file order, replaying seats as the API would see them."""
    by_key = {batch.key: batch for batch in batches}
    seats: Counter[str] = Counter()
    seen: set[str] = set()
    allocations: list[SeedAllocation] = []

    def take(batch: SeedBatch, at: str) -> None:
        if seats[batch.key] >= batch.capacity:
            raise BatchSeedError(f"{at}: batch {batch.key} is full")
        seats[batch.key] += 1

    for index, item in enumerate(raw_allocations):
        at = f"{where}.allocations[{index}]"
        batch = by_key.get(str(item.get("batch")))
        if batch is None:
            raise BatchSeedError(f"{at}.batch: the key of a batch above is required")
        application = str(item.get("application"))
        if application not in admitted:
            raise BatchSeedError(f"{at}.application: an ADMITTED application is required")
        if application in seen:
            raise BatchSeedError(f"{at}.application: allocated once only (then transfer)")
        seen.add(application)
        if admitted[application] != (batch.course, batch.campus):
            raise BatchSeedError(f"{at}: the admission's course and campus must be the batch's")
        allocated_by = _actor(actors, item.get("allocated_by"), f"{at}.allocated_by")
        if not actors[allocated_by].may(BATCH_ALLOCATE.code, batch.campus):
            raise BatchSeedError(f"{at}.allocated_by: needs batch.allocate at {batch.campus}")
        state, outstanding = _payment(finance, application)
        raw_override = item.get("override_reason")
        override = clean_reason(str(raw_override)) if raw_override else None
        if state is InvoiceState.PAID and raw_override:
            raise BatchSeedError(f"{at}.override_reason: the fees are paid; no override")
        if state is not InvoiceState.PAID and override is None:
            raise BatchSeedError(
                f"{at}.override_reason: fees are not fully paid ({state.value}); "
                "a payment override reason is required"
            )
        take(batch, at)
        transfer = _move(item.get("transfer"), f"{at}.transfer", actors, transfer=True)
        current = batch
        if transfer is not None:
            target = by_key.get(str(transfer.to))
            if target is None or target.key == batch.key:
                raise BatchSeedError(f"{at}.transfer.to: another batch above is required")
            if (target.course, target.campus) != (batch.course, batch.campus):
                raise BatchSeedError(f"{at}.transfer.to: same course and campus only")
            if not actors[transfer.by].may(BATCH_ALLOCATE.code, batch.campus):
                raise BatchSeedError(f"{at}.transfer.by: needs batch.allocate")
            seats[batch.key] -= 1
            take(target, f"{at}.transfer")
            current = target
        withdraw = _move(item.get("withdraw"), f"{at}.withdraw", actors, transfer=False)
        if withdraw is not None:
            if not actors[withdraw.by].may(BATCH_ALLOCATE.code, batch.campus):
                raise BatchSeedError(f"{at}.withdraw.by: needs batch.allocate")
            seats[current.key] -= 1
        allocations.append(
            SeedAllocation(
                batch=batch.key,
                application=application,
                allocated_by=allocated_by,
                override_reason=override if state is not InvoiceState.PAID else None,
                invoice_state=state,
                outstanding_minor=outstanding if outstanding else None,
                transfer=transfer,
                withdraw=withdraw,
            )
        )
    for batch in batches:
        if batch.status is BatchStatus.CANCELLED and seats[batch.key]:
            raise BatchSeedError(f"{where}.batches: {batch.key} is cancelled with students")
    return tuple(allocations)


def parse_batch_section(
    raw: Mapping[str, Any],
    where: str,
    *,
    courses: Mapping[str, CourseStatus],
    campuses: set[str],
    admitted: Mapping[str, tuple[str, str]],
    finance: SeedFinance,
    actors: Mapping[str, Actor],
) -> SeedBatches:
    """Validate an institute's ``batches`` and ``allocations`` (the API's rules)."""
    batches = parse_batches(
        raw.get("batches", ()), where, courses=courses, campuses=campuses, actors=actors
    )
    allocations = parse_allocations(
        raw.get("allocations", ()),
        where,
        batches=batches,
        admitted=admitted,
        finance=finance,
        actors=actors,
    )
    return SeedBatches(batches, allocations)


# --- Writing --------------------------------------------------------------------------------


async def _activity(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    batch_id: uuid.UUID,
    kind: ActivityKind,
    actor: uuid.UUID,
    *,
    allocation_id: uuid.UUID | None = None,
    extra: Mapping[str, object] | None = None,
    **details: object,
) -> None:
    await db.execute(
        insert(ACTIVITIES).values(
            id=uuid.uuid7(),
            tenant_id=tenant_id,
            batch_id=batch_id,
            allocation_id=allocation_id,
            kind=kind.value,
            actor_membership_id=actor,
            details=activity_details({**details, **(extra or {})}),
        )
    )


async def _set_admission(
    db: AsyncSession, admission_id: uuid.UUID, status: AdmissionStatus
) -> None:
    await db.execute(
        update(ADMISSIONS)
        .where(ADMISSIONS.c.id == admission_id)
        .values(status=status.value, version=ADMISSIONS.c.version + 1, updated_at=func.now())
    )


async def _end(
    db: AsyncSession, allocation_id: uuid.UUID, reason: EndReason, move: SeedMove, by: uuid.UUID
) -> None:
    await db.execute(
        update(ALLOCATIONS)
        .where(ALLOCATIONS.c.id == allocation_id)
        .values(
            status=AllocationStatus.ENDED.value,
            end_reason=reason.value,
            end_note=move.reason,
            ended_at=func.now(),
            ended_by_membership_id=by,
            version=ALLOCATIONS.c.version + 1,
            updated_at=func.now(),
        )
    )


async def seed_batches(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    section: SeedBatches,
    course_ids: Mapping[str, uuid.UUID],
    campus_ids: Mapping[str, uuid.UUID],
    admissions: Mapping[str, SeededAdmission],
    memberships: Mapping[str, uuid.UUID],
) -> None:
    """Insert one institute's batches and replay its allocations, transfers and
    withdrawals in file order; then apply each batch's final status."""
    if not section.batches:
        return
    on = await today(db)
    ids: dict[str, uuid.UUID] = {}
    by_key = {batch.key: batch for batch in section.batches}
    for batch in section.batches:
        ids[batch.key] = uuid.uuid7()
        start = on + timedelta(days=batch.starts_in_days)
        await db.execute(
            insert(BATCHES).values(
                id=ids[batch.key],
                tenant_id=tenant_id,
                course_id=course_ids[batch.course],
                campus_id=campus_ids[batch.campus],
                code=batch.code,
                name=batch.name,
                intake_label=batch.intake_label,
                start_date=start,
                end_date=start + timedelta(days=batch.duration_days),
                capacity=batch.capacity,
                status=BatchStatus.OPEN.value,
                created_by_membership_id=memberships[batch.created_by],
                version=1,
            )
        )
        await _activity(
            db,
            tenant_id,
            ids[batch.key],
            ActivityKind.CREATED,
            memberships[batch.created_by],
            code=batch.code,
        )
    rows = await db.execute(
        select(ADMISSIONS.c.id, ADMISSIONS.c.admission_number).where(
            ADMISSIONS.c.tenant_id == tenant_id,
            ADMISSIONS.c.id.in_([a.admission_id for a in admissions.values()]),
        )
    )
    numbers: dict[uuid.UUID, str] = {row[0]: row[1] for row in rows}
    for allocation in section.allocations:
        batch = by_key[allocation.batch]
        admission = admissions[allocation.application]
        number = numbers[admission.admission_id]
        actor = memberships[allocation.allocated_by]
        overridden = allocation.override_reason is not None
        first = uuid.uuid7()
        await db.execute(
            insert(ALLOCATIONS).values(
                id=first,
                tenant_id=tenant_id,
                batch_id=ids[batch.key],
                course_id=admission.course_id,
                campus_id=admission.campus_id,
                admission_id=admission.admission_id,
                student_id=admission.student_id,
                status=AllocationStatus.ACTIVE.value,
                payment_basis=(PaymentBasis.OVERRIDE if overridden else PaymentBasis.PAID).value,
                override_reason=allocation.override_reason,
                override_invoice_state=allocation.invoice_state.value if overridden else None,
                override_outstanding_minor=allocation.outstanding_minor if overridden else None,
                allocated_by_membership_id=actor,
                version=1,
            )
        )
        await _set_admission(db, admission.admission_id, AdmissionStatus.ENROLLED)
        await _activity(
            db,
            tenant_id,
            ids[batch.key],
            ActivityKind.ALLOCATED,
            actor,
            allocation_id=first,
            batch_code=batch.code,
            admission_number=number,
            payment_basis=(PaymentBasis.OVERRIDE if overridden else PaymentBasis.PAID).value,
            invoice_state=allocation.invoice_state.value if overridden else None,
            outstanding_minor=allocation.outstanding_minor if overridden else None,
        )
        current, current_id = batch, first
        if allocation.transfer is not None:
            target = by_key[str(allocation.transfer.to)]
            mover = memberships[allocation.transfer.by]
            await _end(db, first, EndReason.TRANSFERRED, allocation.transfer, mover)
            moved = uuid.uuid7()
            await db.execute(
                insert(ALLOCATIONS).values(
                    id=moved,
                    tenant_id=tenant_id,
                    batch_id=ids[target.key],
                    course_id=admission.course_id,
                    campus_id=admission.campus_id,
                    admission_id=admission.admission_id,
                    student_id=admission.student_id,
                    status=AllocationStatus.ACTIVE.value,
                    payment_basis=PaymentBasis.TRANSFER.value,
                    transferred_from_id=first,
                    allocated_by_membership_id=mover,
                    version=1,
                )
            )
            details = {
                "from_batch_code": batch.code,
                "to_batch_code": target.code,
                "admission_number": number,
            }
            await _activity(
                db,
                tenant_id,
                ids[batch.key],
                ActivityKind.TRANSFERRED_OUT,
                mover,
                allocation_id=first,
                extra=details,
            )
            await _activity(
                db,
                tenant_id,
                ids[target.key],
                ActivityKind.TRANSFERRED_IN,
                mover,
                allocation_id=moved,
                extra=details,
            )
            current, current_id = target, moved
        if allocation.withdraw is not None:
            by = memberships[allocation.withdraw.by]
            await _end(db, current_id, EndReason.WITHDRAWN, allocation.withdraw, by)
            await _set_admission(db, admission.admission_id, AdmissionStatus.ADMITTED)
            await _activity(
                db,
                tenant_id,
                ids[current.key],
                ActivityKind.WITHDRAWN,
                by,
                allocation_id=current_id,
                batch_code=current.code,
                admission_number=number,
            )
    for batch in section.batches:
        if batch.status is BatchStatus.OPEN:
            continue
        await db.execute(
            update(BATCHES)
            .where(BATCHES.c.id == ids[batch.key])
            .values(
                status=batch.status.value,
                status_reason=batch.status_reason,
                version=BATCHES.c.version + 1,
                updated_at=func.now(),
            )
        )
        await _activity(
            db,
            tenant_id,
            ids[batch.key],
            ActivityKind.STATUS_CHANGED,
            memberships[batch.created_by],
            extra={
                "from": BatchStatus.OPEN.value,
                "to": batch.status.value,
                "has_reason": batch.status_reason is not None,
            },
        )
