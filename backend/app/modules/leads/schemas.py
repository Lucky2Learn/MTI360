"""Lead API contracts (Phase 02-1; blueprint §17).

Request models reject unknown fields (``RequestModel``): a ``tenant_id``,
``status``, ``campus_id`` or ``owner`` that a route does not declare is a 422.
Responses never contain another tenant's data, and the "duplicate of" link
is omitted when the caller may not read that lead.
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints

from app.core.schemas import RequestModel, ResponseModel
from app.modules.courses.domain import CourseStatus
from app.modules.leads.domain import (
    FOLLOW_UP_TEXT_MAX_LENGTH,
    NOTE_MAX_LENGTH,
    REASON_MAX_LENGTH,
    ActivityKind,
    FollowUpKind,
    FollowUpStatus,
    LeadSource,
    LeadStatus,
)

Version = Annotated[int, Field(ge=1)]
Name = Annotated[str, StringConstraints(min_length=1, max_length=200)]
Mobile = Annotated[str, StringConstraints(max_length=32)]
Email = Annotated[str, StringConstraints(max_length=254)]
City = Annotated[str, StringConstraints(max_length=120)]
Qualification = Annotated[str, StringConstraints(max_length=200)]
FollowUpText = Annotated[str, StringConstraints(max_length=FOLLOW_UP_TEXT_MAX_LENGTH)]


# --- Responses -----------------------------------------------------------------------------


class CourseRef(ResponseModel):
    id: uuid.UUID
    code: str
    name: str
    status: CourseStatus


class CampusRef(ResponseModel):
    id: uuid.UUID
    code: str
    name: str


class OwnerRef(ResponseModel):
    membership_id: uuid.UUID
    display_name: str
    active: bool


class PersonRef(ResponseModel):
    display_name: str


class LeadRef(ResponseModel):
    id: uuid.UUID
    full_name: str


class TransitionOption(ResponseModel):
    """A status the caller may move the lead to now (the server rule, for the UI)."""

    to_status: LeadStatus
    requires_reason: bool
    requires_duplicate_target: bool


class LeadOut(ResponseModel):
    id: uuid.UUID
    full_name: str
    mobile: str | None
    email: str | None
    date_of_birth: date | None
    city: str | None
    highest_qualification: str | None
    source: LeadSource
    status: LeadStatus
    status_reason: str | None
    status_changed_at: datetime
    interested_course: CourseRef | None
    campus: CampusRef | None
    owner: OwnerRef | None
    duplicate_of: LeadRef | None
    next_follow_up_at: datetime | None
    overdue_follow_ups: int
    created_by: PersonRef | None
    transitions: list[TransitionOption]
    created_at: datetime
    updated_at: datetime
    version: int


class CourseBrief(ResponseModel):
    code: str
    name: str


class CampusBrief(ResponseModel):
    id: uuid.UUID
    code: str


class OwnerBrief(ResponseModel):
    membership_id: uuid.UUID
    display_name: str


class LeadListItem(ResponseModel):
    id: uuid.UUID
    full_name: str
    mobile: str | None
    email: str | None
    status: LeadStatus
    source: LeadSource
    interested_course: CourseBrief | None
    campus: CampusBrief | None
    owner: OwnerBrief | None
    next_follow_up_at: datetime | None
    overdue_follow_ups: int
    transitions: list[TransitionOption]
    created_at: datetime
    updated_at: datetime
    version: int


class DuplicateCandidate(ResponseModel):
    id: uuid.UUID
    full_name: str
    status: LeadStatus
    course_name: str | None
    campus_name: str | None
    owner_name: str | None
    created_at: datetime
    matched_on: list[Literal["mobile", "email"]]


class DuplicateCheckOut(ResponseModel):
    candidates: list[DuplicateCandidate]


class Assignee(ResponseModel):
    membership_id: uuid.UUID
    display_name: str


class AssigneesOut(ResponseModel):
    items: list[Assignee]


class FollowUpOut(ResponseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    due_at: datetime
    kind: FollowUpKind
    note: str | None
    outcome: str | None
    status: FollowUpStatus
    overdue: bool
    assignee: OwnerRef | None
    completed_at: datetime | None
    completed_by: PersonRef | None
    created_at: datetime
    version: int


class FollowUpsOut(ResponseModel):
    items: list[FollowUpOut]


class ActivityOut(ResponseModel):
    id: uuid.UUID
    kind: ActivityKind
    actor: PersonRef | None
    details: dict[str, Any]
    body: str | None
    created_at: datetime


# --- Requests ------------------------------------------------------------------------------


class CreateLeadRequest(RequestModel):
    full_name: Name
    mobile: Mobile | None = None
    email: Email | None = None
    source: LeadSource
    interested_course_id: uuid.UUID | None = None
    campus_id: uuid.UUID | None = None
    owner: Literal["me"] | uuid.UUID | None = None
    date_of_birth: date | None = None
    city: City | None = None
    highest_qualification: Qualification | None = None


class UpdateLeadRequest(RequestModel):
    """Only the fields sent change. Campus and owner change through ``/assign``."""

    full_name: Name | None = None
    mobile: Mobile | None = None
    email: Email | None = None
    source: LeadSource | None = None
    interested_course_id: uuid.UUID | None = None
    date_of_birth: date | None = None
    city: City | None = None
    highest_qualification: Qualification | None = None
    version: Version


class TransitionRequest(RequestModel):
    to_status: LeadStatus
    reason: Annotated[str, StringConstraints(max_length=REASON_MAX_LENGTH)] | None = None
    duplicate_of_lead_id: uuid.UUID | None = None
    version: Version


class AssignRequest(RequestModel):
    """The full assignment: both fields are always sent (null = unassigned / pool)."""

    owner_membership_id: uuid.UUID | None
    campus_id: uuid.UUID | None
    version: Version


class DuplicateCheckRequest(RequestModel):
    mobile: Mobile | None = None
    email: Email | None = None
    exclude_lead_id: uuid.UUID | None = None


class ScheduleFollowUpRequest(RequestModel):
    due_at: datetime
    kind: FollowUpKind
    note: FollowUpText | None = None
    assignee_membership_id: uuid.UUID | None = None


class RescheduleFollowUpRequest(RequestModel):
    due_at: datetime | None = None
    kind: FollowUpKind | None = None
    note: FollowUpText | None = None
    assignee_membership_id: uuid.UUID | None = None
    version: Version


class CompleteFollowUpRequest(RequestModel):
    outcome: FollowUpText | None = None
    version: Version


class CancelFollowUpRequest(RequestModel):
    version: Version


class NoteRequest(RequestModel):
    body: Annotated[str, StringConstraints(min_length=1, max_length=NOTE_MAX_LENGTH)]
