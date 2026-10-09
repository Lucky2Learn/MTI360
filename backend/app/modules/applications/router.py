"""Application routes (Phase 02-2; ADR-0021 §3-§6). Mounted by ``app.api.tenant``.

``/api/v1/applications*``, one permission per route (``application.read`` /
``.create`` / ``.update`` / ``.review``, ``admission.approve``), in the
request transaction. An application of another tenant, or of a campus outside
the caller's campuses, is not found (404). Search terms are names and
application numbers only; contact details never appear in URLs.
"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.core.authz import campus_visible, require_permission
from app.core.db.session import DbSession
from app.core.errors import ErrorDetail, ValidationFailedError
from app.core.pagination import Pagination, SortField, sort_param
from app.core.schemas import Envelope, ListEnvelope
from app.modules.applications import repository as repo
from app.modules.applications import service
from app.modules.applications.domain import (
    DETAIL_FIELDS,
    EDITABLE,
    REASON_REQUIRED,
    REVIEW_TRANSITIONS,
    ActivityKind,
    ApplicationStatus,
    missing_for_submit,
)
from app.modules.applications.permissions import (
    APPLICATION_CREATE,
    APPLICATION_READ,
    APPLICATION_REVIEW,
    APPLICATION_UPDATE,
)
from app.modules.applications.schemas import (
    AdmissionLink,
    AdmitRequest,
    ApplicationActivityOut,
    ApplicationListItem,
    ApplicationOut,
    CourseRef,
    CreateApplicationRequest,
    DocumentSummary,
    LeadLink,
    ReviewOption,
    ReviewRequest,
    StudentCandidate,
    StudentCandidatesOut,
    SubmitRequest,
    UpdateApplicationRequest,
)
from app.modules.courses.domain import CourseStatus
from app.modules.leads import follow_ups
from app.modules.leads.domain import LeadStatus
from app.modules.leads.permissions import LEAD_READ
from app.modules.leads.schemas import CampusRef, PersonRef
from app.modules.leads.service import Caller, caller
from app.modules.students import repository as students_repo
from app.modules.students.permissions import ADMISSION_APPROVE, STUDENT_READ

APPLICATION_SORT = ("created_at", "updated_at", "submitted_at", "full_name", "number")
ApplicationSort = Annotated[
    tuple[SortField, ...], Depends(sort_param(allowed=APPLICATION_SORT, default="-created_at"))
]
application_routes = APIRouter(tags=["tenant-applications"])


def _person(name: str | None) -> PersonRef | None:
    return PersonRef(display_name=name) if name else None


def application_out(row: repo.ApplicationDetailRow, who: Caller) -> ApplicationOut:
    app = row.application
    current = ApplicationStatus(app.status)
    context = who.context
    lead_visible = (
        app.lead_id is not None
        and row.lead_name is not None
        and LEAD_READ.code in context.permissions
        and campus_visible(row.lead_campus_id, context)
    )
    return ApplicationOut(
        id=app.id,
        number=app.number,
        status=current,
        status_reason=app.status_reason,
        status_changed_at=app.status_changed_at,
        lead=(
            LeadLink(
                id=app.lead_id, full_name=row.lead_name or "", status=LeadStatus(row.lead_status)
            )
            if lead_visible and app.lead_id and row.lead_status
            else None
        ),
        course=CourseRef(
            id=app.course_id,
            code=row.course_code,
            name=row.course_name,
            status=CourseStatus(row.course_status),
        ),
        campus=CampusRef(id=app.campus_id, code=row.campus_code, name=row.campus_name),
        owner=_person(row.owner_name),
        created_by=_person(row.creator_name),
        submitted_at=app.submitted_at,
        reviewed_at=app.reviewed_at,
        reviewed_by=_person(row.reviewer_name),
        declared_at=app.declared_at,
        declared_by=_person(row.declarer_name),
        full_name=app.full_name,
        date_of_birth=app.date_of_birth,
        mobile=app.mobile,
        email=app.email,
        address=app.address,
        city=app.city,
        state=app.state,
        postal_code=app.postal_code,
        highest_qualification=app.highest_qualification,
        education_details=app.education_details,
        indos_number=app.indos_number,
        cdc_number=app.cdc_number,
        eligibility_notes=app.eligibility_notes,
        documents=DocumentSummary(
            total=row.documents_total,
            verified=row.documents_verified,
            pending=row.documents_pending,
        ),
        editable=current in EDITABLE,
        missing_for_submit=(
            missing_for_submit(
                {field: getattr(app, field) for field in DETAIL_FIELDS},
                declared=app.declared_at is not None,
            )
            if current in EDITABLE
            else []
        ),
        review_options=[
            ReviewOption(to_status=target, requires_reason=target in REASON_REQUIRED)
            for target in ApplicationStatus
            if REVIEW_TRANSITIONS.allows(current, target)
        ],
        admission=(
            AdmissionLink(
                id=row.admission_id,
                admission_number=row.admission_number or "",
                student_id=row.student_id,
                student_number=row.student_number or "",
                student_visible=STUDENT_READ.code in context.permissions
                and campus_visible(row.student_campus_id, context),
            )
            if row.admission_id and row.student_id
            else None
        ),
        created_at=app.created_at,
        updated_at=app.updated_at,
        version=app.version,
    )


def activity_out(view: follow_ups.ActivityView) -> ApplicationActivityOut:
    item = view.item
    return ApplicationActivityOut(
        id=item.id,
        kind=ActivityKind(item.kind),
        actor=_person(view.actor_name),
        details=view.details,
        created_at=item.created_at,
    )


def _matched_on(row: students_repo.CandidateRow) -> list[Literal["mobile", "email"]]:
    matched: list[Literal["mobile", "email"]] = []
    if row.mobile_match:
        matched.append("mobile")
    if row.email_match:
        matched.append("email")
    return matched


@application_routes.get("/applications", dependencies=[require_permission(APPLICATION_READ)])
async def list_applications(
    db: DbSession,
    pagination: Pagination,
    sort: ApplicationSort,
    q: Annotated[str | None, Query(max_length=200)] = None,
    application_status: Annotated[list[ApplicationStatus] | None, Query(alias="status")] = None,
    campus: uuid.UUID | None = None,
    course: uuid.UUID | None = None,
    lead: uuid.UUID | None = None,
    owner: Literal["me"] | None = None,
) -> ListEnvelope[ApplicationListItem]:
    filters = repo.ApplicationFilters(
        search=q.strip() if q and q.strip() else None,
        statuses=tuple(application_status or ()),
        campus=campus,
        course=course,
        lead=lead,
    )
    rows, total = await service.list_applications(db, filters, pagination, sort, mine=owner == "me")
    return ListEnvelope.build(
        [ApplicationListItem.model_validate(row, from_attributes=True) for row in rows],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@application_routes.post(
    "/applications",
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(APPLICATION_CREATE)],
)
async def create_application(
    body: CreateApplicationRequest, db: DbSession
) -> Envelope[ApplicationOut]:
    values = body.model_dump(exclude_unset=True, exclude={"lead_id", "course_id", "campus_id"})
    row = await service.create_application(
        db, lead_id=body.lead_id, course_id=body.course_id, campus_id=body.campus_id, values=values
    )
    who = await caller(db, APPLICATION_READ)
    return Envelope(data=application_out(row, who))


@application_routes.get(
    "/applications/{application_id}", dependencies=[require_permission(APPLICATION_READ)]
)
async def read_application(application_id: uuid.UUID, db: DbSession) -> Envelope[ApplicationOut]:
    row, who = await service.get_application(db, application_id)
    return Envelope(data=application_out(row, who))


@application_routes.patch(
    "/applications/{application_id}", dependencies=[require_permission(APPLICATION_UPDATE)]
)
async def update_application(
    application_id: uuid.UUID, body: UpdateApplicationRequest, db: DbSession
) -> Envelope[ApplicationOut]:
    changes = body.model_dump(exclude_unset=True, exclude={"version", "declaration_confirmed"})
    row = await service.update_application(
        db,
        application_id,
        changes=changes,
        declaration=body.declaration_confirmed,
        version=body.version,
    )
    who = await caller(db, APPLICATION_UPDATE)
    return Envelope(data=application_out(row, who))


@application_routes.post(
    "/applications/{application_id}/submit", dependencies=[require_permission(APPLICATION_UPDATE)]
)
async def submit_application(
    application_id: uuid.UUID, body: SubmitRequest, db: DbSession
) -> Envelope[ApplicationOut]:
    row = await service.submit(db, application_id, version=body.version)
    who = await caller(db, APPLICATION_UPDATE)
    return Envelope(data=application_out(row, who))


@application_routes.post(
    "/applications/{application_id}/review", dependencies=[require_permission(APPLICATION_REVIEW)]
)
async def review_application(
    application_id: uuid.UUID, body: ReviewRequest, db: DbSession
) -> Envelope[ApplicationOut]:
    row = await service.review(
        db,
        application_id,
        target=ApplicationStatus(body.to_status),
        reason=body.reason,
        version=body.version,
    )
    who = await caller(db, APPLICATION_REVIEW)
    return Envelope(data=application_out(row, who))


@application_routes.get(
    "/applications/{application_id}/activity", dependencies=[require_permission(APPLICATION_READ)]
)
async def list_activity(
    application_id: uuid.UUID, db: DbSession, pagination: Pagination
) -> ListEnvelope[ApplicationActivityOut]:
    views, total = await service.list_activity(db, application_id, pagination)
    return ListEnvelope.build(
        [activity_out(view) for view in views],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@application_routes.get(
    "/applications/{application_id}/student-candidates",
    dependencies=[require_permission(ADMISSION_APPROVE)],
)
async def student_candidates(
    application_id: uuid.UUID, db: DbSession
) -> Envelope[StudentCandidatesOut]:
    rows = await service.student_candidates(db, application_id)
    candidates = [
        StudentCandidate(
            id=row.id,
            student_number=row.student_number,
            full_name=row.full_name,
            date_of_birth=row.date_of_birth,
            campus_code=row.campus_code,
            created_at=row.created_at,
            matched_on=_matched_on(row),
        )
        for row in rows
    ]
    return Envelope(data=StudentCandidatesOut(candidates=candidates))


@application_routes.post(
    "/applications/{application_id}/admit", dependencies=[require_permission(ADMISSION_APPROVE)]
)
async def admit_application(
    application_id: uuid.UUID, body: AdmitRequest, db: DbSession
) -> Envelope[ApplicationOut]:
    if body.student.value == "existing" and body.student_id is None:
        raise ValidationFailedError(
            details=[
                ErrorDetail(
                    field="student_id", code="required", message="Choose the student to link."
                )
            ]
        )
    row = await service.admit(
        db,
        application_id,
        choice=body.student,
        student_id=body.student_id,
        version=body.version,
    )
    who = await caller(db, ADMISSION_APPROVE)
    return Envelope(data=application_out(row, who))
