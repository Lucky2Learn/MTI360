"""The course catalogue (Phase 02-1; blueprint §4-§6, ADR-0020 §1-§2).

Courses are institute-wide: a course is an authorization resource **without
a campus**, so the T01 rules apply unchanged (D-B1):

* ``course.read`` (campus-scoped) admits campus-restricted members, because
  ``authorize()`` lets a campus permission reach a resource with no campus;
* ``course.manage`` (tenant-scoped) needs all-campus access.

The code is immutable after creation; there is no delete (archive instead).
Every change checks the optimistic ``version`` and writes a ``domain`` audit
event in the request transaction (code, field names and statuses only).
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditTarget, write_audit_event
from app.core.authz import Permission, authorize
from app.core.context import RequestContext, current_context
from app.core.errors import ConflictError, ErrorDetail, NotFoundError, ValidationFailedError
from app.core.pagination import PageParams, SortField
from app.modules.courses import events
from app.modules.courses.domain import (
    COURSE_TRANSITIONS,
    INITIAL_STATUS,
    TEXT_MAX_LENGTH,
    CourseCategory,
    CourseStatus,
    DurationUnit,
    clean_name,
    clean_text,
    duration_valid,
    normalize_code,
)
from app.modules.courses.models import Course
from app.modules.courses.permissions import COURSE_MANAGE, COURSE_READ
from app.modules.courses.repository import CourseFilters, CourseRepository

CODE_TAKEN = "A course with this code already exists."
STALE = "This course was changed by someone else. Reload and try again."
EDITABLE_FIELDS = (
    "name",
    "category",
    "description",
    "eligibility_summary",
    "duration_value",
    "duration_unit",
)


@dataclass(frozen=True, slots=True)
class CourseResource:
    """A course as an authorization resource: institute-wide, so no campus."""

    tenant_id: uuid.UUID
    campus_id: uuid.UUID | None = None


def _detail(field: str, code: str, message: str) -> ErrorDetail:
    return ErrorDetail(field=field, code=code, message=message)


def _invalid(*details: ErrorDetail) -> ValidationFailedError:
    return ValidationFailedError(details=list(details))


def _clean(values: Mapping[str, Any]) -> tuple[dict[str, Any], list[ErrorDetail]]:
    """Validated course fields (only those present in ``values``) and the problems found."""
    cleaned: dict[str, Any] = {}
    problems: list[ErrorDetail] = []
    if "name" in values:
        name = clean_name(values["name"] or "")
        if name is None:
            problems.append(_detail("name", "invalid", "Enter a name of up to 200 characters."))
        cleaned["name"] = name
    if "category" in values:
        if values["category"] is None:
            problems.append(_detail("category", "required", "Choose a category."))
        else:
            cleaned["category"] = CourseCategory(values["category"]).value
    for field in ("description", "eligibility_summary"):
        if field in values:
            text = clean_text(values[field])
            if text is not None and len(text) > TEXT_MAX_LENGTH:
                problems.append(_detail(field, "too_long", "Use at most 2000 characters."))
            cleaned[field] = text
    if "duration_value" in values or "duration_unit" in values:
        unit = values.get("duration_unit")
        cleaned["duration_value"] = values.get("duration_value")
        cleaned["duration_unit"] = DurationUnit(unit).value if unit is not None else None
    return cleaned, problems


def _duration_problem(value: int | None, unit: str | None) -> ErrorDetail | None:
    if duration_valid(value, DurationUnit(unit) if unit else None):
        return None
    return _detail(
        "duration_value",
        "duration_pair",
        "Enter a duration from 1 to 1000 with its unit, or leave both empty.",
    )


async def _course(
    db: AsyncSession, context: RequestContext, course_id: uuid.UUID, permission: Permission
) -> Course:
    found = await CourseRepository(db).find(course_id)
    if found is None:
        raise NotFoundError()
    authorize(context, permission, CourseResource(found.tenant_id))
    return found


async def list_courses(
    db: AsyncSession, filters: CourseFilters, page: PageParams, sort: Sequence[SortField]
) -> tuple[list[Course], int]:
    authorize(current_context(), COURSE_READ)
    return await CourseRepository(db).search(filters, page, sort)


async def get_course(db: AsyncSession, course_id: uuid.UUID) -> Course:
    context = current_context()
    authorize(context, COURSE_READ)
    return await _course(db, context, course_id, COURSE_READ)


async def create_course(db: AsyncSession, *, code: str, values: Mapping[str, Any]) -> Course:
    """A new ``DRAFT`` course. ``values`` holds the editable fields."""
    context = current_context()
    authorize(context, COURSE_MANAGE)
    clean_code = normalize_code(code)
    cleaned, problems = _clean({field: values.get(field) for field in EDITABLE_FIELDS})
    if clean_code is None:
        problems.insert(
            0,
            _detail(
                "code",
                "invalid",
                "Use up to 32 letters, digits or hyphens, starting with a letter or digit.",
            ),
        )
    duration = _duration_problem(cleaned["duration_value"], cleaned["duration_unit"])
    if duration is not None:
        problems.append(duration)
    if problems or clean_code is None:
        raise _invalid(*problems)
    repository = CourseRepository(db)
    if await repository.code_taken(clean_code):
        raise ConflictError(CODE_TAKEN)
    course = Course(code=clean_code, status=INITIAL_STATUS.value, **cleaned)
    try:
        await repository.add(course)
    except IntegrityError:  # created concurrently
        raise ConflictError(CODE_TAKEN) from None
    await db.refresh(course)
    await write_audit_event(
        db,
        events.COURSE_CREATED,
        target=AuditTarget("course", course.id),
        metadata={"code": clean_code},
    )
    return course


async def update_course(
    db: AsyncSession, course_id: uuid.UUID, *, changes: Mapping[str, Any], version: int
) -> Course:
    """Edit the provided fields (optimistic ``version``). The code never changes."""
    context = current_context()
    authorize(context, COURSE_MANAGE)
    course = await _course(db, context, course_id, COURSE_MANAGE)
    if course.version != version:
        raise ConflictError(STALE)
    cleaned, problems = _clean(changes)
    value = cleaned.get("duration_value", course.duration_value)
    unit = cleaned.get("duration_unit", course.duration_unit)
    duration = _duration_problem(value, unit)
    if duration is not None:
        problems.append(duration)
    if problems:
        raise _invalid(*problems)
    changed = sorted(field for field, new in cleaned.items() if getattr(course, field) != new)
    if not changed:
        return course
    for field in changed:
        setattr(course, field, cleaned[field])
    await db.flush()
    await db.refresh(course)
    await write_audit_event(
        db,
        events.COURSE_UPDATED,
        target=AuditTarget("course", course.id),
        metadata={"changed_fields": changed},
    )
    return course


async def change_status(
    db: AsyncSession, course_id: uuid.UUID, *, status: CourseStatus, version: int
) -> Course:
    """Activate, archive or reactivate (``COURSE_TRANSITIONS``)."""
    context = current_context()
    authorize(context, COURSE_MANAGE)
    course = await _course(db, context, course_id, COURSE_MANAGE)
    if course.version != version:
        raise ConflictError(STALE)
    current = CourseStatus(course.status)
    if not COURSE_TRANSITIONS.allows(current, status):
        raise _invalid(
            _detail("status", "invalid_transition", "This course cannot move to that status.")
        )
    course.status = status.value
    await db.flush()
    await db.refresh(course)
    await write_audit_event(
        db,
        events.COURSE_STATUS_CHANGED,
        target=AuditTarget("course", course.id),
        metadata={"from": current.value, "to": status.value},
    )
    return course
