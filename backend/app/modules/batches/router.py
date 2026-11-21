"""Batch routes (Phase 02-6). Mounted by ``app.api.tenant``.

``/api/v1/batches*`` and ``/api/v1/batch-allocations*``. ``batch.read`` for
reads, ``batch.manage`` for batch changes, ``batch.allocate`` for eligible
admissions, allocation, transfer and withdrawal. A batch or allocation of
another tenant, or of a campus outside the caller's campuses, is not found.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.authz import require_permission
from app.core.db.session import DbSession
from app.core.pagination import Pagination, SortField, sort_param
from app.core.schemas import Envelope, ListEnvelope
from app.modules.batches import service
from app.modules.batches.domain import AllocationStatus, BatchStatus
from app.modules.batches.permissions import BATCH_ALLOCATE, BATCH_MANAGE, BATCH_READ
from app.modules.batches.repository import SORT_COLUMNS, AllocationFilters, BatchFilters
from app.modules.batches.schemas import (
    AllocateRequest,
    AllocationOut,
    BatchActivityOut,
    BatchOut,
    BatchStatusRequest,
    CreateBatchRequest,
    EligibleAdmissionOut,
    TransferRequest,
    UpdateBatchRequest,
    WithdrawRequest,
    allocation_out,
    batch_out,
    eligible_out,
)
from app.modules.leads.schemas import PersonRef

BatchSort = Annotated[
    tuple[SortField, ...], Depends(sort_param(allowed=set(SORT_COLUMNS), default="-start_date"))
]
Search = Annotated[str | None, Query(max_length=200)]
batch_routes = APIRouter(tags=["tenant-batches"])


def _search(q: str | None) -> str | None:
    return q.strip() if q and q.strip() else None


@batch_routes.get("/batches", dependencies=[require_permission(BATCH_READ)])
async def list_batches(
    db: DbSession,
    pagination: Pagination,
    sort: BatchSort,
    q: Search = None,
    batch_status: Annotated[list[BatchStatus] | None, Query(alias="status")] = None,
    course_id: uuid.UUID | None = None,
    campus_id: uuid.UUID | None = None,
    has_seats: bool | None = None,
) -> ListEnvelope[BatchOut]:
    filters = BatchFilters(
        search=_search(q),
        statuses=tuple(batch_status or ()),
        course_id=course_id,
        campus_id=campus_id,
        has_seats=has_seats,
    )
    rows, total = await service.list_batches(db, filters, pagination, sort)
    return ListEnvelope.build(
        [batch_out(row) for row in rows],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@batch_routes.post(
    "/batches",
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(BATCH_MANAGE)],
)
async def create_batch(body: CreateBatchRequest, db: DbSession) -> Envelope[BatchOut]:
    row = await service.create_batch(
        db,
        course_id=body.course_id,
        campus_id=body.campus_id,
        code=body.code,
        values=body.model_dump(exclude={"course_id", "campus_id", "code"}),
    )
    return Envelope(data=batch_out(row))


@batch_routes.get("/batches/{batch_id}", dependencies=[require_permission(BATCH_READ)])
async def read_batch(batch_id: uuid.UUID, db: DbSession) -> Envelope[BatchOut]:
    return Envelope(data=batch_out(await service.get_batch(db, batch_id)))


@batch_routes.patch("/batches/{batch_id}", dependencies=[require_permission(BATCH_MANAGE)])
async def update_batch(
    batch_id: uuid.UUID, body: UpdateBatchRequest, db: DbSession
) -> Envelope[BatchOut]:
    changes = body.model_dump(exclude_unset=True, exclude={"version"})
    row = await service.update_batch(db, batch_id, changes=changes, version=body.version)
    return Envelope(data=batch_out(row))


@batch_routes.post("/batches/{batch_id}/status", dependencies=[require_permission(BATCH_MANAGE)])
async def change_batch_status(
    batch_id: uuid.UUID, body: BatchStatusRequest, db: DbSession
) -> Envelope[BatchOut]:
    row = await service.change_status(
        db, batch_id, status=body.status, reason=body.reason, version=body.version
    )
    return Envelope(data=batch_out(row))


@batch_routes.get("/batches/{batch_id}/allocations", dependencies=[require_permission(BATCH_READ)])
async def batch_allocations(
    batch_id: uuid.UUID,
    db: DbSession,
    pagination: Pagination,
    q: Search = None,
    allocation_status: Annotated[list[AllocationStatus] | None, Query(alias="status")] = None,
) -> ListEnvelope[AllocationOut]:
    filters = AllocationFilters(
        batch_id=batch_id, statuses=tuple(allocation_status or ()), search=_search(q)
    )
    rows, total = await service.list_allocations(db, filters, pagination)
    return ListEnvelope.build(
        [allocation_out(row) for row in rows],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@batch_routes.get(
    "/batches/{batch_id}/eligible-admissions",
    dependencies=[require_permission(BATCH_ALLOCATE)],
)
async def eligible_admissions(
    batch_id: uuid.UUID, db: DbSession, pagination: Pagination, q: Search = None
) -> ListEnvelope[EligibleAdmissionOut]:
    _, rows, total = await service.eligible_admissions(
        db, batch_id, search=_search(q), page=pagination
    )
    return ListEnvelope.build(
        [eligible_out(row) for row in rows],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@batch_routes.post(
    "/batches/{batch_id}/allocations",
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(BATCH_ALLOCATE)],
)
async def allocate(
    batch_id: uuid.UUID, body: AllocateRequest, db: DbSession
) -> Envelope[AllocationOut]:
    row = await service.allocate(
        db, batch_id, admission_id=body.admission_id, override_reason=body.override_reason
    )
    return Envelope(data=allocation_out(row))


@batch_routes.get("/batches/{batch_id}/activity", dependencies=[require_permission(BATCH_READ)])
async def batch_activity(
    batch_id: uuid.UUID, db: DbSession, pagination: Pagination
) -> ListEnvelope[BatchActivityOut]:
    views, total = await service.batch_activity(db, batch_id, pagination)
    entries = [
        BatchActivityOut(
            id=view.item.id,
            kind=view.item.kind,
            actor=PersonRef(display_name=view.actor_name) if view.actor_name else None,
            details=view.details,
            created_at=view.item.created_at,
        )
        for view in views
    ]
    return ListEnvelope.build(
        entries, total=total, limit=pagination.limit, offset=pagination.offset
    )


@batch_routes.get("/batch-allocations", dependencies=[require_permission(BATCH_READ)])
async def list_allocations(
    db: DbSession,
    pagination: Pagination,
    student_id: uuid.UUID | None = None,
    allocation_status: Annotated[list[AllocationStatus] | None, Query(alias="status")] = None,
) -> ListEnvelope[AllocationOut]:
    """Allocations in the caller's campuses; Student 360 reads ``?student_id=``."""
    filters = AllocationFilters(student_id=student_id, statuses=tuple(allocation_status or ()))
    rows, total = await service.list_allocations(db, filters, pagination)
    return ListEnvelope.build(
        [allocation_out(row) for row in rows],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@batch_routes.post(
    "/batch-allocations/{allocation_id}/transfer",
    dependencies=[require_permission(BATCH_ALLOCATE)],
)
async def transfer(
    allocation_id: uuid.UUID, body: TransferRequest, db: DbSession
) -> Envelope[AllocationOut]:
    row = await service.transfer(
        db,
        allocation_id,
        target_batch_id=body.target_batch_id,
        reason=body.reason,
        version=body.version,
    )
    return Envelope(data=allocation_out(row))


@batch_routes.post(
    "/batch-allocations/{allocation_id}/withdraw",
    dependencies=[require_permission(BATCH_ALLOCATE)],
)
async def withdraw(
    allocation_id: uuid.UUID, body: WithdrawRequest, db: DbSession
) -> Envelope[AllocationOut]:
    row = await service.withdraw(db, allocation_id, reason=body.reason, version=body.version)
    return Envelope(data=allocation_out(row))
