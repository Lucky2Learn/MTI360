"""Finance-lite request and response models (Phase 02-5; ADR-0022, addendum R1-R3).

Amounts are integer paise (``*_minor``) in both directions; the currency is
always ``INR``. The server computes every total and balance.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.core.schemas import RequestModel, ResponseModel
from app.modules.finance.domain import (
    FEE_HEAD_MAX_LENGTH,
    MAX_AMOUNT_MINOR,
    NAME_MAX_LENGTH,
    FeeItem,
    FeeStructureStatus,
)
from app.modules.finance.repository import StructureRow

Version = Annotated[int, Field(ge=1)]
AmountMinor = Annotated[int, Field(strict=True, ge=0, le=MAX_AMOUNT_MINOR)]
"""A JSON integer of paise: strings and floats (even 1.0) are refused."""
FeeHead = Annotated[str, StringConstraints(min_length=1, max_length=FEE_HEAD_MAX_LENGTH)]
Name = Annotated[str, StringConstraints(min_length=1, max_length=NAME_MAX_LENGTH)]
LINES_ACCEPTED = 100
"""Requests carry at most this many lines; the 30-line rule answers with its own detail."""


class FeeItemIn(RequestModel):
    fee_head: FeeHead
    amount_minor: AmountMinor

    def item(self) -> FeeItem:
        return FeeItem(self.fee_head, self.amount_minor)


class FeeItemOut(ResponseModel):
    fee_head: str
    amount_minor: int


class CourseRefOut(ResponseModel):
    id: uuid.UUID
    code: str
    name: str


class FeeStructureOut(ResponseModel):
    id: uuid.UUID
    course: CourseRefOut
    name: str
    status: FeeStructureStatus
    items: list[FeeItemOut]
    total_minor: int
    currency: str
    activated_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


class CreateFeeStructureRequest(RequestModel):
    course_id: uuid.UUID
    name: Name
    items: Annotated[list[FeeItemIn], Field(max_length=LINES_ACCEPTED)]


class UpdateFeeStructureRequest(RequestModel):
    """Only the fields sent change; a structure is editable while ``DRAFT``."""

    name: Name | None = None
    items: Annotated[list[FeeItemIn], Field(max_length=LINES_ACCEPTED)] | None = None
    version: Version


class FeeStructureStatusRequest(RequestModel):
    status: Literal[FeeStructureStatus.ACTIVE, FeeStructureStatus.ARCHIVED]
    version: Version


def structure_out(row: StructureRow) -> FeeStructureOut:
    structure = row.structure
    return FeeStructureOut(
        id=structure.id,
        course=CourseRefOut(id=row.course.id, code=row.course.code, name=row.course.name),
        name=structure.name,
        status=FeeStructureStatus(structure.status),
        items=[
            FeeItemOut(fee_head=str(item["fee_head"]), amount_minor=int(item["amount_minor"]))
            for item in structure.items
        ],
        total_minor=structure.total_minor,
        currency=structure.currency,
        activated_at=structure.activated_at,
        archived_at=structure.archived_at,
        created_at=structure.created_at,
        updated_at=structure.updated_at,
        version=structure.version,
    )
