"""Lead routes (Phase 02-1; blueprint §17). Mounted by ``app.api.tenant``.

``/api/v1/leads*`` and ``/api/v1/lead-follow-ups/*``, one permission per
route (``lead.read`` / ``lead.create`` / ``lead.update`` / ``lead.assign``),
in the request transaction. A lead of another tenant, or of a campus outside
the caller's campuses, is not found (404). Contact details are searched with
``q`` only; the duplicate check is a POST so they never appear in URLs.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.core.authz import require_permission
from app.core.context import current_context
from app.core.db.session import DbSession
from app.core.errors import ErrorDetail, ValidationFailedError
from app.core.pagination import Pagination, SortField, sort_param
from app.core.schemas import Envelope, ListEnvelope
from app.modules.courses.domain import CourseStatus
from app.modules.leads import follow_ups, service
from app.modules.leads import repository as repo
from app.modules.leads.domain import (
    CLOSED_STATUSES,
    LEAD_TRANSITIONS,
    REASON_REQUIRED,
    FollowUpFilter,
    FollowUpStatus,
    LeadSource,
    LeadStatus,
    search_digits,
)
from app.modules.leads.permissions import LEAD_ASSIGN, LEAD_CREATE, LEAD_READ, LEAD_UPDATE
from app.modules.leads.schemas import (
    ActivityOut,
    Assignee,
    AssigneesOut,
    AssignRequest,
    CampusBrief,
    CampusRef,
    CancelFollowUpRequest,
    CompleteFollowUpRequest,
    CourseBrief,
    CourseRef,
    CreateLeadRequest,
    DuplicateCandidate,
    DuplicateCheckOut,
    DuplicateCheckRequest,
    FollowUpOut,
    FollowUpsOut,
    LeadListItem,
    LeadOut,
    LeadRef,
    NoteRequest,
    OwnerRef,
    PersonRef,
    RescheduleFollowUpRequest,
    ScheduleFollowUpRequest,
    TransitionOption,
    TransitionRequest,
    UpdateLeadRequest,
)

LEAD_SORT = ("created_at", "updated_at", "full_name", "next_follow_up_at")
LeadSort = Annotated[
    tuple[SortField, ...], Depends(sort_param(allowed=LEAD_SORT, default="-created_at"))
]
lead_routes = APIRouter(tags=["tenant-leads"])


def _invalid(field: str, message: str) -> ValidationFailedError:
    return ValidationFailedError(
        details=[ErrorDetail(field=field, code="invalid", message=message)]
    )


def transitions(current: str) -> list[TransitionOption]:
    status_now = LeadStatus(current)
    reopening = status_now in CLOSED_STATUSES
    return [
        TransitionOption(
            to_status=target,
            requires_reason=target in REASON_REQUIRED or reopening,
            requires_duplicate_target=target is LeadStatus.DUPLICATE,
        )
        for target in LeadStatus
        if LEAD_TRANSITIONS.allows(status_now, target)
    ]


def lead_out(row: repo.LeadDetailRow) -> LeadOut:
    lead = row.lead
    context = current_context()
    return LeadOut(
        id=lead.id,
        full_name=lead.full_name,
        mobile=lead.mobile,
        email=lead.email,
        date_of_birth=lead.date_of_birth,
        city=lead.city,
        highest_qualification=lead.highest_qualification,
        source=LeadSource(lead.source),
        status=LeadStatus(lead.status),
        status_reason=lead.status_reason,
        status_changed_at=lead.status_changed_at,
        interested_course=(
            CourseRef(
                id=lead.interested_course_id,
                code=row.course_code or "",
                name=row.course_name or "",
                status=CourseStatus(row.course_status),
            )
            if lead.interested_course_id and row.course_status
            else None
        ),
        campus=(
            CampusRef(id=lead.campus_id, code=row.campus_code or "", name=row.campus_name or "")
            if lead.campus_id
            else None
        ),
        owner=(
            OwnerRef(
                membership_id=lead.owner_membership_id,
                display_name=row.owner_name or "",
                active=bool(row.owner_active),
            )
            if lead.owner_membership_id
            else None
        ),
        duplicate_of=(
            LeadRef(id=lead.duplicate_of_lead_id, full_name=row.duplicate_name or "")
            if lead.duplicate_of_lead_id and service.duplicate_visible(row, context)
            else None
        ),
        next_follow_up_at=row.next_follow_up_at,
        overdue_follow_ups=row.overdue_follow_ups,
        created_by=PersonRef(display_name=row.creator_name) if row.creator_name else None,
        transitions=transitions(lead.status),
        created_at=lead.created_at,
        updated_at=lead.updated_at,
        version=lead.version,
    )


def list_item(row: repo.LeadListRow) -> LeadListItem:
    return LeadListItem(
        id=row.id,
        full_name=row.full_name,
        mobile=row.mobile,
        email=row.email,
        status=LeadStatus(row.status),
        source=LeadSource(row.source),
        interested_course=(
            CourseBrief(code=row.course_code, name=row.course_name or "")
            if row.course_code
            else None
        ),
        campus=CampusBrief(code=row.campus_code) if row.campus_code else None,
        owner=PersonRef(display_name=row.owner_name) if row.owner_name else None,
        next_follow_up_at=row.next_follow_up_at,
        overdue_follow_ups=row.overdue_follow_ups,
        transitions=transitions(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
        version=row.version,
    )


def follow_up_out(view: follow_ups.FollowUpView) -> FollowUpOut:
    item = view.item
    return FollowUpOut(
        id=item.id,
        lead_id=item.lead_id,
        due_at=item.due_at,
        kind=item.kind,  # type: ignore[arg-type]
        note=item.note,
        outcome=item.outcome,
        status=item.status,  # type: ignore[arg-type]
        overdue=view.overdue,
        assignee=OwnerRef(
            membership_id=item.assignee_membership_id,
            display_name=view.assignee_name or "",
            active=view.assignee_name is not None,
        ),
        completed_at=item.completed_at,
        completed_by=(
            PersonRef(display_name=view.completed_by_name) if view.completed_by_name else None
        ),
        created_at=item.created_at,
        version=item.version,
    )


def activity_out(view: follow_ups.ActivityView) -> ActivityOut:
    item = view.item
    return ActivityOut(
        id=item.id,
        kind=item.kind,  # type: ignore[arg-type]
        actor=PersonRef(display_name=view.actor_name) if view.actor_name else None,
        details=view.details,
        body=item.body,
        created_at=item.created_at,
    )


def _optional_uuid(value: str | None, field: str, keyword: str) -> tuple[bool, uuid.UUID | None]:
    """``(keyword given, UUID)`` for parameters like ``owner=unassigned|<id>``."""
    if value is None or value == "":
        return False, None
    if value == keyword:
        return True, None
    try:
        return False, uuid.UUID(value)
    except ValueError:
        raise _invalid(field, f"Use {keyword!r} or an ID.") from None


def _matched_on(row: repo.DuplicateRow) -> list[Literal["mobile", "email"]]:
    matched: list[Literal["mobile", "email"]] = []
    if row.mobile_match:
        matched.append("mobile")
    if row.email_match:
        matched.append("email")
    return matched


# --- Leads ---------------------------------------------------------------------------------


@lead_routes.get("/leads", dependencies=[require_permission(LEAD_READ)])
async def list_leads(
    db: DbSession,
    pagination: Pagination,
    sort: LeadSort,
    q: Annotated[str | None, Query(max_length=200)] = None,
    lead_status: Annotated[list[LeadStatus] | None, Query(alias="status")] = None,
    owner: Annotated[str | None, Query(max_length=40)] = None,
    campus: Annotated[str | None, Query(max_length=40)] = None,
    course: uuid.UUID | None = None,
    source: Annotated[list[LeadSource] | None, Query()] = None,
    follow_up: FollowUpFilter | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    utc_offset: Annotated[int, Query(ge=-720, le=840)] = 0,
) -> ListEnvelope[LeadListItem]:
    """``utc_offset``: the caller's offset in minutes, for "today" and the created dates."""
    search = q.strip() if q and q.strip() else None
    owner_id: uuid.UUID | None
    if owner == "me":
        unassigned, owner_id = False, await service.me(db)
    else:
        unassigned, owner_id = _optional_uuid(owner, "owner", "unassigned")
    pool, campus_id = _optional_uuid(campus, "campus", "none")
    local_today = (datetime.now(UTC) + timedelta(minutes=utc_offset)).date()
    day_start, day_end = repo.day_bounds(local_today, utc_offset)
    filters = repo.LeadFilters(
        search=search,
        search_digits=search_digits(search) if search else None,
        statuses=tuple(lead_status or ()),
        owner=owner_id,
        unassigned=unassigned,
        campus=campus_id,
        pool=pool,
        course=course,
        sources=tuple(source or ()),
        follow_up=follow_up.value if follow_up else None,
        day_start=day_start,
        day_end=day_end,
        created_from=repo.day_bounds(created_from, utc_offset)[0] if created_from else None,
        created_before=repo.day_bounds(created_to, utc_offset)[1] if created_to else None,
    )
    rows, total = await service.list_leads(db, filters, pagination, sort)
    return ListEnvelope.build(
        [list_item(row) for row in rows],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@lead_routes.post("/leads/duplicate-check", dependencies=[require_permission(LEAD_READ)])
async def duplicate_check(
    body: DuplicateCheckRequest, db: DbSession
) -> Envelope[DuplicateCheckOut]:
    if not (body.mobile and body.mobile.strip()) and not (body.email and body.email.strip()):
        raise _invalid("mobile", "Enter a mobile number or an email.")
    rows = await service.duplicate_check(
        db, mobile=body.mobile, email=body.email, exclude=body.exclude_lead_id
    )
    candidates = [
        DuplicateCandidate(
            id=row.id,
            full_name=row.full_name,
            status=LeadStatus(row.status),
            course_name=row.course_name,
            campus_name=row.campus_name,
            owner_name=row.owner_name,
            created_at=row.created_at,
            matched_on=_matched_on(row),
        )
        for row in rows
    ]
    return Envelope(data=DuplicateCheckOut(candidates=candidates))


@lead_routes.get("/leads/assignees", dependencies=[require_permission(LEAD_ASSIGN)])
async def list_assignees(
    db: DbSession, campus_id: Annotated[str | None, Query(max_length=40)] = None
) -> Envelope[AssigneesOut]:
    _, campus = _optional_uuid(campus_id, "campus_id", "none")
    members = await service.assignees(db, campus)
    items = [Assignee(membership_id=m.membership_id, display_name=m.display_name) for m in members]
    return Envelope(data=AssigneesOut(items=items))


@lead_routes.post(
    "/leads", status_code=status.HTTP_201_CREATED, dependencies=[require_permission(LEAD_CREATE)]
)
async def create_lead(body: CreateLeadRequest, db: DbSession) -> Envelope[LeadOut]:
    values = body.model_dump(exclude={"campus_id", "owner"})
    row = await service.create_lead(db, values=values, campus_id=body.campus_id, owner=body.owner)
    return Envelope(data=lead_out(row))


@lead_routes.get("/leads/{lead_id}", dependencies=[require_permission(LEAD_READ)])
async def read_lead(lead_id: uuid.UUID, db: DbSession) -> Envelope[LeadOut]:
    return Envelope(data=lead_out(await service.get_lead(db, lead_id)))


@lead_routes.patch("/leads/{lead_id}", dependencies=[require_permission(LEAD_UPDATE)])
async def update_lead(
    lead_id: uuid.UUID, body: UpdateLeadRequest, db: DbSession
) -> Envelope[LeadOut]:
    changes = body.model_dump(exclude_unset=True, exclude={"version"})
    row = await service.update_lead(db, lead_id, changes=changes, version=body.version)
    return Envelope(data=lead_out(row))


@lead_routes.post("/leads/{lead_id}/transition", dependencies=[require_permission(LEAD_UPDATE)])
async def transition_lead(
    lead_id: uuid.UUID, body: TransitionRequest, db: DbSession
) -> Envelope[LeadOut]:
    row = await service.transition(
        db,
        lead_id,
        target=body.to_status,
        reason=body.reason,
        duplicate_of=body.duplicate_of_lead_id,
        version=body.version,
    )
    return Envelope(data=lead_out(row))


@lead_routes.post("/leads/{lead_id}/assign", dependencies=[require_permission(LEAD_ASSIGN)])
async def assign_lead(lead_id: uuid.UUID, body: AssignRequest, db: DbSession) -> Envelope[LeadOut]:
    row = await service.assign(
        db,
        lead_id,
        owner_id=body.owner_membership_id,
        campus_id=body.campus_id,
        version=body.version,
    )
    return Envelope(data=lead_out(row))


# --- Follow-ups ----------------------------------------------------------------------------


@lead_routes.get("/leads/{lead_id}/follow-ups", dependencies=[require_permission(LEAD_READ)])
async def list_follow_ups(
    lead_id: uuid.UUID,
    db: DbSession,
    follow_up_status: Annotated[FollowUpStatus | None, Query(alias="status")] = None,
) -> Envelope[FollowUpsOut]:
    views = await follow_ups.list_follow_ups(db, lead_id, follow_up_status)
    return Envelope(data=FollowUpsOut(items=[follow_up_out(view) for view in views]))


@lead_routes.post(
    "/leads/{lead_id}/follow-ups",
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(LEAD_UPDATE)],
)
async def schedule_follow_up(
    lead_id: uuid.UUID, body: ScheduleFollowUpRequest, db: DbSession
) -> Envelope[FollowUpOut]:
    view = await follow_ups.schedule(
        db,
        lead_id,
        due_at=body.due_at,
        kind=body.kind,
        note=body.note,
        assignee=body.assignee_membership_id,
    )
    return Envelope(data=follow_up_out(view))


@lead_routes.patch(
    "/lead-follow-ups/{follow_up_id}", dependencies=[require_permission(LEAD_UPDATE)]
)
async def reschedule_follow_up(
    follow_up_id: uuid.UUID, body: RescheduleFollowUpRequest, db: DbSession
) -> Envelope[FollowUpOut]:
    changes = body.model_dump(exclude_unset=True, exclude={"version"})
    view = await follow_ups.reschedule(db, follow_up_id, changes=changes, version=body.version)
    return Envelope(data=follow_up_out(view))


@lead_routes.post(
    "/lead-follow-ups/{follow_up_id}/complete", dependencies=[require_permission(LEAD_UPDATE)]
)
async def complete_follow_up(
    follow_up_id: uuid.UUID, body: CompleteFollowUpRequest, db: DbSession
) -> Envelope[FollowUpOut]:
    view = await follow_ups.complete(db, follow_up_id, outcome=body.outcome, version=body.version)
    return Envelope(data=follow_up_out(view))


@lead_routes.post(
    "/lead-follow-ups/{follow_up_id}/cancel", dependencies=[require_permission(LEAD_UPDATE)]
)
async def cancel_follow_up(
    follow_up_id: uuid.UUID, body: CancelFollowUpRequest, db: DbSession
) -> Envelope[FollowUpOut]:
    view = await follow_ups.cancel(db, follow_up_id, version=body.version)
    return Envelope(data=follow_up_out(view))


# --- Activity and notes --------------------------------------------------------------------


@lead_routes.get("/leads/{lead_id}/activity", dependencies=[require_permission(LEAD_READ)])
async def list_activity(
    lead_id: uuid.UUID, db: DbSession, pagination: Pagination
) -> ListEnvelope[ActivityOut]:
    views, total = await follow_ups.list_activity(db, lead_id, pagination)
    return ListEnvelope.build(
        [activity_out(view) for view in views],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@lead_routes.post(
    "/leads/{lead_id}/notes",
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(LEAD_UPDATE)],
)
async def add_note(lead_id: uuid.UUID, body: NoteRequest, db: DbSession) -> Envelope[ActivityOut]:
    view = await follow_ups.add_note(db, lead_id, body=body.body)
    return Envelope(data=activity_out(view))
