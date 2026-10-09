"""Student routes (Phase 02-2; ADR-0021 §2, §6, §11). Mounted by ``app.api.tenant``.

``/api/v1/students*``: the list, Student 360 (profile and admissions), its
documents (``document.read``) and its timeline. A student of another tenant,
or of a home campus outside the caller's campuses, is not found (404).
"""

import uuid
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Query

from app.core.authz import require_permission
from app.core.db.session import DbSession
from app.core.pagination import Pagination, SortField, sort_param
from app.core.schemas import Envelope, ListEnvelope
from app.modules.documents.permissions import DOCUMENT_READ
from app.modules.leads.schemas import CampusRef, PersonRef
from app.modules.students import service
from app.modules.students.domain import AdmissionStatus, StudentStatus
from app.modules.students.permissions import STUDENT_READ
from app.modules.students.repository import SORTS
from app.modules.students.schemas import (
    AdmissionOut,
    StudentDocument,
    StudentDocumentsOut,
    StudentListItem,
    StudentOut,
    TimelineEntry,
)

StudentSort = Annotated[
    tuple[SortField, ...], Depends(sort_param(allowed=SORTS, default="-created_at"))
]
student_routes = APIRouter(tags=["tenant-students"])


def _person(name: str | None) -> PersonRef | None:
    return PersonRef(display_name=name) if name else None


@student_routes.get("/students", dependencies=[require_permission(STUDENT_READ)])
async def list_students(
    db: DbSession,
    pagination: Pagination,
    sort: StudentSort,
    q: Annotated[str | None, Query(max_length=200)] = None,
    campus: uuid.UUID | None = None,
) -> ListEnvelope[StudentListItem]:
    rows, total = await service.list_students(
        db,
        search=q.strip() if q and q.strip() else None,
        campus=campus,
        page=pagination,
        sort=sort,
    )
    return ListEnvelope.build(
        [StudentListItem.model_validate(row, from_attributes=True) for row in rows],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@student_routes.get("/students/{student_id}", dependencies=[require_permission(STUDENT_READ)])
async def read_student(student_id: uuid.UUID, db: DbSession) -> Envelope[StudentOut]:
    profile = await service.get_student(db, student_id)
    detail = profile.detail
    student = detail.student
    return Envelope(
        data=StudentOut(
            id=student.id,
            student_number=student.student_number,
            status=StudentStatus(student.status),
            full_name=student.full_name,
            date_of_birth=student.date_of_birth,
            mobile=student.mobile,
            email=student.email,
            city=student.city,
            home_campus=CampusRef(
                id=student.home_campus_id, code=detail.campus_code, name=detail.campus_name
            ),
            created_by=_person(detail.creator_name),
            admissions=[
                AdmissionOut(
                    id=row.id,
                    admission_number=row.admission_number,
                    status=AdmissionStatus(row.status),
                    application_id=row.application_id,
                    application_number=row.application_number,
                    course_id=row.course_id,
                    course_code=row.course_code,
                    course_name=row.course_name,
                    course_category=row.course_category,  # type: ignore[arg-type]
                    campus=CampusRef(id=row.campus_id, code=row.campus_code, name=row.campus_name),
                    approved_at=row.approved_at,
                    approved_by=_person(row.approver_name),
                )
                for row in profile.admissions
            ],
            created_at=student.created_at,
            updated_at=student.updated_at,
            version=student.version,
        )
    )


@student_routes.get(
    "/students/{student_id}/documents", dependencies=[require_permission(DOCUMENT_READ)]
)
async def student_documents(student_id: uuid.UUID, db: DbSession) -> Envelope[StudentDocumentsOut]:
    rows = await service.student_documents(db, student_id)
    items = [StudentDocument.model_validate(row, from_attributes=True) for row in rows]
    return Envelope(data=StudentDocumentsOut(items=items))


@student_routes.get(
    "/students/{student_id}/activity", dependencies=[require_permission(STUDENT_READ)]
)
async def student_activity(
    student_id: uuid.UUID, db: DbSession, pagination: Pagination
) -> ListEnvelope[TimelineEntry]:
    views, sources, total = await service.student_activity(db, student_id, pagination)
    entries = [
        TimelineEntry(
            id=view.item.id,
            source=cast(Literal["lead", "application"], sources[view.item.id]),
            kind=view.item.kind,
            actor=_person(view.actor_name),
            details=view.details,
            body=view.item.body,
            created_at=view.item.created_at,
        )
        for view in views
    ]
    return ListEnvelope.build(
        entries, total=total, limit=pagination.limit, offset=pagination.offset
    )
