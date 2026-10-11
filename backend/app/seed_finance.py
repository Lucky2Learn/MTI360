"""Development seed: fee structures, fee invoices, payments and receipts (Phase 02-5; ADR-0022).

Part of ``app.seed``: development only, fictitious people and references.
Rows go through the same tables, keys and CHECKs as the API and carry what
the API would have written for the same history:

* numbers from the shared financial-year sequences (``next_number``), in the
  institute's transaction, in issue and confirmation order (gap-free);
* fee invoice lines built from the fee structure by the domain rules (an
  adjustment needs a reason; a structure line left out is kept at zero);
* ``paid_minor`` equal to the sum of ``CONFIRMED`` payments and the status that
  follows from it; one receipt for every payment that was ever confirmed;
* the finance activity timeline, request hashes and row versions of the API.

Before anything is written, the file is checked against the API's rules: each
actor holds the permission for the fee invoice's campus (``fee_structure.manage``
needs all campuses); one live fee invoice per admission, a replacement only
after the earlier one is cancelled; a fee invoice is issued from its course's
``ACTIVE`` fee structure (a cancelled one may name a structure archived since);
no overpayment, counting pending cheques and demand drafts; a reversal is never
done by the recorder; a cancelled fee invoice has no ``PENDING`` or
``CONFIRMED`` payment.

Dates are relative to the database's IST date when the seed runs
(``due_in_days``, ``received_days_ago``), so an overdue fee invoice stays
overdue; numbers, amounts and statuses are the same on every run.
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Final, cast

from sqlalchemy import Table, func, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.activity import record_activity
from app.core.sequences import SequenceName, next_number
from app.modules.courses.domain import CourseStatus
from app.modules.finance.domain import (
    CLEARANCE_METHODS,
    CURRENCY,
    LINES_MAX,
    MAX_AMOUNT_MINOR,
    NAME_MAX_LENGTH,
    REASON_MAX_LENGTH,
    REFERENCE_MAX_LENGTH,
    ActivityKind,
    FeeItem,
    FeeStructureStatus,
    InvoiceStatus,
    IssuedLine,
    PaymentMethod,
    PaymentStatus,
    clean_label,
    initial_payment_status,
    invoice_lines,
    invoice_status,
    is_adjusted,
    items_problems,
    lines_total,
    request_hash,
    valid_amount,
)
from app.modules.finance.invoice_repository import today
from app.modules.finance.models import (
    FeeStructure,
    FinanceActivity,
    Invoice,
    InvoiceLine,
    Payment,
    Receipt,
)
from app.modules.finance.permissions import (
    FEE_STRUCTURE_MANAGE,
    INVOICE_CANCEL,
    INVOICE_ISSUE,
    PAYMENT_RECORD,
    PAYMENT_REVERSE,
)
from app.modules.finance.service import stored_items

STRUCTURES = cast(Table, FeeStructure.__table__)
INVOICES = cast(Table, Invoice.__table__)
LINES = cast(Table, InvoiceLine.__table__)
PAYMENTS = cast(Table, Payment.__table__)
RECEIPTS = cast(Table, Receipt.__table__)
ACTIVITIES = cast(Table, FinanceActivity.__table__)

STRUCTURE_VERSIONS: Final = {
    FeeStructureStatus.DRAFT: 1,
    FeeStructureStatus.ACTIVE: 2,  # created, activated
    FeeStructureStatus.ARCHIVED: 3,  # created, activated, archived
}
EVER_CONFIRMED: Final = frozenset({PaymentStatus.CONFIRMED, PaymentStatus.REVERSED})
CLOSED: Final = frozenset({PaymentStatus.FAILED, PaymentStatus.REVERSED})


class FinanceSeedError(ValueError):
    """An invalid finance section of the seed file; the message is safe to print."""


@dataclass(frozen=True, slots=True)
class Actor:
    """What a seed member may do: their role's permissions and their campus scope."""

    permissions: frozenset[str]
    campuses: frozenset[str] | None
    """Campus codes; ``None`` for all campuses."""

    def may(self, permission: str, campus: str | None = None) -> bool:
        """``campus`` ``None``: a tenant-wide permission, which needs all campuses."""
        if permission not in self.permissions:
            return False
        if self.campuses is None:
            return True
        return campus is not None and campus in self.campuses


@dataclass(frozen=True, slots=True)
class SeedFeeStructure:
    key: str
    course: str
    name: str
    status: FeeStructureStatus
    items: tuple[FeeItem, ...]
    created_by: str


@dataclass(frozen=True, slots=True)
class SeedPayment:
    amount_minor: int
    method: PaymentMethod
    reference: str | None
    received_days_ago: int
    recorded_by: str
    status: PaymentStatus
    reason: str | None
    confirmed_by: str | None
    """Who confirmed it (on record for cash, UPI and bank transfer); ``None`` if never."""
    closed_by: str | None
    """Who failed or reversed it."""

    @property
    def initial(self) -> PaymentStatus:
        return initial_payment_status(self.method)


@dataclass(frozen=True, slots=True)
class SeedInvoice:
    key: str
    application: str
    structure: str
    requested: tuple[FeeItem, ...]
    """The lines as the issuer sent them (the structure's when not adjusted)."""
    lines: tuple[IssuedLine, ...]
    adjustment_reason: str | None
    due_in_days: int
    issued_by: str
    cancel_reason: str | None
    cancelled_by: str | None
    payments: tuple[SeedPayment, ...]

    @property
    def total_minor(self) -> int:
        return lines_total(self.lines)

    @property
    def paid_minor(self) -> int:
        return sum(p.amount_minor for p in self.payments if p.status is PaymentStatus.CONFIRMED)

    @property
    def status(self) -> InvoiceStatus:
        if self.cancel_reason is not None:
            return InvoiceStatus.CANCELLED
        return invoice_status(self.total_minor, self.paid_minor)


@dataclass(frozen=True, slots=True)
class SeedFinance:
    fee_structures: tuple[SeedFeeStructure, ...] = ()
    invoices: tuple[SeedInvoice, ...] = ()


@dataclass(frozen=True, slots=True)
class SeededAdmission:
    """An admission the applications seed created, by its application's key."""

    admission_id: uuid.UUID
    student_id: uuid.UUID
    student_number: str
    course_id: uuid.UUID
    campus_id: uuid.UUID


# --- Parsing --------------------------------------------------------------------------------


def _text(item: Mapping[str, Any], key: str, at: str, max_length: int) -> str | None:
    value = item.get(key)
    if value is None:
        return None
    clean = clean_label(value, max_length) if isinstance(value, str) else None
    if clean is None:
        raise FinanceSeedError(f"{at}.{key}: text of 1 to {max_length} characters")
    return clean


def _int(item: Mapping[str, Any], key: str, at: str, *, default: int | None = None) -> int:
    value = item.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise FinanceSeedError(f"{at}.{key}: an integer is required")
    return value


def _items(raw: Any, at: str) -> tuple[FeeItem, ...]:
    if not isinstance(raw, list):
        raise FinanceSeedError(f"{at}: a list of fee heads is required")
    items: list[FeeItem] = []
    for index, item in enumerate(raw):
        where = f"{at}[{index}]"
        head = _text(item, "fee_head", where, 100)
        if head is None:
            raise FinanceSeedError(f"{where}.fee_head: required")
        items.append(FeeItem(head, _int(item, "amount_minor", where)))
    problems = items_problems(items)
    if problems:
        raise FinanceSeedError(f"{at}: {', '.join(problems)}")
    return tuple(items)


def _actor(actors: Mapping[str, Actor], email: str | None, at: str) -> Actor:
    if email is None or email not in actors:
        raise FinanceSeedError(f"{at}: a seed member is required")
    return actors[email]


def _require(
    actors: Mapping[str, Actor], email: str | None, permission: str, campus: str | None, at: str
) -> str:
    if not _actor(actors, email, at).may(permission, campus):
        where = "all campuses" if campus is None else f"campus {campus}"
        raise FinanceSeedError(f"{at}: {email} does not hold {permission} for {where}")
    return cast(str, email)


def parse_structures(
    raw: Sequence[Mapping[str, Any]],
    where: str,
    *,
    courses: Mapping[str, CourseStatus],
    actors: Mapping[str, Actor],
) -> tuple[SeedFeeStructure, ...]:
    structures: list[SeedFeeStructure] = []
    active: set[str] = set()
    for index, item in enumerate(raw):
        at = f"{where}.fee_structures[{index}]"
        key = _text(item, "key", at, 50)
        if key is None or key in {s.key for s in structures}:
            raise FinanceSeedError(f"{at}.key: a unique key is required")
        course = _text(item, "course", at, 50) or ""
        if course not in courses or courses[course] is CourseStatus.ARCHIVED:
            raise FinanceSeedError(f"{at}.course: a seed course that is not archived")
        name = _text(item, "name", at, NAME_MAX_LENGTH)
        if name is None:
            raise FinanceSeedError(f"{at}.name: required")
        try:
            status = FeeStructureStatus(item.get("status", "DRAFT"))
        except ValueError:
            raise FinanceSeedError(f"{at}.status: unknown status") from None
        if status is FeeStructureStatus.ACTIVE:
            if course in active:
                raise FinanceSeedError(f"{at}: one ACTIVE fee structure per course")
            active.add(course)
        created_by = _require(
            actors, item.get("created_by"), FEE_STRUCTURE_MANAGE.code, None, f"{at}.created_by"
        )
        structures.append(
            SeedFeeStructure(
                key, course, name, status, _items(item.get("items"), f"{at}.items"), created_by
            )
        )
    return tuple(structures)


def _payment(
    item: Mapping[str, Any], at: str, campus: str, actors: Mapping[str, Actor]
) -> SeedPayment:
    amount = _int(item, "amount_minor", at)
    if not valid_amount(amount, positive=True):
        raise FinanceSeedError(f"{at}.amount_minor: more than 0 and at most the maximum")
    try:
        method = PaymentMethod(str(item.get("method")))
        status = PaymentStatus(str(item.get("status")))
    except ValueError:
        raise FinanceSeedError(f"{at}: unknown method or status") from None
    reference = _text(item, "reference", at, REFERENCE_MAX_LENGTH)
    if reference is None and method is not PaymentMethod.CASH:
        raise FinanceSeedError(f"{at}.reference: required except for cash")
    received_days_ago = _int(item, "received_days_ago", at)
    if received_days_ago < 0:
        raise FinanceSeedError(f"{at}.received_days_ago: the money was received, not due")
    clearance = method in CLEARANCE_METHODS
    if not clearance and status not in EVER_CONFIRMED:
        raise FinanceSeedError(f"{at}.status: cash, UPI and bank transfer are confirmed on record")
    reason = _text(item, "reason", at, REASON_MAX_LENGTH)
    if (status in CLOSED) != (reason is not None):
        raise FinanceSeedError(f"{at}.reason: required for failed and reversed payments only")
    recorded_by = _require(actors, item.get("recorded_by"), PAYMENT_RECORD.code, campus, at)
    confirmed_by: str | None = None
    if status in EVER_CONFIRMED:
        if clearance:
            confirmed_by = _require(
                actors,
                item.get("confirmed_by", recorded_by),
                PAYMENT_RECORD.code,
                campus,
                f"{at}.confirmed_by",
            )
        elif item.get("confirmed_by", recorded_by) != recorded_by:
            raise FinanceSeedError(f"{at}.confirmed_by: confirmed on record by its recorder")
        else:
            confirmed_by = recorded_by
    elif "confirmed_by" in item:
        raise FinanceSeedError(f"{at}.confirmed_by: for confirmed or reversed payments only")
    closed_by: str | None = None
    if status is PaymentStatus.FAILED:
        closed_by = _require(
            actors, item.get("closed_by"), PAYMENT_RECORD.code, campus, f"{at}.closed_by"
        )
    elif status is PaymentStatus.REVERSED:
        closed_by = _require(
            actors, item.get("closed_by"), PAYMENT_REVERSE.code, campus, f"{at}.closed_by"
        )
        if closed_by == recorded_by:
            raise FinanceSeedError(f"{at}.closed_by: never reversed by its recorder")
    elif "closed_by" in item:
        raise FinanceSeedError(f"{at}.closed_by: for failed or reversed payments only")
    return SeedPayment(
        amount_minor=amount,
        method=method,
        reference=reference,
        received_days_ago=received_days_ago,
        recorded_by=recorded_by,
        status=status,
        reason=reason,
        confirmed_by=confirmed_by,
        closed_by=closed_by,
    )


def _check_balance(total: int, payments: Sequence[SeedPayment], at: str) -> None:
    """Replay the payments in order, as the API would accept them (pending counts)."""
    paid = pending = 0
    for index, payment in enumerate(payments):
        if payment.amount_minor > total - paid - pending:
            raise FinanceSeedError(f"{at}.payments[{index}]: more than the balance to collect")
        if payment.status is PaymentStatus.PENDING:
            pending += payment.amount_minor
        elif payment.status is PaymentStatus.CONFIRMED:
            paid += payment.amount_minor
        # FAILED and REVERSED end where they started.


def parse_invoices(
    raw: Sequence[Mapping[str, Any]],
    where: str,
    *,
    structures: Sequence[SeedFeeStructure],
    admitted: Mapping[str, tuple[str, str]],
    actors: Mapping[str, Actor],
) -> tuple[SeedInvoice, ...]:
    """Validate an institute's ``invoices``; ``admitted``: application key → (course, campus)."""
    by_key = {s.key: s for s in structures}
    invoices: list[SeedInvoice] = []
    live: set[str] = set()
    for index, item in enumerate(raw):
        at = f"{where}.invoices[{index}]"
        key = _text(item, "key", at, 50)
        if key is None or key in {i.key for i in invoices}:
            raise FinanceSeedError(f"{at}.key: a unique key is required")
        application = _text(item, "application", at, 50) or ""
        if application not in admitted:
            raise FinanceSeedError(f"{at}.application: an ADMITTED seed application")
        if application in live:
            raise FinanceSeedError(f"{at}: the admission's fee invoice must be cancelled first")
        course, campus = admitted[application]
        structure = by_key.get(_text(item, "structure", at, 50) or "")
        if structure is None or structure.course != course:
            raise FinanceSeedError(f"{at}.structure: a fee structure of the admission's course")
        cancelled = item.get("cancelled")
        if structure.status is FeeStructureStatus.DRAFT or (
            structure.status is FeeStructureStatus.ARCHIVED and cancelled is None
        ):
            raise FinanceSeedError(f"{at}.structure: issued from the course's ACTIVE structure")
        issued_by = _require(actors, item.get("issued_by"), INVOICE_ISSUE.code, campus, at)
        requested = _items(item["lines"], f"{at}.lines") if "lines" in item else structure.items
        lines = tuple(invoice_lines(structure.items, requested))
        total = lines_total(lines)
        if len(lines) > LINES_MAX or not 0 < total <= MAX_AMOUNT_MINOR:
            raise FinanceSeedError(f"{at}.lines: at most 30 lines and a total above zero")
        reason = _text(item, "adjustment_reason", at, REASON_MAX_LENGTH)
        if is_adjusted(lines) != (reason is not None):
            raise FinanceSeedError(f"{at}.adjustment_reason: required for adjusted lines only")
        payments = tuple(
            _payment(payment, f"{at}.payments[{n}]", campus, actors)
            for n, payment in enumerate(item.get("payments", ()))
        )
        _check_balance(total, payments, at)
        cancel_reason = cancelled_by = None
        if cancelled is not None:
            cancel_reason = _text(cancelled, "reason", f"{at}.cancelled", REASON_MAX_LENGTH)
            if cancel_reason is None:
                raise FinanceSeedError(f"{at}.cancelled.reason: required")
            cancelled_by = _require(
                actors, cancelled.get("by"), INVOICE_CANCEL.code, campus, f"{at}.cancelled"
            )
            if any(payment.status not in CLOSED for payment in payments):
                raise FinanceSeedError(f"{at}.cancelled: fail or reverse every payment first")
        else:
            live.add(application)
        invoices.append(
            SeedInvoice(
                key=key,
                application=application,
                structure=structure.key,
                requested=requested,
                lines=lines,
                adjustment_reason=reason,
                due_in_days=_int(item, "due_in_days", at),
                issued_by=issued_by,
                cancel_reason=cancel_reason,
                cancelled_by=cancelled_by,
                payments=payments,
            )
        )
    return tuple(invoices)


def parse_finance(
    raw: Mapping[str, Any],
    where: str,
    *,
    courses: Mapping[str, CourseStatus],
    admitted: Mapping[str, tuple[str, str]],
    actors: Mapping[str, Actor],
) -> SeedFinance:
    """Validate an institute's ``fee_structures`` and ``invoices`` (the API's rules)."""
    structures = parse_structures(
        raw.get("fee_structures", ()), where, courses=courses, actors=actors
    )
    invoices = parse_invoices(
        raw.get("invoices", ()), where, structures=structures, admitted=admitted, actors=actors
    )
    return SeedFinance(structures, invoices)


# --- Writing --------------------------------------------------------------------------------


async def _activity(
    db: AsyncSession, invoice_id: uuid.UUID, kind: ActivityKind, actor: uuid.UUID, **details: Any
) -> None:
    await record_activity(
        db,
        ACTIVITIES,
        subject_column="invoice_id",
        subject_id=invoice_id,
        kind=kind.value,
        actor_membership_id=actor,
        details=details,
    )


async def _seed_payment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    invoice_id: uuid.UUID,
    invoice_number: str,
    admission: SeededAdmission,
    payment: SeedPayment,
    received_on: date,
    memberships: Mapping[str, uuid.UUID],
) -> None:
    """Record, then confirm, fail or reverse ``payment`` as the API would have."""
    payment_id = uuid.uuid7()
    recorder = memberships[payment.recorded_by]
    confirmer = memberships[payment.confirmed_by] if payment.confirmed_by else None
    closer = memberships[payment.closed_by] if payment.closed_by else None
    clearance = payment.method in CLEARANCE_METHODS
    changes = int(clearance and payment.status is not PaymentStatus.PENDING) + int(
        payment.status is PaymentStatus.REVERSED
    )
    await db.execute(
        insert(PAYMENTS).values(
            id=payment_id,
            tenant_id=tenant_id,
            invoice_id=invoice_id,
            student_id=admission.student_id,
            campus_id=admission.campus_id,
            amount_minor=payment.amount_minor,
            currency=CURRENCY,
            method=payment.method.value,
            reference=payment.reference,
            received_on=received_on,
            status=payment.status.value,
            status_reason=payment.reason,
            recorded_by_membership_id=recorder,
            confirmed_at=func.now() if confirmer else None,
            confirmed_by_membership_id=confirmer,
            closed_at=func.now() if closer else None,
            closed_by_membership_id=closer,
            idempotency_key=uuid.uuid4(),
            request_hash=request_hash(
                "record_payment",
                {
                    "invoice_id": str(invoice_id),
                    "amount_minor": payment.amount_minor,
                    "method": payment.method.value,
                    "reference": payment.reference,
                    "received_on": received_on.isoformat(),
                },
            ),
            version=1 + changes,
        )
    )
    receipt_number: str | None = None
    if payment.status in EVER_CONFIRMED:
        receipt_number = await next_number(db, SequenceName.RECEIPT)
        await db.execute(
            insert(RECEIPTS).values(
                id=uuid.uuid7(),
                tenant_id=tenant_id,
                number=receipt_number,
                payment_id=payment_id,
                invoice_number=invoice_number,
                student_number=admission.student_number,
                amount_minor=payment.amount_minor,
                currency=CURRENCY,
                method=payment.method.value,
            )
        )
    money: dict[str, Any] = {
        "payment_id": str(payment_id),
        "amount_minor": payment.amount_minor,
        "method": payment.method.value,
    }
    await _activity(
        db,
        invoice_id,
        ActivityKind.PAYMENT_RECORDED,
        recorder,
        **money,
        status=payment.initial.value,
        receipt_number=None if clearance else receipt_number,
    )
    if clearance and confirmer is not None:
        await _activity(
            db,
            invoice_id,
            ActivityKind.PAYMENT_CONFIRMED,
            confirmer,
            **money,
            receipt_number=receipt_number,
        )
    if payment.status is PaymentStatus.FAILED and closer is not None:
        await _activity(
            db, invoice_id, ActivityKind.PAYMENT_FAILED, closer, **money, reason=payment.reason
        )
    if payment.status is PaymentStatus.REVERSED and closer is not None:
        await _activity(
            db,
            invoice_id,
            ActivityKind.PAYMENT_REVERSED,
            closer,
            **money,
            receipt_number=receipt_number,
            reason=payment.reason,
        )


async def _seed_invoice(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    invoice: SeedInvoice,
    structure: SeedFeeStructure,
    structure_id: uuid.UUID,
    admission: SeededAdmission,
    on: date,
    memberships: Mapping[str, uuid.UUID],
) -> None:
    invoice_id = uuid.uuid7()
    number = await next_number(db, SequenceName.INVOICE)
    issuer = memberships[invoice.issued_by]
    canceller = memberships[invoice.cancelled_by] if invoice.cancelled_by else None
    due_date = on + timedelta(days=invoice.due_in_days)
    adjusted = is_adjusted(invoice.lines)
    structure_total = sum(item.amount_minor for item in structure.items)
    # Each confirmation and reversal changes the balance; a cancellation, the status.
    changes = sum(
        int(p.status in EVER_CONFIRMED) + int(p.status is PaymentStatus.REVERSED)
        for p in invoice.payments
    ) + int(canceller is not None)
    await db.execute(
        insert(INVOICES).values(
            id=invoice_id,
            tenant_id=tenant_id,
            number=number,
            admission_id=admission.admission_id,
            student_id=admission.student_id,
            course_id=admission.course_id,
            campus_id=admission.campus_id,
            fee_structure_id=structure_id,
            # Issued while the structure was ACTIVE (a cancelled one may be archived since).
            fee_structure_version=STRUCTURE_VERSIONS[FeeStructureStatus.ACTIVE],
            structure_total_minor=structure_total,
            total_minor=invoice.total_minor,
            paid_minor=invoice.paid_minor,
            currency=CURRENCY,
            due_date=due_date,
            adjusted=adjusted,
            adjustment_reason=invoice.adjustment_reason,
            status=invoice.status.value,
            status_reason=invoice.cancel_reason,
            issued_by_membership_id=issuer,
            cancelled_at=func.now() if canceller else None,
            cancelled_by_membership_id=canceller,
            idempotency_key=uuid.uuid4(),
            request_hash=request_hash(
                "issue_invoice",
                {
                    "admission_id": str(admission.admission_id),
                    "due_date": due_date.isoformat(),
                    "lines": [[item.fee_head, item.amount_minor] for item in invoice.requested],
                    "adjustment_reason": invoice.adjustment_reason,
                },
            ),
            version=1 + changes,
        )
    )
    for line in invoice.lines:
        await db.execute(
            insert(LINES).values(
                id=uuid.uuid7(),
                tenant_id=tenant_id,
                invoice_id=invoice_id,
                position=line.position,
                fee_head=line.fee_head,
                amount_minor=line.amount_minor,
                structure_amount_minor=line.structure_amount_minor,
            )
        )
    await _activity(
        db,
        invoice_id,
        ActivityKind.ISSUED,
        issuer,
        number=number,
        total_minor=invoice.total_minor,
        structure_total_minor=structure_total,
        adjusted=adjusted,
        line_count=len(invoice.lines),
        adjusted_fee_heads=[line.fee_head for line in invoice.lines if line.adjusted],
    )
    for payment in invoice.payments:
        received_on = on - timedelta(days=payment.received_days_ago)
        await _seed_payment(
            db, tenant_id, invoice_id, number, admission, payment, received_on, memberships
        )
    if canceller is not None:
        await _activity(
            db, invoice_id, ActivityKind.CANCELLED, canceller, reason=invoice.cancel_reason
        )


async def seed_finance(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    finance: SeedFinance,
    course_ids: Mapping[str, uuid.UUID],
    admissions: Mapping[str, SeededAdmission],
    memberships: Mapping[str, uuid.UUID],
) -> None:
    """Insert one institute's fee structures, fee invoices, payments and receipts."""
    structure_ids: dict[str, uuid.UUID] = {}
    for structure in finance.fee_structures:
        structure_ids[structure.key] = uuid.uuid7()
        draft = structure.status is FeeStructureStatus.DRAFT
        archived = structure.status is FeeStructureStatus.ARCHIVED
        await db.execute(
            insert(STRUCTURES).values(
                id=structure_ids[structure.key],
                tenant_id=tenant_id,
                course_id=course_ids[structure.course],
                name=structure.name,
                status=structure.status.value,
                items=stored_items(structure.items),
                total_minor=sum(item.amount_minor for item in structure.items),
                currency=CURRENCY,
                created_by_membership_id=memberships[structure.created_by],
                activated_at=None if draft else func.now(),
                archived_at=func.now() if archived else None,
                version=STRUCTURE_VERSIONS[structure.status],
            )
        )
    if not finance.invoices:
        return
    on = await today(db)  # the IST date that decides overdue
    structures = {structure.key: structure for structure in finance.fee_structures}
    for invoice in finance.invoices:
        await _seed_invoice(
            db,
            tenant_id,
            invoice,
            structures[invoice.structure],
            structure_ids[invoice.structure],
            admissions[invoice.application],
            on,
            memberships,
        )
