"""Fee invoice, payment and receipt data access (Phase 02-5; ADR-0022).

Explicit tenant predicates on every statement (and the ORM tenant filter and
Row-Level Security behind them). Lists apply
:func:`app.core.authz.campus_visibility` to the fee invoice's campus, so a
restricted member never receives a row ``authorize()`` would answer with 404
— including through the ``student_id`` filter of Student 360 (addendum R2).
Locks (``FOR UPDATE``) are taken in one order: admission, invoice, payment.
"""

import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Final

from sqlalchemy import ColumnElement, Date, and_, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.authz import campus_visibility
from app.core.context import RequestContext
from app.core.pagination import PageParams, SortField
from app.core.search import escape_like
from app.core.sequences.numbering import IST_ZONE
from app.modules.courses.models import Course
from app.modules.finance.domain import InvoiceStatus, PaymentMethod, PaymentStatus
from app.modules.finance.models import FinanceActivity, Invoice, InvoiceLine, Payment, Receipt
from app.modules.identity.models import TenantMembership, User
from app.modules.institute.models import Campus
from app.modules.students.models import Admission, Student

Actor = aliased(TenantMembership, name="finance_actor")
ActorUser = aliased(User, name="finance_actor_user")
Recorder = aliased(TenantMembership, name="payment_recorder")
RecorderUser = aliased(User, name="payment_recorder_user")
LIVE = (InvoiceStatus.ISSUED.value, InvoiceStatus.PARTIALLY_PAID.value, InvoiceStatus.PAID.value)
UNPAID = (InvoiceStatus.ISSUED.value, InvoiceStatus.PARTIALLY_PAID.value)


def ist_today() -> ColumnElement[date]:
    """SQL: today's date in India Standard Time (the date that decides overdue)."""
    return cast(func.timezone(IST_ZONE, func.now()), Date)


async def today(db: AsyncSession) -> date:
    found: date | None = await db.scalar(select(ist_today()))
    if found is None:  # pragma: no cover - now() is never NULL
        raise RuntimeError("the database clock gave no date")
    return found


def _like(column: Any, pattern: str) -> ColumnElement[bool]:
    return column.ilike(pattern, escape="\\")  # type: ignore[no-any-return]


# --- Rows used by the commands -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AdmissionRef:
    id: uuid.UUID
    number: str
    student_id: uuid.UUID
    course_id: uuid.UUID
    campus_id: uuid.UUID


async def admission(
    db: AsyncSession, tenant_id: uuid.UUID, admission_id: uuid.UUID, *, lock: bool
) -> AdmissionRef | None:
    """The admission of the trusted tenant; locked to serialise fee invoice issue for it."""
    statement = select(Admission).where(
        Admission.tenant_id == tenant_id, Admission.id == admission_id
    )
    if lock:
        statement = statement.with_for_update()
    found = await db.scalar(statement)
    if found is None:
        return None
    return AdmissionRef(
        found.id, found.admission_number, found.student_id, found.course_id, found.campus_id
    )


async def student_number(db: AsyncSession, tenant_id: uuid.UUID, student_id: uuid.UUID) -> str:
    found: str | None = await db.scalar(
        select(Student.student_number).where(
            Student.tenant_id == tenant_id, Student.id == student_id
        )
    )
    if found is None:  # pragma: no cover - the composite key guarantees the student
        raise LookupError("student")
    return found


async def invoice(
    db: AsyncSession, tenant_id: uuid.UUID, invoice_id: uuid.UUID, *, lock: bool = False
) -> Invoice | None:
    statement = select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.id == invoice_id)
    if lock:
        statement = statement.with_for_update()
    found: Invoice | None = await db.scalar(statement)
    return found


async def invoice_by_key(db: AsyncSession, tenant_id: uuid.UUID, key: uuid.UUID) -> Invoice | None:
    found: Invoice | None = await db.scalar(
        select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.idempotency_key == key)
    )
    return found


async def live_invoice_of(
    db: AsyncSession, tenant_id: uuid.UUID, admission_id: uuid.UUID
) -> uuid.UUID | None:
    found: uuid.UUID | None = await db.scalar(
        select(Invoice.id).where(
            Invoice.tenant_id == tenant_id,
            Invoice.admission_id == admission_id,
            Invoice.status.in_(LIVE),
        )
    )
    return found


async def payment(
    db: AsyncSession, tenant_id: uuid.UUID, payment_id: uuid.UUID, *, lock: bool = False
) -> Payment | None:
    statement = select(Payment).where(Payment.tenant_id == tenant_id, Payment.id == payment_id)
    if lock:
        statement = statement.with_for_update()
    found: Payment | None = await db.scalar(statement)
    return found


async def payment_by_key(db: AsyncSession, tenant_id: uuid.UUID, key: uuid.UUID) -> Payment | None:
    found: Payment | None = await db.scalar(
        select(Payment).where(Payment.tenant_id == tenant_id, Payment.idempotency_key == key)
    )
    return found


async def receipt_of(
    db: AsyncSession, tenant_id: uuid.UUID, payment_id: uuid.UUID
) -> Receipt | None:
    found: Receipt | None = await db.scalar(
        select(Receipt).where(Receipt.tenant_id == tenant_id, Receipt.payment_id == payment_id)
    )
    return found


async def open_payments(
    db: AsyncSession, tenant_id: uuid.UUID, invoice_id: uuid.UUID
) -> dict[PaymentStatus, tuple[int, int]]:
    """``(count, amount)`` of the invoice's ``PENDING`` and ``CONFIRMED`` payments."""
    rows = (
        await db.execute(
            select(
                Payment.status,
                func.count(Payment.id),
                func.coalesce(func.sum(Payment.amount_minor), 0),
            )
            .where(
                Payment.tenant_id == tenant_id,
                Payment.invoice_id == invoice_id,
                Payment.status.in_([PaymentStatus.PENDING.value, PaymentStatus.CONFIRMED.value]),
            )
            .group_by(Payment.status)
        )
    ).all()
    return {PaymentStatus(row[0]): (int(row[1]), int(row[2])) for row in rows}


async def confirmed_total(db: AsyncSession, tenant_id: uuid.UUID, invoice_id: uuid.UUID) -> int:
    """The sum of the invoice's ``CONFIRMED`` payments: what ``paid_minor`` must equal."""
    total = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount_minor), 0)).where(
            Payment.tenant_id == tenant_id,
            Payment.invoice_id == invoice_id,
            Payment.status == PaymentStatus.CONFIRMED.value,
        )
    )
    return int(total or 0)


# --- Fee invoice views ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class InvoiceRow:
    invoice: Invoice
    admission_number: str
    student_number: str
    student_name: str
    course_code: str
    course_name: str
    campus_code: str
    overdue: bool


@dataclass(frozen=True, slots=True)
class InvoiceFilters:
    search: str | None = None
    statuses: Collection[InvoiceStatus] = ()
    campus_id: uuid.UUID | None = None
    course_id: uuid.UUID | None = None
    student_id: uuid.UUID | None = None
    due_from: date | None = None
    due_to: date | None = None
    overdue: bool | None = None
    outstanding: bool | None = None


INVOICE_SORT_COLUMNS: Final = {
    "issued_at": Invoice.issued_at,
    "due_date": Invoice.due_date,
    "number": Invoice.number,
    "balance": Invoice.total_minor - Invoice.paid_minor,
}


def overdue_condition() -> ColumnElement[bool]:
    """Unpaid (fully or partly) and past its due date in IST."""
    return and_(Invoice.status.in_(UNPAID), Invoice.due_date < ist_today())


def _invoice_columns() -> tuple[Any, ...]:
    return (
        Invoice,
        Admission.admission_number,
        Student.student_number,
        Student.full_name,
        Course.code,
        Course.name,
        Campus.code,
        overdue_condition().label("overdue"),
    )


def _invoice_joins(statement: Any) -> Any:
    return (
        statement.join(
            Admission,
            and_(Admission.tenant_id == Invoice.tenant_id, Admission.id == Invoice.admission_id),
        )
        .join(
            Student,
            and_(Student.tenant_id == Invoice.tenant_id, Student.id == Invoice.student_id),
        )
        .join(Course, and_(Course.tenant_id == Invoice.tenant_id, Course.id == Invoice.course_id))
        .join(Campus, and_(Campus.tenant_id == Invoice.tenant_id, Campus.id == Invoice.campus_id))
    )


def _invoice_row(row: Any) -> InvoiceRow:
    return InvoiceRow(row[0], row[1], row[2], row[3], row[4], row[5], row[6], bool(row[7]))


def _invoice_conditions(
    context: RequestContext, tenant_id: uuid.UUID, filters: InvoiceFilters
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = [
        Invoice.tenant_id == tenant_id,
        campus_visibility(Invoice.campus_id, context),
    ]
    if filters.search:
        pattern = f"%{escape_like(filters.search)}%"
        conditions.append(
            or_(
                _like(Invoice.number, pattern),
                _like(Admission.admission_number, pattern),
                _like(Student.student_number, pattern),
                _like(Student.full_name, pattern),
            )
        )
    if filters.statuses:
        conditions.append(Invoice.status.in_(sorted(s.value for s in filters.statuses)))
    if filters.campus_id is not None:
        conditions.append(Invoice.campus_id == filters.campus_id)
    if filters.course_id is not None:
        conditions.append(Invoice.course_id == filters.course_id)
    if filters.student_id is not None:
        conditions.append(Invoice.student_id == filters.student_id)
    if filters.due_from is not None:
        conditions.append(Invoice.due_date >= filters.due_from)
    if filters.due_to is not None:
        conditions.append(Invoice.due_date <= filters.due_to)
    if filters.overdue is not None:
        conditions.append(overdue_condition() if filters.overdue else ~overdue_condition())
    if filters.outstanding is not None:
        unpaid = Invoice.status.in_(UNPAID)
        conditions.append(unpaid if filters.outstanding else ~unpaid)
    return conditions


async def search_invoices(
    db: AsyncSession,
    context: RequestContext,
    tenant_id: uuid.UUID,
    filters: InvoiceFilters,
    page: PageParams,
    sort: Sequence[SortField],
) -> tuple[list[InvoiceRow], int]:
    conditions = _invoice_conditions(context, tenant_id, filters)
    total = await db.scalar(
        _invoice_joins(select(func.count(Invoice.id)).select_from(Invoice)).where(*conditions)
    )
    order = [
        INVOICE_SORT_COLUMNS[f.name].desc() if f.descending else INVOICE_SORT_COLUMNS[f.name]
        for f in sort
    ]
    statement = (
        _invoice_joins(select(*_invoice_columns()).select_from(Invoice))
        .where(*conditions)
        .order_by(*order, Invoice.id.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    rows = (await db.execute(statement)).all()
    return [_invoice_row(row) for row in rows], int(total or 0)


async def invoice_view(
    db: AsyncSession, tenant_id: uuid.UUID, invoice_id: uuid.UUID
) -> InvoiceRow | None:
    row = (
        await db.execute(
            _invoice_joins(select(*_invoice_columns()).select_from(Invoice)).where(
                Invoice.tenant_id == tenant_id, Invoice.id == invoice_id
            )
        )
    ).one_or_none()
    return _invoice_row(row) if row is not None else None


async def lines_of(
    db: AsyncSession, tenant_id: uuid.UUID, invoice_id: uuid.UUID
) -> list[InvoiceLine]:
    return list(
        (
            await db.scalars(
                select(InvoiceLine)
                .where(InvoiceLine.tenant_id == tenant_id, InvoiceLine.invoice_id == invoice_id)
                .order_by(InvoiceLine.position)
            )
        ).all()
    )


@dataclass(frozen=True, slots=True)
class ActivityRow:
    activity: FinanceActivity
    actor_name: str | None


async def activity_of(
    db: AsyncSession, tenant_id: uuid.UUID, invoice_id: uuid.UUID
) -> list[ActivityRow]:
    rows = (
        await db.execute(
            select(FinanceActivity, ActorUser.display_name)
            .outerjoin(
                Actor,
                and_(
                    Actor.tenant_id == FinanceActivity.tenant_id,
                    Actor.id == FinanceActivity.actor_membership_id,
                ),
            )
            .outerjoin(ActorUser, ActorUser.id == Actor.user_id)
            .where(FinanceActivity.tenant_id == tenant_id, FinanceActivity.invoice_id == invoice_id)
            .order_by(FinanceActivity.created_at, FinanceActivity.id)
        )
    ).all()
    return [ActivityRow(row[0], row[1]) for row in rows]


# --- Payment views ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PaymentRow:
    payment: Payment
    receipt: Receipt | None
    invoice_number: str
    student_number: str
    student_name: str
    recorded_by_name: str | None


@dataclass(frozen=True, slots=True)
class PaymentFilters:
    search: str | None = None
    statuses: Collection[PaymentStatus] = ()
    methods: Collection[PaymentMethod] = ()
    campus_id: uuid.UUID | None = None
    received_from: date | None = None
    received_to: date | None = None


PAYMENT_SORT_COLUMNS: Final = {
    "received_on": Payment.received_on,
    "created_at": Payment.created_at,
    "amount": Payment.amount_minor,
}
_PAYMENT_COLUMNS: Final = (
    Payment,
    Receipt,
    Invoice.number,
    Student.student_number,
    Student.full_name,
    RecorderUser.display_name,
)


def _payment_joins(statement: Any) -> Any:
    return (
        statement.join(
            Invoice,
            and_(Invoice.tenant_id == Payment.tenant_id, Invoice.id == Payment.invoice_id),
        )
        .join(
            Student,
            and_(Student.tenant_id == Payment.tenant_id, Student.id == Payment.student_id),
        )
        .outerjoin(
            Receipt,
            and_(Receipt.tenant_id == Payment.tenant_id, Receipt.payment_id == Payment.id),
        )
        .outerjoin(
            Recorder,
            and_(
                Recorder.tenant_id == Payment.tenant_id,
                Recorder.id == Payment.recorded_by_membership_id,
            ),
        )
        .outerjoin(RecorderUser, RecorderUser.id == Recorder.user_id)
    )


def _payment_row(row: Any) -> PaymentRow:
    return PaymentRow(row[0], row[1], row[2], row[3], row[4], row[5])


def _payment_conditions(
    context: RequestContext, tenant_id: uuid.UUID, filters: PaymentFilters
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = [
        Payment.tenant_id == tenant_id,
        campus_visibility(Payment.campus_id, context),
    ]
    if filters.search:
        pattern = f"%{escape_like(filters.search)}%"
        conditions.append(
            or_(
                _like(Invoice.number, pattern),
                _like(Receipt.number, pattern),
                _like(Student.student_number, pattern),
                _like(Student.full_name, pattern),
                _like(Payment.reference, pattern),
            )
        )
    if filters.statuses:
        conditions.append(Payment.status.in_(sorted(s.value for s in filters.statuses)))
    if filters.methods:
        conditions.append(Payment.method.in_(sorted(m.value for m in filters.methods)))
    if filters.campus_id is not None:
        conditions.append(Payment.campus_id == filters.campus_id)
    if filters.received_from is not None:
        conditions.append(Payment.received_on >= filters.received_from)
    if filters.received_to is not None:
        conditions.append(Payment.received_on <= filters.received_to)
    return conditions


async def search_payments(
    db: AsyncSession,
    context: RequestContext,
    tenant_id: uuid.UUID,
    filters: PaymentFilters,
    page: PageParams,
    sort: Sequence[SortField],
) -> tuple[list[PaymentRow], int]:
    conditions = _payment_conditions(context, tenant_id, filters)
    total = await db.scalar(
        _payment_joins(select(func.count(Payment.id)).select_from(Payment)).where(*conditions)
    )
    order = [
        PAYMENT_SORT_COLUMNS[f.name].desc() if f.descending else PAYMENT_SORT_COLUMNS[f.name]
        for f in sort
    ]
    statement = (
        _payment_joins(select(*_PAYMENT_COLUMNS).select_from(Payment))
        .where(*conditions)
        .order_by(*order, Payment.id.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    rows = (await db.execute(statement)).all()
    return [_payment_row(row) for row in rows], int(total or 0)


async def payments_of(
    db: AsyncSession, tenant_id: uuid.UUID, invoice_id: uuid.UUID
) -> list[PaymentRow]:
    rows = (
        await db.execute(
            _payment_joins(select(*_PAYMENT_COLUMNS).select_from(Payment))
            .where(Payment.tenant_id == tenant_id, Payment.invoice_id == invoice_id)
            .order_by(Payment.created_at, Payment.id)
        )
    ).all()
    return [_payment_row(row) for row in rows]


async def payment_view(
    db: AsyncSession, tenant_id: uuid.UUID, payment_id: uuid.UUID
) -> PaymentRow | None:
    row = (
        await db.execute(
            _payment_joins(select(*_PAYMENT_COLUMNS).select_from(Payment)).where(
                Payment.tenant_id == tenant_id, Payment.id == payment_id
            )
        )
    ).one_or_none()
    return _payment_row(row) if row is not None else None


# --- Summary --------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Summary:
    invoice_count: int
    invoiced_minor: int
    collected_minor: int
    outstanding_minor: int
    outstanding_count: int
    overdue_minor: int
    overdue_count: int
    pending_minor: int
    pending_count: int
    as_of: date


async def summary(
    db: AsyncSession, context: RequestContext, tenant_id: uuid.UUID, campus_id: uuid.UUID | None
) -> Summary:
    """Totals of the live fee invoices the caller may see (cancelled ones are excluded)."""
    live: list[ColumnElement[bool]] = [
        Invoice.tenant_id == tenant_id,
        Invoice.status.in_(LIVE),
        campus_visibility(Invoice.campus_id, context),
    ]
    if campus_id is not None:
        live.append(Invoice.campus_id == campus_id)
    balance = Invoice.total_minor - Invoice.paid_minor
    overdue = overdue_condition()
    totals = (
        await db.execute(
            select(
                func.count(Invoice.id),
                func.coalesce(func.sum(Invoice.total_minor), 0),
                func.coalesce(func.sum(Invoice.paid_minor), 0),
                func.coalesce(func.sum(balance), 0),
                func.count(Invoice.id).filter(balance > 0),
                func.coalesce(func.sum(case((overdue, balance), else_=0)), 0),
                func.count(Invoice.id).filter(overdue),
                ist_today(),
            ).where(*live)
        )
    ).one()
    pending = (
        await db.execute(
            select(func.count(Payment.id), func.coalesce(func.sum(Payment.amount_minor), 0))
            .select_from(Payment)
            .join(
                Invoice,
                and_(Invoice.tenant_id == Payment.tenant_id, Invoice.id == Payment.invoice_id),
            )
            .where(*live, Payment.status == PaymentStatus.PENDING.value)
        )
    ).one()
    return Summary(
        invoice_count=int(totals[0]),
        invoiced_minor=int(totals[1]),
        collected_minor=int(totals[2]),
        outstanding_minor=int(totals[3]),
        outstanding_count=int(totals[4]),
        overdue_minor=int(totals[5]),
        overdue_count=int(totals[6]),
        pending_minor=int(pending[1]),
        pending_count=int(pending[0]),
        as_of=totals[7],
    )
