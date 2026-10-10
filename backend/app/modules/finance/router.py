"""Finance-lite routes (Phase 02-5; ADR-0022 §11, addendum R1-R3). Mounted by ``app.api.tenant``.

``/api/v1/fee-structures*``: ``fee_structure.read`` for reads,
``fee_structure.manage`` for changes, in the request transaction. Another
tenant's row is not found. Every route requires exactly one permission; the
service re-checks it and the resource's campus.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.authz import require_permission
from app.core.db.session import DbSession
from app.core.pagination import Pagination, SortField, sort_param
from app.core.schemas import Envelope, ListEnvelope
from app.modules.finance import service
from app.modules.finance.domain import FeeStructureStatus
from app.modules.finance.permissions import FEE_STRUCTURE_MANAGE, FEE_STRUCTURE_READ
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
