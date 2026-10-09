"""Application API contracts (Phase 02-2; ADR-0021 §3-§6).

Request models reject unknown fields (``RequestModel``): a ``tenant_id``,
``status``, ``number`` or ``owner`` that a route does not declare is a 422.
The lead link is omitted when the caller may not read that lead.
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints

from app.core.schemas import RequestModel, ResponseModel
from app.modules.applications.domain import (
    ADDRESS_MAX_LENGTH,
    REASON_MAX_LENGTH,
    TEXT_MAX_LENGTH,
    ActivityKind,
    ApplicationStatus,
)
from app.modules.courses.domain import CourseStatus
from app.modules.leads.domain import LeadStatus
from app.modules.leads.schemas import CampusRef, PersonRef
from app.modules.students.domain import StudentChoice

Version = Annotated[int, Field(ge=1)]
Short = Annotated[str, StringConstraints(max_length=200)]
Text = Annotated[str, StringConstraints(max_length=TEXT_MAX_LENGTH)]


class ApplicationDetails(RequestModel):
    """The applicant's details as entered (every field optional; validated by the service)."""

    full_name: Annotated[str, StringConstraints(max_length=200)] | None = None
    date_of_birth: date | None = None
    mobile: Annotated[str, StringConstraints(max_length=32)] | None = None
    email: Annotated[str, StringConstraints(max_length=254)] | None = None
    address: Annotated[str, StringConstraints(max_length=ADDRESS_MAX_LENGTH)] | None = None
    city: Short | None = None
    state: Short | None = None
    postal_code: Annotated[str, StringConstraints(max_length=16)] | None = None
    highest_qualification: Short | None = None
    education_details: Text | None = None
    indos_number: Annotated[str, StringConstraints(max_length=32)] | None = None
    cdc_number: Annotated[str, StringConstraints(max_length=40)] | None = None
    eligibility_notes: Text | None = None


class CreateApplicationRequest(ApplicationDetails):
    lead_id: uuid.UUID | None = None
    course_id: uuid.UUID
    campus_id: uuid.UUID


class UpdateApplicationRequest(ApplicationDetails):
    course_id: uuid.UUID | None = None
    campus_id: uuid.UUID | None = None
    declaration_confirmed: bool | None = None
    """True: staff confirm the applicant made the declaration (who and when are recorded)."""
    version: Version


class SubmitRequest(RequestModel):
    version: Version


class ReviewRequest(RequestModel):
    to_status: Literal[
        ApplicationStatus.UNDER_REVIEW,
        ApplicationStatus.APPROVED,
        ApplicationStatus.CORRECTION_REQUIRED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.NOT_ELIGIBLE,
    ]
    reason: Annotated[str, StringConstraints(max_length=REASON_MAX_LENGTH)] | None = None
    version: Version


class AdmitRequest(RequestModel):
    student: StudentChoice
    """``new``: create the student; ``existing``: link ``student_id`` (an explicit choice)."""
    student_id: uuid.UUID | None = None
    version: Version


# --- Responses -----------------------------------------------------------------------------


class CourseRef(ResponseModel):
    id: uuid.UUID
    code: str
    name: str
    status: CourseStatus


class LeadLink(ResponseModel):
    id: uuid.UUID
    full_name: str
    status: LeadStatus


class AdmissionLink(ResponseModel):
    id: uuid.UUID
    admission_number: str
    student_id: uuid.UUID
    student_number: str
    student_visible: bool


class DocumentSummary(ResponseModel):
    total: int
    verified: int
    pending: int


class ReviewOption(ResponseModel):
    to_status: ApplicationStatus
    requires_reason: bool


class ApplicationOut(ResponseModel):
    id: uuid.UUID
    number: str
    status: ApplicationStatus
    status_reason: str | None
    status_changed_at: datetime
    lead: LeadLink | None
    course: CourseRef
    campus: CampusRef
    owner: PersonRef | None
    created_by: PersonRef | None
    submitted_at: datetime | None
    reviewed_at: datetime | None
    reviewed_by: PersonRef | None
    declared_at: datetime | None
    declared_by: PersonRef | None
    full_name: str
    date_of_birth: date | None
    mobile: str | None
    email: str | None
    address: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    highest_qualification: str | None
    education_details: str | None
    indos_number: str | None
    cdc_number: str | None
    eligibility_notes: str | None
    documents: DocumentSummary
    editable: bool
    missing_for_submit: list[str]
    review_options: list[ReviewOption]
    admission: AdmissionLink | None
    created_at: datetime
    updated_at: datetime
    version: int


class ApplicationListItem(ResponseModel):
    id: uuid.UUID
    number: str
    full_name: str
    status: ApplicationStatus
    lead_id: uuid.UUID | None
    course_code: str
    course_name: str
    campus_id: uuid.UUID
    campus_code: str
    owner_name: str | None
    documents_pending: int
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


class ApplicationActivityOut(ResponseModel):
    id: uuid.UUID
    kind: ActivityKind
    actor: PersonRef | None
    details: dict[str, Any]
    created_at: datetime


class StudentCandidate(ResponseModel):
    id: uuid.UUID
    student_number: str
    full_name: str
    date_of_birth: date | None
    campus_code: str
    created_at: datetime
    matched_on: list[Literal["mobile", "email"]]


class StudentCandidatesOut(ResponseModel):
    candidates: list[StudentCandidate]
