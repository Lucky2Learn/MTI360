"""Finance-lite routes (Phase 02-5; ADR-0022 §11, addendum R1-R3). Mounted by ``app.api.tenant``.

16 routes, each requiring exactly one permission (the service re-checks it
and the resource's campus), in the request transaction:

* ``/fee-structures*`` — ``fee_structure.read`` / ``fee_structure.manage``;
* ``/invoices*`` — ``invoice.read``, ``invoice.issue``, ``invoice.cancel``,
  and ``payment.record`` for ``POST /invoices/{id}/payments``;
* ``/payments*`` — ``invoice.read``, ``payment.record`` (confirm, fail),
  ``payment.reverse``;
* ``/finance/summary`` — ``invoice.read``.

Another tenant's row is not found. Issue and record answer 201 for a new
record and 200 for an idempotent replay (R3). Student 360 lists a student's
fee invoices with ``GET /invoices?student_id=`` (R2).
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.core.authz import Permission, require_permission
from app.core.db.session import DbSession
from app.core.pagination import Pagination, SortField, sort_param
from app.core.ratelimit import RateLimiter
from app.core.schemas import Envelope, ListEnvelope
from app.modules.finance import invoicing, service
from app.modules.finance.domain import (
    FeeStructureStatus,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
)
from app.modules.finance.invoice_repository import (
    INVOICE_SORT_COLUMNS,
    PAYMENT_SORT_COLUMNS,
    InvoiceFilters,
    PaymentFilters,
)
from app.modules.finance.invoice_schemas import (
    CancelInvoiceRequest,
    InvoiceDetailOut,
    InvoiceOut,
    IssueInvoiceRequest,
    PaymentOut,
    PaymentReasonRequest,
    PaymentVersionRequest,
    RecordPaymentRequest,
    SummaryOut,
    invoice_detail_out,
    invoice_out,
    payment_out,
    summary_out,
)
from app.modules.finance.permissions import (
    FEE_STRUCTURE_MANAGE,
    FEE_STRUCTURE_READ,
    INVOICE_CANCEL,
    INVOICE_ISSUE,
    INVOICE_READ,
    PAYMENT_RECORD,
    PAYMENT_REVERSE,
)
from app.modules.finance.repository import STRUCTURE_SORT_COLUMNS, StructureFilters
from app.modules.finance.schemas import (
    CreateFeeStructureRequest,
    FeeStructureOut,
    FeeStructureStatusRequest,
    UpdateFeeStructureRequest,
    structure_out,
)

finance_routes = APIRouter(tags=["tenant-finance"])
StructureSort = Annotated[
    tuple[SortField, ...], Depends(sort_param(allowed=STRUCTURE_SORT_COLUMNS, default="name"))
]
InvoiceSort = Annotated[
    tuple[SortField, ...],
    Depends(sort_param(allowed=INVOICE_SORT_COLUMNS, default="-issued_at")),
]
PaymentSort = Annotated[
    tuple[SortField, ...],
    Depends(sort_param(allowed=PAYMENT_SORT_COLUMNS, default="-created_at")),
]
Search = Annotated[str | None, Query(max_length=200)]


def business_limiter(request: Request) -> RateLimiter:
    """The per-member limiter of business writes (shared with uploads; keys are per action)."""
    limiter: RateLimiter = request.app.state.upload_limiter
    return limiter


BusinessLimiter = Annotated[RateLimiter, Depends(business_limiter)]


def _search(q: str | None) -> str | None:
    return q.strip() if q and q.strip() else None


@finance_routes.get("/fee-structures", dependencies=[require_permission(FEE_STRUCTURE_READ)])
async def list_fee_structures(
    db: DbSession,
    pagination: Pagination,
    sort: StructureSort,
    q: Annotated[str | None, Query(max_length=200)] = None,
    structure_status: Annotated[list[FeeStructureStatus] | None, Query(alias="status")] = None,
    course_id: uuid.UUID | None = None,
) -> ListEnvelope[FeeStructureOut]:
    filters = StructureFilters(
        search=q.strip() if q and q.strip() else None,
        statuses=tuple(structure_status or ()),
        course_id=course_id,
    )
    rows, total = await service.list_structures(db, filters, pagination, sort)
    return ListEnvelope.build(
        [structure_out(row) for row in rows],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@finance_routes.post(
    "/fee-structures",
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(FEE_STRUCTURE_MANAGE)],
)
async def create_fee_structure(
    body: CreateFeeStructureRequest, db: DbSession
) -> Envelope[FeeStructureOut]:
    row = await service.create_structure(
        db, course_id=body.course_id, name=body.name, items=[item.item() for item in body.items]
    )
    return Envelope(data=structure_out(row))


@finance_routes.get(
    "/fee-structures/{structure_id}", dependencies=[require_permission(FEE_STRUCTURE_READ)]
)
async def read_fee_structure(structure_id: uuid.UUID, db: DbSession) -> Envelope[FeeStructureOut]:
    return Envelope(data=structure_out(await service.get_structure(db, structure_id)))


@finance_routes.patch(
    "/fee-structures/{structure_id}", dependencies=[require_permission(FEE_STRUCTURE_MANAGE)]
)
async def update_fee_structure(
    structure_id: uuid.UUID, body: UpdateFeeStructureRequest, db: DbSession
) -> Envelope[FeeStructureOut]:
    row = await service.update_structure(
        db,
        structure_id,
        name=body.name,
        items=[item.item() for item in body.items] if body.items is not None else None,
        version=body.version,
    )
    return Envelope(data=structure_out(row))


@finance_routes.post(
    "/fee-structures/{structure_id}/status",
    dependencies=[require_permission(FEE_STRUCTURE_MANAGE)],
)
async def change_fee_structure_status(
    structure_id: uuid.UUID, body: FeeStructureStatusRequest, db: DbSession
) -> Envelope[FeeStructureOut]:
    row = await service.change_structure_status(
        db, structure_id, status=FeeStructureStatus(body.status), version=body.version
    )
    return Envelope(data=structure_out(row))


# --- Fee invoices --------------------------------------------------------------------------


@finance_routes.get("/invoices", dependencies=[require_permission(INVOICE_READ)])
async def list_invoices(
    db: DbSession,
    pagination: Pagination,
    sort: InvoiceSort,
    q: Search = None,
    invoice_status: Annotated[list[InvoiceStatus] | None, Query(alias="status")] = None,
    campus_id: uuid.UUID | None = None,
    course_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    overdue: bool | None = None,
    outstanding: bool | None = None,
) -> ListEnvelope[InvoiceOut]:
    filters = InvoiceFilters(
        search=_search(q),
        statuses=tuple(invoice_status or ()),
        campus_id=campus_id,
        course_id=course_id,
        student_id=student_id,
        due_from=due_from,
        due_to=due_to,
        overdue=overdue,
        outstanding=outstanding,
    )
    rows, total = await invoicing.list_invoices(db, filters, pagination, sort)
    return ListEnvelope.build(
        [invoice_out(row) for row in rows],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@finance_routes.post(
    "/invoices",
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(INVOICE_ISSUE)],
)
async def issue_invoice(
    body: IssueInvoiceRequest, db: DbSession, response: Response
) -> Envelope[InvoiceDetailOut]:
    outcome = await invoicing.issue_invoice(
        db,
        invoicing.IssueRequest(
            admission_id=body.admission_id,
            due_date=body.due_date,
            lines=[item.item() for item in body.lines],
            adjustment_reason=body.adjustment_reason,
            idempotency_key=body.idempotency_key,
        ),
    )
    if not outcome.created:
        response.status_code = status.HTTP_200_OK
    who = await invoicing.reader(db, INVOICE_ISSUE)
    return Envelope(data=invoice_detail_out(await invoicing.invoice_detail(db, who, outcome.id)))


@finance_routes.get("/invoices/{invoice_id}", dependencies=[require_permission(INVOICE_READ)])
async def read_invoice(invoice_id: uuid.UUID, db: DbSession) -> Envelope[InvoiceDetailOut]:
    return Envelope(data=invoice_detail_out(await invoicing.get_invoice(db, invoice_id)))


@finance_routes.post(
    "/invoices/{invoice_id}/cancel", dependencies=[require_permission(INVOICE_CANCEL)]
)
async def cancel_invoice(
    invoice_id: uuid.UUID, body: CancelInvoiceRequest, db: DbSession
) -> Envelope[InvoiceDetailOut]:
    await invoicing.cancel_invoice(db, invoice_id, reason=body.reason, version=body.version)
    who = await invoicing.reader(db, INVOICE_CANCEL)
    return Envelope(data=invoice_detail_out(await invoicing.invoice_detail(db, who, invoice_id)))


@finance_routes.post(
    "/invoices/{invoice_id}/payments",
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(PAYMENT_RECORD)],
)
async def record_payment(
    invoice_id: uuid.UUID,
    body: RecordPaymentRequest,
    db: DbSession,
    response: Response,
    limiter: BusinessLimiter,
) -> Envelope[PaymentOut]:
    outcome = await invoicing.record_payment(
        db,
        invoice_id,
        invoicing.PaymentRequest(
            amount_minor=body.amount_minor,
            method=body.method,
            reference=body.reference,
            received_on=body.received_on,
            idempotency_key=body.idempotency_key,
        ),
        limiter,
    )
    if not outcome.created:
        response.status_code = status.HTTP_200_OK
    return Envelope(data=await _payment(db, PAYMENT_RECORD, outcome.id))


# --- Payments ------------------------------------------------------------------------------


async def _payment(db: DbSession, permission: Permission, payment_id: uuid.UUID) -> PaymentOut:
    who = await invoicing.reader(db, permission)
    detail = await invoicing.payment_detail(db, who, payment_id)
    return payment_out(detail.row, detail.membership_id)


@finance_routes.get("/payments", dependencies=[require_permission(INVOICE_READ)])
async def list_payments(
    db: DbSession,
    pagination: Pagination,
    sort: PaymentSort,
    q: Search = None,
    payment_status: Annotated[list[PaymentStatus] | None, Query(alias="status")] = None,
    method: Annotated[list[PaymentMethod] | None, Query()] = None,
    campus_id: uuid.UUID | None = None,
    received_from: date | None = None,
    received_to: date | None = None,
) -> ListEnvelope[PaymentOut]:
    filters = PaymentFilters(
        search=_search(q),
        statuses=tuple(payment_status or ()),
        methods=tuple(method or ()),
        campus_id=campus_id,
        received_from=received_from,
        received_to=received_to,
    )
    rows, membership_id, total = await invoicing.list_payments(db, filters, pagination, sort)
    return ListEnvelope.build(
        [payment_out(row, membership_id) for row in rows],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@finance_routes.get("/payments/{payment_id}", dependencies=[require_permission(INVOICE_READ)])
async def read_payment(payment_id: uuid.UUID, db: DbSession) -> Envelope[PaymentOut]:
    detail = await invoicing.get_payment(db, payment_id)
    return Envelope(data=payment_out(detail.row, detail.membership_id))


@finance_routes.post(
    "/payments/{payment_id}/confirm", dependencies=[require_permission(PAYMENT_RECORD)]
)
async def confirm_payment(
    payment_id: uuid.UUID, body: PaymentVersionRequest, db: DbSession
) -> Envelope[PaymentOut]:
    await invoicing.confirm_payment(db, payment_id, version=body.version)
    return Envelope(data=await _payment(db, PAYMENT_RECORD, payment_id))


@finance_routes.post(
    "/payments/{payment_id}/fail", dependencies=[require_permission(PAYMENT_RECORD)]
)
async def fail_payment(
    payment_id: uuid.UUID, body: PaymentReasonRequest, db: DbSession
) -> Envelope[PaymentOut]:
    await invoicing.fail_payment(db, payment_id, reason=body.reason, version=body.version)
    return Envelope(data=await _payment(db, PAYMENT_RECORD, payment_id))


@finance_routes.post(
    "/payments/{payment_id}/reverse", dependencies=[require_permission(PAYMENT_REVERSE)]
)
async def reverse_payment(
    payment_id: uuid.UUID, body: PaymentReasonRequest, db: DbSession
) -> Envelope[PaymentOut]:
    await invoicing.reverse_payment(db, payment_id, reason=body.reason, version=body.version)
    return Envelope(data=await _payment(db, PAYMENT_REVERSE, payment_id))


@finance_routes.get("/finance/summary", dependencies=[require_permission(INVOICE_READ)])
async def finance_summary(
    db: DbSession, campus_id: uuid.UUID | None = None
) -> Envelope[SummaryOut]:
    return Envelope(data=summary_out(await invoicing.summary(db, campus_id)))
