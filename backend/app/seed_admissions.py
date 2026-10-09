"""Development seed: courses, leads, follow-ups and notes (Phase 02-1; blueprint §26).

Part of ``app.seed`` (T01-08, D16): development only, realistic maritime
fixtures, fictitious contact details (``.example`` emails, the ``90000 10xxx``
mobile range). Rows are inserted as the system realm with the institute as
the trusted tenant, through the same tables, keys and CHECKs as the API, and
each lead gets the timeline the API would have written (created, status,
follow-ups, notes). No audit events besides the seed's own: the seed is not
a member's action.

Leads reference courses and campuses by code and members by their seed
email. A ``DUPLICATE`` lead names an earlier lead by ``key``.
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Final, cast

from sqlalchemy import Table, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.activity import record_activity
from app.modules.courses.domain import (
    CourseCategory,
    CourseStatus,
    DurationUnit,
    duration_valid,
    normalize_code,
)
from app.modules.courses.models import Course
from app.modules.leads.domain import (
    CLOSED_STATUSES,
    OPEN_STATUSES,
    REASON_REQUIRED,
    ActivityKind,
    FollowUpKind,
    LeadSource,
    LeadStatus,
    clean_email,
    clean_mobile,
    mobile_key,
)
from app.modules.leads.models import Lead, LeadActivity, LeadFollowUp

COURSES = cast(Table, Course.__table__)
LEADS = cast(Table, Lead.__table__)
FOLLOW_UPS = cast(Table, LeadFollowUp.__table__)
ACTIVITIES = cast(Table, LeadActivity.__table__)
SEEDABLE_STATUSES: Final = OPEN_STATUSES | CLOSED_STATUSES
FICTITIOUS_MOBILE_PREFIX: Final = "9000010"


class AdmissionsSeedError(ValueError):
    """An invalid courses/leads section (``app.seed`` reports it as a SeedError)."""


@dataclass(frozen=True, slots=True)
class SeedCourse:
    code: str
    name: str
    category: CourseCategory
    status: CourseStatus
    duration_value: int | None
    duration_unit: DurationUnit | None
    eligibility_summary: str | None
    description: str | None


@dataclass(frozen=True, slots=True)
class SeedFollowUp:
    due_in_hours: int
    kind: FollowUpKind
    note: str | None


@dataclass(frozen=True, slots=True)
class SeedLead:
    key: str
    full_name: str
    mobile: str | None
    email: str | None
    source: LeadSource
    course: str | None
    campus: str | None
    owner: str | None
    created_by: str
    status: LeadStatus
    status_reason: str | None
    duplicate_of: str | None
    date_of_birth: date | None
    city: str | None
    qualification: str | None
    follow_ups: tuple[SeedFollowUp, ...]
    notes: tuple[str, ...]


def _text(raw: Mapping[str, Any], key: str, where: str, *, required: bool = True) -> str | None:
    value = raw.get(key)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AdmissionsSeedError(f"{where}.{key}: a non-empty string is required")
    return " ".join(value.split())


def _enum[E](kind: type[E], value: Any, where: str) -> E:
    try:
        return kind(value)  # type: ignore[call-arg]
    except ValueError:
        raise AdmissionsSeedError(f"{where}: unknown value") from None


def parse_courses(raw: Sequence[Mapping[str, Any]], where: str) -> tuple[SeedCourse, ...]:
    courses: list[SeedCourse] = []
    for index, item in enumerate(raw):
        at = f"{where}.courses[{index}]"
        code = normalize_code(_text(item, "code", at) or "")
        if code is None:
            raise AdmissionsSeedError(f"{at}.code: invalid course code")
        value = item.get("duration_value")
        unit_raw = item.get("duration_unit")
        unit = _enum(DurationUnit, unit_raw, f"{at}.duration_unit") if unit_raw else None
        if not duration_valid(value, unit):
            raise AdmissionsSeedError(f"{at}: duration value and unit go together")
        courses.append(
            SeedCourse(
                code=code,
                name=_text(item, "name", at) or "",
                category=_enum(CourseCategory, item.get("category"), f"{at}.category"),
                status=_enum(CourseStatus, item.get("status", "DRAFT"), f"{at}.status"),
                duration_value=value,
                duration_unit=unit,
                eligibility_summary=_text(item, "eligibility_summary", at, required=False),
                description=_text(item, "description", at, required=False),
            )
        )
    if len({c.code for c in courses}) != len(courses):
        raise AdmissionsSeedError(f"{where}.courses: codes must be unique")
    return tuple(courses)


def _contact(item: Mapping[str, Any], at: str) -> tuple[str | None, str | None]:
    try:
        mobile = clean_mobile(item.get("mobile"))
        email = clean_email(item.get("email"))
    except ValueError:
        raise AdmissionsSeedError(f"{at}: invalid mobile or email") from None
    if mobile is None and email is None:
        raise AdmissionsSeedError(f"{at}: a mobile or an email is required")
    if mobile and not (mobile_key(mobile) or "").startswith(FICTITIOUS_MOBILE_PREFIX):
        raise AdmissionsSeedError(f"{at}.mobile: use the fictitious 90000 10xxx range")
    if email and not email[1].rsplit("@", 1)[1].endswith("example.com"):
        raise AdmissionsSeedError(f"{at}.email: development emails must use example.com")
    return mobile, email[0] if email else None


def parse_leads(
    raw: Sequence[Mapping[str, Any]],
    where: str,
    *,
    courses: set[str],
    campuses: set[str],
    members: set[str],
) -> tuple[SeedLead, ...]:
    leads: list[SeedLead] = []
    keys: dict[str, LeadStatus] = {}
    for index, item in enumerate(raw):
        at = f"{where}.leads[{index}]"
        key = _text(item, "key", at) or ""
        if key in keys:
            raise AdmissionsSeedError(f"{at}.key: duplicate key")
        mobile, email = _contact(item, at)
        status = _enum(LeadStatus, item.get("status", "NEW"), f"{at}.status")
        if status not in SEEDABLE_STATUSES:
            raise AdmissionsSeedError(f"{at}.status: APPLICATION and ADMITTED come from 02-2")
        reason = _text(item, "status_reason", at, required=False)
        if status in REASON_REQUIRED and reason is None:
            raise AdmissionsSeedError(f"{at}.status_reason: required for this status")
        duplicate_of = _text(item, "duplicate_of", at, required=False)
        if (status is LeadStatus.DUPLICATE) != (duplicate_of is not None):
            raise AdmissionsSeedError(f"{at}.duplicate_of: required for DUPLICATE only")
        if duplicate_of is not None and keys.get(duplicate_of) in (None, LeadStatus.DUPLICATE):
            raise AdmissionsSeedError(f"{at}.duplicate_of: an earlier, non-duplicate lead")
        course = _text(item, "course", at, required=False)
        campus = _text(item, "campus", at, required=False)
        owner = _text(item, "owner", at, required=False)
        created_by = _text(item, "created_by", at) or ""
        if course is not None and course not in courses:
            raise AdmissionsSeedError(f"{at}.course: unknown course code")
        if campus is not None and campus not in campuses:
            raise AdmissionsSeedError(f"{at}.campus: unknown campus code")
        if (owner is not None and owner not in members) or created_by not in members:
            raise AdmissionsSeedError(f"{at}: owner and created_by must be seed members")
        birth = item.get("date_of_birth")
        follow_ups = tuple(
            SeedFollowUp(
                due_in_hours=int(f["due_in_hours"]),
                kind=_enum(FollowUpKind, f.get("kind"), f"{at}.follow_ups.kind"),
                note=_text(f, "note", f"{at}.follow_ups", required=False),
            )
            for f in item.get("follow_ups", ())
        )
        leads.append(
            SeedLead(
                key=key,
                full_name=_text(item, "full_name", at) or "",
                mobile=mobile,
                email=email,
                source=_enum(LeadSource, item.get("source"), f"{at}.source"),
                course=course,
                campus=campus,
                owner=owner,
                created_by=created_by,
                status=status,
                status_reason=reason,
                duplicate_of=duplicate_of,
                date_of_birth=date.fromisoformat(birth) if birth else None,
                city=_text(item, "city", at, required=False),
                qualification=_text(item, "highest_qualification", at, required=False),
                follow_ups=follow_ups,
                notes=tuple(str(note) for note in item.get("notes", ())),
            )
        )
        keys[key] = status
    return tuple(leads)


async def _activity(
    db: AsyncSession,
    lead_id: uuid.UUID,
    kind: ActivityKind,
    actor: uuid.UUID,
    details: Mapping[str, object] | None = None,
    body: str | None = None,
) -> None:
    await record_activity(
        db,
        ACTIVITIES,
        subject_column="lead_id",
        subject_id=lead_id,
        kind=kind.value,
        actor_membership_id=actor,
        details=details,
        body=body,
    )


async def seed_admissions(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    courses: Sequence[SeedCourse],
    leads: Sequence[SeedLead],
    campus_ids: Mapping[str, uuid.UUID],
    memberships: Mapping[str, uuid.UUID],
) -> tuple[dict[str, uuid.UUID], dict[str, uuid.UUID]]:
    """Insert one institute's courses and leads (system realm, trusted tenant).

    Returns the course IDs by code and the lead IDs by key (Phase 02-2 applications)."""
    course_ids: dict[str, uuid.UUID] = {}
    for course in courses:
        course_ids[course.code] = uuid.uuid7()
        await db.execute(
            insert(COURSES).values(
                id=course_ids[course.code],
                tenant_id=tenant_id,
                code=course.code,
                name=course.name,
                category=course.category.value,
                status=course.status.value,
                duration_value=course.duration_value,
                duration_unit=course.duration_unit.value if course.duration_unit else None,
                eligibility_summary=course.eligibility_summary,
                description=course.description,
                version=1,
            )
        )
    lead_ids: dict[str, uuid.UUID] = {}
    now = datetime.now(UTC)
    for lead in leads:
        lead_id = lead_ids[lead.key] = uuid.uuid7()
        creator = memberships[lead.created_by]
        email = clean_email(lead.email)
        await db.execute(
            insert(LEADS).values(
                id=lead_id,
                tenant_id=tenant_id,
                full_name=lead.full_name,
                mobile=lead.mobile,
                mobile_key=mobile_key(lead.mobile),
                email=lead.email,
                email_normalized=email[1] if email else None,
                source=lead.source.value,
                interested_course_id=course_ids[lead.course] if lead.course else None,
                campus_id=campus_ids[lead.campus] if lead.campus else None,
                owner_membership_id=memberships[lead.owner] if lead.owner else None,
                status=lead.status.value,
                status_reason=lead.status_reason,
                duplicate_of_lead_id=lead_ids[lead.duplicate_of] if lead.duplicate_of else None,
                created_by_membership_id=creator,
                date_of_birth=lead.date_of_birth,
                city=lead.city,
                highest_qualification=lead.qualification,
                version=1,
            )
        )
        await _activity(
            db,
            lead_id,
            ActivityKind.CREATED,
            creator,
            {"source": lead.source.value, "possible_duplicates": 0},
        )
        if lead.status is not LeadStatus.NEW:
            details: dict[str, object] = {"from": "NEW", "to": lead.status.value}
            if lead.status_reason:
                details["reason"] = lead.status_reason
            if lead.duplicate_of:
                details["duplicate_of"] = lead_ids[lead.duplicate_of]
            await _activity(db, lead_id, ActivityKind.STATUS_CHANGED, creator, details)
        for follow_up in lead.follow_ups:
            follow_up_id = uuid.uuid7()
            due_at = now + timedelta(hours=follow_up.due_in_hours)
            assignee = memberships[lead.owner] if lead.owner else creator
            await db.execute(
                insert(FOLLOW_UPS).values(
                    id=follow_up_id,
                    tenant_id=tenant_id,
                    lead_id=lead_id,
                    assignee_membership_id=assignee,
                    due_at=due_at,
                    kind=follow_up.kind.value,
                    note=follow_up.note,
                    created_by_membership_id=creator,
                    version=1,
                )
            )
            await _activity(
                db,
                lead_id,
                ActivityKind.FOLLOW_UP_SCHEDULED,
                creator,
                {
                    "follow_up_id": follow_up_id,
                    "follow_up_kind": follow_up.kind.value,
                    "due_at": due_at.isoformat(),
                },
            )
        for note in lead.notes:
            await _activity(db, lead_id, ActivityKind.NOTE, creator, body=note)
    return course_ids, lead_ids
