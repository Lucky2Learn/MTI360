"""Lead management (Phase 02-1; blueprint §7-§10, §13, §17, ADR-0020 §3-§7).

Authorization (D-B1): every lead permission is campus-scoped. A lead with no
campus (the institute pool, L6) is visible to every holder; a campus lead only
to members with that campus; anything else is **not found** (404). Lists and
the duplicate check apply the same rule as a SQL predicate
(``campus_visibility``). Ownership is a work-queue attribute, never an
authorization boundary (ADR-0020 Y1).

Every mutation checks the optimistic ``version`` (409 when stale), records a
``lead_activities`` row and, for profile, status and assignment changes, a
``domain`` audit event in the same transaction. Audit metadata carries only
sources, statuses, field names and booleans: never a name, mobile, email,
reason or note text.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal, cast

from sqlalchemy import Table, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.activity import record_activity
from app.core.audit import AuditTarget, write_audit_event
from app.core.authz import Permission, authorize, campus_visible
from app.core.context import RequestContext, current_context
from app.core.errors import (
    ConflictError,
    ErrorDetail,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from app.core.pagination import PageParams, SortField
from app.modules.courses.domain import CourseStatus
from app.modules.leads import events
from app.modules.leads import repository as repo
from app.modules.leads.domain import (
    APPLICATION_START,
    CITY_MAX_LENGTH,
    INITIAL_STATUS,
    QUALIFICATION_MAX_LENGTH,
    REASON_MAX_LENGTH,
    ActivityKind,
    LeadSource,
    LeadStatus,
    TransitionProblem,
    birth_date_valid,
    clean_email,
    clean_mobile,
    clean_name,
    clean_optional,
    clean_text,
    mobile_key,
    transition_problem,
)
from app.modules.leads.models import Lead, LeadActivity
from app.modules.leads.permissions import LEAD_ASSIGN, LEAD_CREATE, LEAD_READ, LEAD_UPDATE

ACTIVITIES = cast(Table, LeadActivity.__table__)
STALE = "This lead was changed by someone else. Reload and try again."
PROFILE_FIELDS = (
    "full_name",
    "mobile",
    "email",
    "source",
    "interested_course_id",
    "date_of_birth",
    "city",
    "highest_qualification",
)
"""Fields of ``PATCH /leads/{id}``. Campus and owner change only through assignment."""

type Owner = Literal["me"] | uuid.UUID | None


@dataclass(frozen=True, slots=True)
class LeadResource:
    """A lead as an authorization resource: its campus, or none for the institute pool."""

    tenant_id: uuid.UUID
    campus_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class Caller:
    context: RequestContext
    tenant_id: uuid.UUID
    membership_id: uuid.UUID


def _detail(field: str, code: str, message: str) -> ErrorDetail:
    return ErrorDetail(field=field, code=code, message=message)


def _invalid(*details: ErrorDetail) -> ValidationFailedError:
    return ValidationFailedError(details=list(details))


COURSE_NOT_ACTIVE = _detail("interested_course_id", "course_not_active", "Choose an active course.")
CAMPUS_NOT_AVAILABLE = _detail(
    "campus_id", "campus_not_available", "Choose one of your campuses, or institute-wide."
)
OWNER_NOT_ELIGIBLE = _detail(
    "owner", "owner_not_eligible", "Choose an active team member who works with this campus."
)


async def caller(db: AsyncSession, permission: Permission) -> Caller:
    """Authorize ``permission`` (no resource) and resolve the caller's membership."""
    context = current_context()
    authorize(context, permission)
    if context.tenant_id is None or context.principal_id is None:  # authorize() refused already
        raise PermissionDeniedError()
    membership_id = await repo.membership_of(db, context.tenant_id, context.principal_id)
    if membership_id is None:
        raise PermissionDeniedError()
    return Caller(context, context.tenant_id, membership_id)


async def authorized_lead(
    db: AsyncSession, who: Caller, lead_id: uuid.UUID, permission: Permission
) -> Lead:
    """The lead, if it exists in the tenant and its campus is the caller's (404 otherwise)."""
    found = await repo.lead(db, who.tenant_id, lead_id)
    if found is None:
        raise NotFoundError()
    authorize(who.context, permission, LeadResource(found.tenant_id, found.campus_id))
    return found


# --- Validation ----------------------------------------------------------------------------


def _profile(values: Mapping[str, Any], today: date) -> tuple[dict[str, Any], list[ErrorDetail]]:
    """Clean the provided profile fields; ``mobile``/``email`` also set their duplicate keys."""
    cleaned: dict[str, Any] = {}
    problems: list[ErrorDetail] = []
    if "full_name" in values:
        name = clean_name(values["full_name"] or "")
        if name is None:
            problems.append(_detail("full_name", "required", "Enter the enquirer's name."))
        cleaned["full_name"] = name
    if "mobile" in values:
        try:
            mobile = clean_mobile(values["mobile"])
        except ValueError:
            problems.append(_detail("mobile", "invalid", "Enter a valid mobile number."))
            mobile = None
        cleaned["mobile"], cleaned["mobile_key"] = mobile, mobile_key(mobile)
    if "email" in values:
        try:
            email = clean_email(values["email"])
        except ValueError:
            problems.append(_detail("email", "invalid", "Enter a valid email address."))
            email = None
        cleaned["email"] = email[0] if email else None
        cleaned["email_normalized"] = email[1] if email else None
    if "source" in values:
        if values["source"] is None:
            problems.append(_detail("source", "required", "Choose where the enquiry came from."))
        else:
            cleaned["source"] = LeadSource(values["source"]).value
    if "interested_course_id" in values:
        cleaned["interested_course_id"] = values["interested_course_id"]
    if "date_of_birth" in values:
        if not birth_date_valid(values["date_of_birth"], today):
            problems.append(_detail("date_of_birth", "invalid", "Enter a date in the past."))
        cleaned["date_of_birth"] = values["date_of_birth"]
    for field, limit in (
        ("city", CITY_MAX_LENGTH),
        ("highest_qualification", QUALIFICATION_MAX_LENGTH),
    ):
        if field in values:
            try:
                cleaned[field] = clean_optional(values[field], limit)
            except ValueError:
                problems.append(_detail(field, "too_long", f"Use at most {limit} characters."))
    return cleaned, problems


async def _active_course(db: AsyncSession, tenant_id: uuid.UUID, course_id: uuid.UUID) -> bool:
    return await repo.course_status(db, tenant_id, course_id) == CourseStatus.ACTIVE.value


async def _campus_available(db: AsyncSession, who: Caller, campus_id: uuid.UUID | None) -> bool:
    """NULL (the pool) always; otherwise a campus of the tenant within the caller's scope.
    Unknown and inaccessible campuses are indistinguishable (same 422)."""
    if campus_id is None:
        return True
    return campus_visible(campus_id, who.context) and await repo.campus_exists(
        db, who.tenant_id, campus_id
    )


async def owner_eligible(
    db: AsyncSession, tenant_id: uuid.UUID, membership_id: uuid.UUID, campus_id: uuid.UUID | None
) -> bool:
    """Blueprint §10: ACTIVE, holds ``lead.update``, campus scope covers the lead's campus."""
    found = await repo.eligible_members(
        db,
        tenant_id,
        permission_code=LEAD_UPDATE.code,
        campus_id=campus_id,
        membership_id=membership_id,
    )
    return bool(found)


def _today() -> date:
    return datetime.now(UTC).date()


# --- Reads ---------------------------------------------------------------------------------


async def list_leads(
    db: AsyncSession, filters: repo.LeadFilters, page: PageParams, sort: tuple[SortField, ...]
) -> tuple[list[repo.LeadListRow], int]:
    who = await caller(db, LEAD_READ)
    return await repo.search_leads(db, who.tenant_id, who.context, filters, page, sort)


async def me(db: AsyncSession) -> uuid.UUID:
    """The caller's membership (``owner=me``)."""
    return (await caller(db, LEAD_READ)).membership_id


async def get_lead(db: AsyncSession, lead_id: uuid.UUID) -> repo.LeadDetailRow:
    who = await caller(db, LEAD_READ)
    await authorized_lead(db, who, lead_id, LEAD_READ)
    return await _detail_row(db, who, lead_id)


async def _detail_row(db: AsyncSession, who: Caller, lead_id: uuid.UUID) -> repo.LeadDetailRow:
    row = await repo.lead_detail(db, who.tenant_id, lead_id)
    if row is None:
        raise NotFoundError()
    return row


def duplicate_visible(row: repo.LeadDetailRow, context: RequestContext) -> bool:
    """The "duplicate of" link is shown only when the caller may read that lead."""
    return row.duplicate_name is not None and campus_visible(row.duplicate_campus_id, context)


async def duplicate_check(
    db: AsyncSession, *, mobile: str | None, email: str | None, exclude: uuid.UUID | None
) -> list[repo.DuplicateRow]:
    """Possible duplicates the caller may read (§8). Invalid input simply matches nothing."""
    who = await caller(db, LEAD_READ)
    try:
        key = mobile_key(clean_mobile(mobile))
    except ValueError:
        key = None
    try:
        cleaned = clean_email(email)
    except ValueError:
        cleaned = None
    return await repo.duplicate_candidates(
        db,
        who.tenant_id,
        who.context,
        mobile_key=key,
        email_normalized=cleaned[1] if cleaned else None,
        exclude=exclude,
    )


async def assignees(db: AsyncSession, campus_id: uuid.UUID | None) -> list[repo.Member]:
    """Members a lead of ``campus_id`` (None: the pool) may be assigned to (``lead.assign``)."""
    who = await caller(db, LEAD_ASSIGN)
    if not await _campus_available(db, who, campus_id):
        raise _invalid(CAMPUS_NOT_AVAILABLE)
    return await repo.eligible_members(
        db, who.tenant_id, permission_code=LEAD_UPDATE.code, campus_id=campus_id
    )


# --- Commands ------------------------------------------------------------------------------


async def create_lead(
    db: AsyncSession,
    *,
    values: Mapping[str, Any],
    campus_id: uuid.UUID | None,
    owner: Owner,
) -> repo.LeadDetailRow:
    """A ``NEW`` lead. ``owner="me"`` needs only ``lead.create``; another owner needs
    ``lead.assign``. Possible duplicates never block (warning only, §8)."""
    who = await caller(db, LEAD_CREATE)
    cleaned, problems = _profile({field: values.get(field) for field in PROFILE_FIELDS}, _today())
    if (
        not cleaned.get("mobile")
        and not cleaned.get("email")
        and not any(p.field in {"mobile", "email"} for p in problems)
    ):
        problems.append(_detail("mobile", "contact_required", "Enter a mobile number or an email."))
    course_id = cleaned.get("interested_course_id")
    if course_id is not None and not await _active_course(db, who.tenant_id, course_id):
        problems.append(COURSE_NOT_ACTIVE)
    if not await _campus_available(db, who, campus_id):
        problems.append(CAMPUS_NOT_AVAILABLE)
    owner_id: uuid.UUID | None = None
    if owner == "me":
        owner_id = who.membership_id
    elif isinstance(owner, uuid.UUID):
        if owner != who.membership_id:
            authorize(who.context, LEAD_ASSIGN)  # 403: assigning someone else is assignment
        owner_id = owner
    if owner_id is not None and not await owner_eligible(db, who.tenant_id, owner_id, campus_id):
        problems.append(OWNER_NOT_ELIGIBLE)
    if problems:
        raise _invalid(*problems)
    authorize(who.context, LEAD_CREATE, LeadResource(who.tenant_id, campus_id))
    duplicates = await repo.duplicate_candidates(
        db,
        who.tenant_id,
        who.context,
        mobile_key=cleaned["mobile_key"],
        email_normalized=cleaned["email_normalized"],
        exclude=None,
    )
    lead = Lead(
        tenant_id=who.tenant_id,
        status=INITIAL_STATUS.value,
        campus_id=campus_id,
        owner_membership_id=owner_id,
        created_by_membership_id=who.membership_id,
        **cleaned,
    )
    db.add(lead)
    await db.flush()
    await record_activity(
        db,
        ACTIVITIES,
        subject_column="lead_id",
        subject_id=lead.id,
        kind=ActivityKind.CREATED.value,
        actor_membership_id=who.membership_id,
        details={"source": lead.source, "possible_duplicates": len(duplicates)},
    )
    await write_audit_event(
        db,
        events.LEAD_CREATED,
        target=AuditTarget("lead", lead.id),
        metadata={
            "source": lead.source,
            "has_course": course_id is not None,
            "has_campus": campus_id is not None,
            "has_owner": owner_id is not None,
        },
    )
    return await _detail_row(db, who, lead.id)


async def update_lead(
    db: AsyncSession, lead_id: uuid.UUID, *, changes: Mapping[str, Any], version: int
) -> repo.LeadDetailRow:
    """Edit the provided profile fields (optimistic ``version``)."""
    who = await caller(db, LEAD_UPDATE)
    lead = await authorized_lead(db, who, lead_id, LEAD_UPDATE)
    if lead.version != version:
        raise ConflictError(STALE)
    cleaned, problems = _profile(changes, _today())
    mobile = cleaned.get("mobile", lead.mobile)
    email = cleaned.get("email", lead.email)
    if not mobile and not email and not any(p.field in {"mobile", "email"} for p in problems):
        problems.append(_detail("mobile", "contact_required", "Enter a mobile number or an email."))
    course_id = cleaned.get("interested_course_id")
    if (
        course_id is not None
        and course_id != lead.interested_course_id
        and not await _active_course(db, who.tenant_id, course_id)
    ):
        problems.append(COURSE_NOT_ACTIVE)
    if problems:
        raise _invalid(*problems)
    changed = sorted(
        field
        for field in PROFILE_FIELDS
        if field in cleaned and getattr(lead, field) != cleaned[field]
    )
    if not changed:
        return await _detail_row(db, who, lead.id)
    for field, value in cleaned.items():
        setattr(lead, field, value)
    await db.flush()
    await record_activity(
        db,
        ACTIVITIES,
        subject_column="lead_id",
        subject_id=lead.id,
        kind=ActivityKind.UPDATED.value,
        actor_membership_id=who.membership_id,
        details={"fields": changed},
    )
    await write_audit_event(
        db,
        events.LEAD_UPDATED,
        target=AuditTarget("lead", lead.id),
        metadata={"changed_fields": changed},
    )
    return await _detail_row(db, who, lead.id)


async def transition(
    db: AsyncSession,
    lead_id: uuid.UUID,
    *,
    target: LeadStatus,
    reason: str | None,
    duplicate_of: uuid.UUID | None,
    version: int,
) -> repo.LeadDetailRow:
    """Move a lead through the staff pipeline (``LEAD_TRANSITIONS``, blueprint §9)."""
    who = await caller(db, LEAD_UPDATE)
    lead = await authorized_lead(db, who, lead_id, LEAD_UPDATE)
    if lead.version != version:
        raise ConflictError(STALE)
    try:
        clean_reason = clean_text(reason, REASON_MAX_LENGTH)
    except ValueError:
        raise _invalid(_detail("reason", "too_long", "Use at most 500 characters.")) from None
    target_ok = target is LeadStatus.DUPLICATE and await _duplicate_target_ok(
        db, who, lead, duplicate_of
    )
    current = LeadStatus(lead.status)
    problem = transition_problem(
        current, target, reason=clean_reason, has_duplicate_target=target_ok
    )
    if problem is not None:
        field = {
            TransitionProblem.INVALID: "to_status",
            TransitionProblem.REASON_REQUIRED: "reason",
            TransitionProblem.DUPLICATE_TARGET: "duplicate_of_lead_id",
        }[problem]
        raise _invalid(_detail(field, problem.value, _PROBLEM_MESSAGES[problem]))
    lead.status = target.value
    lead.status_reason = clean_reason
    lead.status_changed_at = func.now()
    lead.duplicate_of_lead_id = duplicate_of if target is LeadStatus.DUPLICATE else None
    await db.flush()
    await _status_changed(db, who.membership_id, lead, current, target, clean_reason)
    return await _detail_row(db, who, lead.id)


_PROBLEM_MESSAGES = {
    TransitionProblem.INVALID: "This lead cannot move to that status.",
    TransitionProblem.REASON_REQUIRED: "Enter a reason.",
    TransitionProblem.DUPLICATE_TARGET: "Choose the original lead this one duplicates.",
}


async def _duplicate_target_ok(
    db: AsyncSession, who: Caller, lead: Lead, target_id: uuid.UUID | None
) -> bool:
    """Another visible lead of the tenant that is not itself a duplicate (§9).
    An invisible target answers exactly like a missing one."""
    if target_id is None or target_id == lead.id:
        return False
    target = await repo.lead(db, who.tenant_id, target_id)
    return (
        target is not None
        and campus_visible(target.campus_id, who.context)
        and target.status != LeadStatus.DUPLICATE.value
    )


async def _status_changed(
    db: AsyncSession,
    actor: uuid.UUID | None,
    lead: Lead,
    current: LeadStatus,
    target: LeadStatus,
    reason: str | None,
) -> None:
    details: dict[str, object] = {"from": current.value, "to": target.value}
    if reason:
        details["reason"] = reason
    if lead.duplicate_of_lead_id is not None:
        details["duplicate_of"] = lead.duplicate_of_lead_id
    await record_activity(
        db,
        ACTIVITIES,
        subject_column="lead_id",
        subject_id=lead.id,
        kind=ActivityKind.STATUS_CHANGED.value,
        actor_membership_id=actor,
        details=details,
    )
    await write_audit_event(
        db,
        events.LEAD_STATUS_CHANGED,
        target=AuditTarget("lead", lead.id),
        metadata={"from": current.value, "to": target.value, "has_reason": reason is not None},
    )


async def mark_application_started(
    db: AsyncSession, lead_id: uuid.UUID, *, actor_membership_id: uuid.UUID | None
) -> Lead:
    """The 02-2 system transition: an application was created for this open lead.

    Called by the application service in the transaction that creates the
    application (after its own authorization); never exposed as a route in
    02-1. Closed and already progressed leads are refused.
    """
    context = current_context()
    if context.tenant_id is None:
        raise PermissionDeniedError()
    lead = await repo.lead(db, context.tenant_id, lead_id)
    if lead is None:
        raise NotFoundError()
    current = LeadStatus(lead.status)
    if not APPLICATION_START.allows(current, LeadStatus.APPLICATION):
        raise _invalid(
            _detail("lead_id", TransitionProblem.INVALID.value, "This lead is not open.")
        )
    lead.status = LeadStatus.APPLICATION.value
    lead.status_reason = None
    lead.status_changed_at = func.now()
    await db.flush()
    await _status_changed(db, actor_membership_id, lead, current, LeadStatus.APPLICATION, None)
    return lead


async def assign(
    db: AsyncSession,
    lead_id: uuid.UUID,
    *,
    owner_id: uuid.UUID | None,
    campus_id: uuid.UUID | None,
    version: int,
) -> repo.LeadDetailRow:
    """Set the owner and campus together (§10). The caller must see both campuses; the
    owner must be eligible for the (new) campus whenever either changes."""
    who = await caller(db, LEAD_ASSIGN)
    lead = await authorized_lead(db, who, lead_id, LEAD_ASSIGN)
    if lead.version != version:
        raise ConflictError(STALE)
    owner_changed = owner_id != lead.owner_membership_id
    campus_changed = campus_id != lead.campus_id
    if not owner_changed and not campus_changed:
        return await _detail_row(db, who, lead.id)
    problems: list[ErrorDetail] = []
    if campus_changed and not await _campus_available(db, who, campus_id):
        problems.append(CAMPUS_NOT_AVAILABLE)
    elif owner_id is not None and not await owner_eligible(db, who.tenant_id, owner_id, campus_id):
        problems.append(OWNER_NOT_ELIGIBLE)
    if problems:
        raise _invalid(*problems)
    authorize(who.context, LEAD_ASSIGN, LeadResource(who.tenant_id, campus_id))
    previous_owner, previous_campus = lead.owner_membership_id, lead.campus_id
    lead.owner_membership_id, lead.campus_id = owner_id, campus_id
    await db.flush()
    await record_activity(
        db,
        ACTIVITIES,
        subject_column="lead_id",
        subject_id=lead.id,
        kind=ActivityKind.ASSIGNED.value,
        actor_membership_id=who.membership_id,
        details={
            "owner_from": previous_owner,
            "owner_to": owner_id,
            "campus_from": previous_campus,
            "campus_to": campus_id,
        },
    )
    await write_audit_event(
        db,
        events.LEAD_ASSIGNED,
        target=AuditTarget("lead", lead.id),
        metadata={"owner_changed": owner_changed, "campus_changed": campus_changed},
    )
    return await _detail_row(db, who, lead.id)
