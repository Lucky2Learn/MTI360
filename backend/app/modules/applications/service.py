"""Applications: create, edit, submit, review and admit (Phase 02-2; ADR-0021 §2-§7, §10-§12).

Authorization (D-B1): every application permission is campus-scoped and an
application always has a campus (L6). An application outside the caller's
campuses is **not found** (404); lists use the same rule as a SQL predicate.

Every mutation checks the optimistic ``version`` (409 when stale), records an
``application_activities`` row and a ``domain`` audit event in the same
transaction. Review and admission lock the application row, so concurrent
decisions serialise and the loser sees the new version (409). Audit metadata
carries statuses, field names and booleans only.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from typing import Any, cast

from sqlalchemy import Table, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.activity import record_activity
from app.core.audit import AuditTarget, write_audit_event
from app.core.authz import Permission, authorize, campus_visible
from app.core.errors import ConflictError, ErrorDetail, NotFoundError, ValidationFailedError
from app.core.pagination import PageParams, SortField
from app.modules.applications import events
from app.modules.applications import repository as repo
from app.modules.applications.domain import (
    ADDRESS_MAX_LENGTH,
    CITY_MAX_LENGTH,
    DETAIL_FIELDS,
    EDITABLE,
    INITIAL_STATUS,
    LEAD_PREFILL,
    QUALIFICATION_MAX_LENGTH,
    REASON_MAX_LENGTH,
    REASON_REQUIRED,
    STATE_MAX_LENGTH,
    TEXT_MAX_LENGTH,
    ActivityKind,
    ApplicationStatus,
    ReviewProblem,
    birth_date_plausible,
    clean_cdc,
    clean_indos,
    clean_postal_code,
    missing_for_submit,
    review_problem,
)
from app.modules.applications.models import Application, ApplicationActivity
from app.modules.applications.permissions import (
    APPLICATION_CREATE,
    APPLICATION_READ,
    APPLICATION_REVIEW,
    APPLICATION_UPDATE,
)
from app.modules.courses.domain import CourseStatus
from app.modules.documents import repository as documents
from app.modules.leads import follow_ups
from app.modules.leads import repository as leads_repo
from app.modules.leads import service as leads
from app.modules.leads.domain import (
    CLOSED_STATUSES,
    clean_email,
    clean_mobile,
    clean_name,
    clean_optional,
    clean_text,
    mobile_key,
)
from app.modules.leads.service import Caller, caller
from app.modules.students import repository as students_repo
from app.modules.students import service as students
from app.modules.students.domain import SequenceName, StudentChoice
from app.modules.students.events import ADMISSION_APPROVED
from app.modules.students.models import Admission
from app.modules.students.permissions import ADMISSION_APPROVE
from app.modules.students.sequences import next_number

ACTIVITIES = cast(Table, ApplicationActivity.__table__)
STALE = "This application was changed by someone else. Reload and try again."
PATCH_FIELDS = (*DETAIL_FIELDS, "course_id", "campus_id")


@dataclass(frozen=True, slots=True)
class ApplicationResource:
    """An application as an authorization resource: its (required) campus."""

    tenant_id: uuid.UUID
    campus_id: uuid.UUID | None


def _detail(field: str, code: str, message: str) -> ErrorDetail:
    return ErrorDetail(field=field, code=code, message=message)


def _invalid(*details: ErrorDetail) -> ValidationFailedError:
    return ValidationFailedError(details=list(details))


COURSE_NOT_ACTIVE = _detail("course_id", "course_not_active", "Choose an active course.")
CAMPUS_NOT_AVAILABLE = _detail("campus_id", "campus_not_available", "Choose one of your campuses.")
LEAD_NOT_AVAILABLE = _detail("lead_id", "lead_not_available", "Choose a lead you can see.")
LEAD_CLOSED = _detail("lead_id", "lead_closed", "Reopen this lead before starting an application.")
APPLICATION_EXISTS = _detail(
    "course_id", "application_exists", "This lead already has an application for this course."
)
NOT_EDITABLE = _detail(
    "status", "application_locked", "Only drafts and applications returned for correction change."
)
_SUBMIT_MESSAGES = {
    "full_name": "Enter the applicant's name.",
    "date_of_birth": "Enter the date of birth.",
    "highest_qualification": "Enter the highest qualification.",
    "contact": "Enter a mobile number or an email.",
    "declaration": "Confirm the applicant's declaration.",
}
_REVIEW_MESSAGES = {
    ReviewProblem.INVALID: ("to_status", "This application cannot move to that status."),
    ReviewProblem.REASON_REQUIRED: ("reason", "Enter a reason."),
    ReviewProblem.DOCUMENTS_PENDING: (
        "documents",
        "Verify every document before approving the application.",
    ),
}


async def authorized_application(
    db: AsyncSession,
    who: Caller,
    application_id: uuid.UUID,
    permission: Permission,
    *,
    lock: bool = False,
) -> Application:
    """The application, if it exists in the tenant and its campus is the caller's (404)."""
    found = await repo.application(db, who.tenant_id, application_id, lock=lock)
    if found is None:
        raise NotFoundError()
    authorize(who.context, permission, ApplicationResource(found.tenant_id, found.campus_id))
    return found


def _today() -> date:
    return datetime.now(UTC).date()


def _clean(
    values: Mapping[str, Any], field: str, cleaner: Any, problems: list[ErrorDetail], message: str
) -> Any:
    try:
        return cleaner(values[field])
    except ValueError:
        problems.append(_detail(field, "invalid", message))
        return None


def details(values: Mapping[str, Any], today: date) -> tuple[dict[str, Any], list[ErrorDetail]]:
    """Clean the provided applicant details; contact fields also set their match keys."""
    cleaned: dict[str, Any] = {}
    problems: list[ErrorDetail] = []
    if "full_name" in values:
        cleaned["full_name"] = clean_name(values["full_name"] or "")
        if cleaned["full_name"] is None:
            problems.append(_detail("full_name", "required", "Enter the applicant's name."))
    if "date_of_birth" in values:
        if not birth_date_plausible(values["date_of_birth"], today):
            problems.append(_detail("date_of_birth", "invalid", "Enter a date in the past."))
        cleaned["date_of_birth"] = values["date_of_birth"]
    if "mobile" in values:
        mobile = _clean(values, "mobile", clean_mobile, problems, "Enter a valid mobile number.")
        cleaned["mobile"], cleaned["mobile_key"] = mobile, mobile_key(mobile)
    if "email" in values:
        email = _clean(values, "email", clean_email, problems, "Enter a valid email address.")
        cleaned["email"] = email[0] if email else None
        cleaned["email_normalized"] = email[1] if email else None
    for field, limit in (
        ("city", CITY_MAX_LENGTH),
        ("state", STATE_MAX_LENGTH),
        ("highest_qualification", QUALIFICATION_MAX_LENGTH),
    ):
        if field in values:
            cleaned[field] = _clean(
                values,
                field,
                lambda raw, limit=limit: clean_optional(raw, limit),
                problems,
                f"Use at most {limit} characters.",
            )
    for field, limit in (
        ("address", ADDRESS_MAX_LENGTH),
        ("education_details", TEXT_MAX_LENGTH),
        ("eligibility_notes", TEXT_MAX_LENGTH),
    ):
        if field in values:
            cleaned[field] = _clean(
                values,
                field,
                lambda raw, limit=limit: clean_text(raw, limit),
                problems,
                f"Use at most {limit} characters.",
            )
    for field, cleaner, message in (
        ("postal_code", clean_postal_code, "Enter a valid postal code."),
        ("indos_number", clean_indos, "Enter the INDoS number: 6-16 letters and digits."),
        ("cdc_number", clean_cdc, "Enter the CDC number: letters, digits, / and -."),
    ):
        if field in values:
            cleaned[field] = _clean(values, field, cleaner, problems, message)
    return cleaned, problems


async def _campus_available(db: AsyncSession, who: Caller, campus_id: uuid.UUID) -> bool:
    return campus_visible(campus_id, who.context) and await leads_repo.campus_exists(
        db, who.tenant_id, campus_id
    )


async def _course_active(db: AsyncSession, who: Caller, course_id: uuid.UUID) -> bool:
    status = await leads_repo.course_status(db, who.tenant_id, course_id)
    return status == CourseStatus.ACTIVE.value


async def _activity(
    db: AsyncSession,
    who: Caller,
    application_id: uuid.UUID,
    kind: ActivityKind,
    details: Mapping[str, object] | None = None,
) -> uuid.UUID:
    return await record_activity(
        db,
        ACTIVITIES,
        subject_column="application_id",
        subject_id=application_id,
        kind=kind.value,
        actor_membership_id=who.membership_id,
        details=details,
    )


async def detail_row(
    db: AsyncSession, who: Caller, application_id: uuid.UUID
) -> repo.ApplicationDetailRow:
    row = await repo.application_detail(db, who.tenant_id, application_id)
    if row is None:
        raise NotFoundError()
    return row


# --- Reads ---------------------------------------------------------------------------------


async def list_applications(
    db: AsyncSession,
    filters: repo.ApplicationFilters,
    page: PageParams,
    sort: tuple[SortField, ...],
    *,
    mine: bool = False,
) -> tuple[list[repo.ApplicationListRow], int]:
    who = await caller(db, APPLICATION_READ)
    if mine:
        filters = replace(filters, owner=who.membership_id)
    return await repo.search_applications(db, who.tenant_id, who.context, filters, page, sort)


async def get_application(
    db: AsyncSession, application_id: uuid.UUID
) -> tuple[repo.ApplicationDetailRow, Caller]:
    who = await caller(db, APPLICATION_READ)
    await authorized_application(db, who, application_id, APPLICATION_READ)
    return await detail_row(db, who, application_id), who


async def list_activity(
    db: AsyncSession, application_id: uuid.UUID, page: PageParams
) -> tuple[list[follow_ups.ActivityView], int]:
    who = await caller(db, APPLICATION_READ)
    await authorized_application(db, who, application_id, APPLICATION_READ)
    items, total = await repo.activities_of(db, who.tenant_id, application_id, page)
    return await follow_ups.activity_views(db, who, items), total


async def student_candidates(
    db: AsyncSession, application_id: uuid.UUID
) -> list[students_repo.CandidateRow]:
    """Students the approver may link at admission (``admission.approve``; never auto-linked)."""
    who = await caller(db, ADMISSION_APPROVE)
    application = await authorized_application(db, who, application_id, ADMISSION_APPROVE)
    return await students.candidates_for(db, who, application)


# --- Commands ------------------------------------------------------------------------------


async def create_application(
    db: AsyncSession,
    *,
    lead_id: uuid.UUID | None,
    course_id: uuid.UUID,
    campus_id: uuid.UUID,
    values: Mapping[str, Any],
) -> repo.ApplicationDetailRow:
    """A ``DRAFT`` for ``course_id`` at ``campus_id``, from a lead (its details prefill the
    fields the request leaves out) or direct. Starts the lead's ``APPLICATION`` stage."""
    who = await caller(db, APPLICATION_CREATE)
    problems: list[ErrorDetail] = []
    provided = {field: values[field] for field in DETAIL_FIELDS if field in values}
    lead = None
    if lead_id is not None:
        lead = await leads_repo.lead(db, who.tenant_id, lead_id)
        if lead is None or not campus_visible(lead.campus_id, who.context):
            problems.append(LEAD_NOT_AVAILABLE)
            lead = None
        elif lead.status in {status.value for status in CLOSED_STATUSES}:
            problems.append(LEAD_CLOSED)
        else:
            for field in LEAD_PREFILL:
                provided.setdefault(field, getattr(lead, field))
    if "full_name" not in provided:
        provided["full_name"] = None
    cleaned, detail_problems = details(provided, _today())
    problems.extend(detail_problems)
    if not await _course_active(db, who, course_id):
        problems.append(COURSE_NOT_ACTIVE)
    elif lead is not None and await repo.open_application_for(
        db, who.tenant_id, lead.id, course_id
    ):
        problems.append(APPLICATION_EXISTS)
    if not await _campus_available(db, who, campus_id):
        problems.append(CAMPUS_NOT_AVAILABLE)
    if problems:
        raise _invalid(*problems)
    authorize(who.context, APPLICATION_CREATE, ApplicationResource(who.tenant_id, campus_id))
    application = Application(
        tenant_id=who.tenant_id,
        number=await next_number(db, SequenceName.APPLICATION),
        lead_id=lead.id if lead else None,
        course_id=course_id,
        campus_id=campus_id,
        owner_membership_id=(lead.owner_membership_id if lead else None) or who.membership_id,
        created_by_membership_id=who.membership_id,
        status=INITIAL_STATUS.value,
        **cleaned,
    )
    db.add(application)
    await db.flush()
    await _activity(
        db,
        who,
        application.id,
        ActivityKind.CREATED,
        {"from_lead": lead is not None, "course_id": course_id, "campus_id": campus_id},
    )
    await write_audit_event(
        db,
        events.APPLICATION_CREATED,
        target=AuditTarget("application", application.id),
        metadata={"from_lead": lead is not None},
    )
    if lead is not None:
        await leads.mark_application_started(
            db,
            lead.id,
            actor_membership_id=who.membership_id,
            application_id=application.id,
            application_number=application.number,
        )
    return await detail_row(db, who, application.id)


async def update_application(
    db: AsyncSession,
    application_id: uuid.UUID,
    *,
    changes: Mapping[str, Any],
    declaration: bool | None,
    version: int,
) -> repo.ApplicationDetailRow:
    """Edit details, course, campus or the declaration while ``DRAFT``/``CORRECTION_REQUIRED``."""
    who = await caller(db, APPLICATION_UPDATE)
    application = await authorized_application(db, who, application_id, APPLICATION_UPDATE)
    if application.version != version:
        raise ConflictError(STALE)
    if ApplicationStatus(application.status) not in EDITABLE:
        raise _invalid(NOT_EDITABLE)
    cleaned, problems = details(changes, _today())
    course_id = changes.get("course_id")
    if (
        course_id is not None
        and course_id != application.course_id
        and not await _course_active(db, who, course_id)
    ):
        problems.append(COURSE_NOT_ACTIVE)
    campus_id = changes.get("campus_id")
    if (
        campus_id is not None
        and campus_id != application.campus_id
        and not await _campus_available(db, who, campus_id)
    ):
        problems.append(CAMPUS_NOT_AVAILABLE)
    if problems:
        raise _invalid(*problems)
    if course_id is not None:
        cleaned["course_id"] = course_id
    if campus_id is not None:
        authorize(who.context, APPLICATION_UPDATE, ApplicationResource(who.tenant_id, campus_id))
        cleaned["campus_id"] = campus_id
    changed = sorted(
        field
        for field in PATCH_FIELDS
        if field in cleaned and getattr(application, field) != cleaned[field]
    )
    declared = application.declared_at is not None
    if declaration is not None and declaration != declared:
        changed.append("declaration")
        application.declared_at = func.now() if declaration else None
        application.declared_by_membership_id = who.membership_id if declaration else None
    if not changed:
        return await detail_row(db, who, application.id)
    for field, value in cleaned.items():
        setattr(application, field, value)
    await db.flush()
    await _activity(db, who, application.id, ActivityKind.UPDATED, {"fields": changed})
    await write_audit_event(
        db,
        events.APPLICATION_UPDATED,
        target=AuditTarget("application", application.id),
        metadata={"changed_fields": changed},
    )
    return await detail_row(db, who, application.id)


async def submit(
    db: AsyncSession, application_id: uuid.UUID, *, version: int
) -> repo.ApplicationDetailRow:
    """``DRAFT``/``CORRECTION_REQUIRED`` → ``SUBMITTED``; its uploaded documents enter review."""
    who = await caller(db, APPLICATION_UPDATE)
    application = await authorized_application(
        db, who, application_id, APPLICATION_UPDATE, lock=True
    )
    if application.version != version:
        raise ConflictError(STALE)
    previous = ApplicationStatus(application.status)
    if previous not in EDITABLE:
        raise _invalid(_detail("status", "invalid_transition", "This application is submitted."))
    values = {field: getattr(application, field) for field in DETAIL_FIELDS}
    missing = missing_for_submit(values, declared=application.declared_at is not None)
    problems = [_detail(field, "required_for_submit", _SUBMIT_MESSAGES[field]) for field in missing]
    if not await _course_active(db, who, application.course_id):
        problems.append(COURSE_NOT_ACTIVE)
    if problems:
        raise _invalid(*problems)
    application.status = ApplicationStatus.SUBMITTED.value
    application.status_reason = None
    application.status_changed_at = func.now()
    application.submitted_at = func.now()
    await db.flush()
    promoted = await documents.promote_uploaded(db, who.tenant_id, application.id)
    await _activity(
        db,
        who,
        application.id,
        ActivityKind.SUBMITTED,
        {"from": previous.value, "documents_for_review": promoted},
    )
    await write_audit_event(
        db,
        events.APPLICATION_SUBMITTED,
        target=AuditTarget("application", application.id),
        metadata={"resubmission": previous is ApplicationStatus.CORRECTION_REQUIRED},
    )
    return await detail_row(db, who, application.id)


async def review(
    db: AsyncSession,
    application_id: uuid.UUID,
    *,
    target: ApplicationStatus,
    reason: str | None,
    version: int,
) -> repo.ApplicationDetailRow:
    """A reviewer's move (``REVIEW_TRANSITIONS``): start review, approve, request
    correction, reject or not eligible. Approval needs every current document verified."""
    who = await caller(db, APPLICATION_REVIEW)
    application = await authorized_application(
        db, who, application_id, APPLICATION_REVIEW, lock=True
    )
    if application.version != version:
        raise ConflictError(STALE)
    try:
        clean_reason = clean_text(reason, REASON_MAX_LENGTH)
    except ValueError:
        raise _invalid(_detail("reason", "too_long", "Use at most 500 characters.")) from None
    current = ApplicationStatus(application.status)
    unverified = await repo.unverified_count(db, who.tenant_id, application.id)
    problem = review_problem(current, target, reason=clean_reason, unverified_documents=unverified)
    if problem is not None:
        field, message = _REVIEW_MESSAGES[problem]
        raise _invalid(_detail(field, problem.value, message))
    kept_reason = clean_reason if target in REASON_REQUIRED else None
    application.status = target.value
    application.status_reason = kept_reason
    application.status_changed_at = func.now()
    application.reviewed_at = func.now()
    application.reviewed_by_membership_id = who.membership_id
    await db.flush()
    activity: dict[str, object] = {"from": current.value, "to": target.value}
    if kept_reason:
        activity["reason"] = kept_reason
    await _activity(db, who, application.id, ActivityKind.STATUS_CHANGED, activity)
    await write_audit_event(
        db,
        events.APPLICATION_STATUS_CHANGED,
        target=AuditTarget("application", application.id),
        metadata={"from": current.value, "to": target.value, "has_reason": bool(kept_reason)},
    )
    return await detail_row(db, who, application.id)


async def admit(
    db: AsyncSession,
    application_id: uuid.UUID,
    *,
    choice: StudentChoice,
    student_id: uuid.UUID | None,
    version: int,
) -> repo.ApplicationDetailRow:
    """``APPROVED`` → ``ADMITTED``: the admission number, the Admission, and a new or the
    explicitly chosen Student, in one transaction (L3: no payment gate). The row lock and
    ``UNIQUE (tenant_id, application_id)`` make a repeated admit impossible."""
    who = await caller(db, ADMISSION_APPROVE)
    application = await authorized_application(
        db, who, application_id, ADMISSION_APPROVE, lock=True
    )
    if application.version != version:
        raise ConflictError(STALE)
    if application.status != ApplicationStatus.APPROVED.value:
        raise _invalid(
            _detail("status", "invalid_transition", "Approve the application before admission.")
        )
    student, created = await students.resolve_student(
        db, who, application, choice=choice, student_id=student_id
    )
    admission = Admission(
        tenant_id=who.tenant_id,
        admission_number=await next_number(db, SequenceName.ADMISSION),
        application_id=application.id,
        student_id=student.id,
        course_id=application.course_id,
        campus_id=application.campus_id,
        approved_by_membership_id=who.membership_id,
    )
    db.add(admission)
    try:
        await db.flush()
    except IntegrityError:  # pragma: no cover - the row lock makes this a backstop only
        raise ConflictError(STALE) from None
    application.status = ApplicationStatus.ADMITTED.value
    application.status_reason = None
    application.status_changed_at = func.now()
    await db.flush()
    await _activity(
        db,
        who,
        application.id,
        ActivityKind.ADMITTED,
        {
            "admission_number": admission.admission_number,
            "student_number": student.student_number,
            "student_created": created,
        },
    )
    await write_audit_event(
        db,
        ADMISSION_APPROVED,
        target=AuditTarget("admission", admission.id),
        metadata={"student_created": created},
    )
    if application.lead_id is not None:
        await leads.mark_admitted(db, application.lead_id, actor_membership_id=who.membership_id)
    return await detail_row(db, who, application.id)
