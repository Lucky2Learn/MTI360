"""Course catalogue routes (Phase 02-1; blueprint §17). Mounted by ``app.api.tenant``.

``/api/v1/courses*``: ``course.read`` for reads, ``course.manage`` for
changes, in the request transaction. Another tenant's course is not found.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import Field, StringConstraints

from app.core.authz import require_permission
from app.core.db.session import DbSession
from app.core.pagination import Pagination, SortField, sort_param
from app.core.schemas import Envelope, ListEnvelope, RequestModel, ResponseModel
from app.modules.courses import service
from app.modules.courses.domain import (
    DURATION_MAX,
    TEXT_MAX_LENGTH,
    CourseCategory,
    CourseStatus,
    DurationUnit,
)
from app.modules.courses.models import Course
from app.modules.courses.permissions import COURSE_MANAGE, COURSE_READ
from app.modules.courses.repository import SORT_COLUMNS, CourseFilters

Name = Annotated[str, StringConstraints(min_length=1, max_length=200)]
LongText = Annotated[str, StringConstraints(max_length=TEXT_MAX_LENGTH)]
Duration = Annotated[int, Field(ge=1, le=DURATION_MAX)]
Version = Annotated[int, Field(ge=1)]


class CourseOut(ResponseModel):
    id: uuid.UUID
    code: str
    name: str
    category: CourseCategory
    status: CourseStatus
    description: str | None
    duration_value: int | None
    duration_unit: DurationUnit | None
    eligibility_summary: str | None
    created_at: datetime
    updated_at: datetime
    version: int


class CreateCourseRequest(RequestModel):
    code: Annotated[str, StringConstraints(min_length=1, max_length=32)]
    name: Name
    category: CourseCategory
    description: LongText | None = None
    duration_value: Duration | None = None
    duration_unit: DurationUnit | None = None
    eligibility_summary: LongText | None = None


class UpdateCourseRequest(RequestModel):
    """Only the fields sent change; ``code`` and ``status`` cannot be set here."""

    name: Name | None = None
    category: CourseCategory | None = None
    description: LongText | None = None
    duration_value: Duration | None = None
    duration_unit: DurationUnit | None = None
    eligibility_summary: LongText | None = None
    version: Version


class CourseStatusRequest(RequestModel):
    status: Literal[CourseStatus.ACTIVE, CourseStatus.ARCHIVED]
    version: Version


def course_out(course: Course) -> CourseOut:
    return CourseOut.model_validate(course)


course_routes = APIRouter(tags=["tenant-courses"])
CourseSort = Annotated[
    tuple[SortField, ...], Depends(sort_param(allowed=SORT_COLUMNS, default="name"))
]


@course_routes.get("/courses", dependencies=[require_permission(COURSE_READ)])
async def list_courses(
    db: DbSession,
    pagination: Pagination,
    sort: CourseSort,
    q: Annotated[str | None, Query(max_length=200)] = None,
    course_status: Annotated[list[CourseStatus] | None, Query(alias="status")] = None,
    category: CourseCategory | None = None,
) -> ListEnvelope[CourseOut]:
    filters = CourseFilters(
        search=q.strip() if q and q.strip() else None,
        statuses=tuple(course_status or ()),
        category=category,
    )
    courses, total = await service.list_courses(db, filters, pagination, sort)
    return ListEnvelope.build(
        [course_out(course) for course in courses],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@course_routes.post(
    "/courses",
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(COURSE_MANAGE)],
)
async def create_course(body: CreateCourseRequest, db: DbSession) -> Envelope[CourseOut]:
    values = body.model_dump(exclude={"code"})
    course = await service.create_course(db, code=body.code, values=values)
    return Envelope(data=course_out(course))


@course_routes.get("/courses/{course_id}", dependencies=[require_permission(COURSE_READ)])
async def read_course(course_id: uuid.UUID, db: DbSession) -> Envelope[CourseOut]:
    return Envelope(data=course_out(await service.get_course(db, course_id)))


@course_routes.patch("/courses/{course_id}", dependencies=[require_permission(COURSE_MANAGE)])
async def update_course(
    course_id: uuid.UUID, body: UpdateCourseRequest, db: DbSession
) -> Envelope[CourseOut]:
    changes = body.model_dump(exclude_unset=True, exclude={"version"})
    course = await service.update_course(db, course_id, changes=changes, version=body.version)
    return Envelope(data=course_out(course))


@course_routes.post("/courses/{course_id}/status", dependencies=[require_permission(COURSE_MANAGE)])
async def change_course_status(
    course_id: uuid.UUID, body: CourseStatusRequest, db: DbSession
) -> Envelope[CourseOut]:
    course = await service.change_status(
        db, course_id, status=CourseStatus(body.status), version=body.version
    )
    return Envelope(data=course_out(course))
