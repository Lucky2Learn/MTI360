"""Students and admissions (Phase 02-2; ADR-0021 §2, §6, §11).

* A student is an authorization resource of its **home campus** (L6, MVP):
  restricted members read the students of their campuses; anything else is
  not found (404, D-B1). Admissions, documents and timeline entries of the
  student are filtered by their own campuses.
* :func:`resolve_student` is the admission step that creates a student or
  links the one the approver chose explicitly (ADR-0021 Y6). It is called by
  the application service inside the admit transaction, never by a route.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditTarget, write_audit_event
from app.core.authz import authorize, campus_visible
from app.core.errors import ErrorDetail, NotFoundError, ValidationFailedError
from app.core.pagination import PageParams, SortField
from app.modules.applications.models import Application
from app.modules.applications.permissions import APPLICATION_READ
from app.modules.documents.permissions import DOCUMENT_READ
from app.modules.leads import follow_ups
from app.modules.leads.permissions import LEAD_READ
from app.modules.leads.service import Caller, caller
from app.modules.students import events
from app.modules.students import repository as repo
from app.modules.students.domain import SequenceName, StudentChoice, StudentStatus
from app.modules.students.models import Student
from app.modules.students.permissions import STUDENT_READ
from app.modules.students.sequences import next_number


@dataclass(frozen=True, slots=True)
class StudentResource:
    tenant_id: uuid.UUID
    campus_id: uuid.UUID | None


STUDENT_NOT_AVAILABLE = ErrorDetail(
    field="student_id",
    code="student_not_available",
    message="Choose one of the matching students, or create a new student.",
)


async def authorized_student(db: AsyncSession, who: Caller, student_id: uuid.UUID) -> Student:
    found = await repo.student(db, who.tenant_id, student_id)
    if found is None:
        raise NotFoundError()
    authorize(who.context, STUDENT_READ, StudentResource(found.tenant_id, found.home_campus_id))
    return found


async def list_students(
    db: AsyncSession,
    *,
    search: str | None,
    campus: uuid.UUID | None,
    page: PageParams,
    sort: tuple[SortField, ...],
) -> tuple[list[repo.StudentListRow], int]:
    who = await caller(db, STUDENT_READ)
    return await repo.search_students(
        db, who.tenant_id, who.context, search=search, campus=campus, page=page, sort=sort
    )


@dataclass(frozen=True, slots=True)
class StudentProfile:
    detail: repo.StudentDetailRow
    admissions: list[repo.AdmissionRow]


async def get_student(db: AsyncSession, student_id: uuid.UUID) -> StudentProfile:
    who = await caller(db, STUDENT_READ)
    await authorized_student(db, who, student_id)
    detail = await repo.student_detail(db, who.tenant_id, student_id)
    if detail is None:  # pragma: no cover - read in this transaction
        raise NotFoundError()
    admissions = await repo.admissions_of(db, who.tenant_id, who.context, student_id)
    return StudentProfile(detail, admissions)


async def student_documents(
    db: AsyncSession, student_id: uuid.UUID
) -> list[repo.StudentDocumentRow]:
    """``document.read`` on a student the caller may also see (its home campus)."""
    who = await caller(db, DOCUMENT_READ)
    found = await repo.student(db, who.tenant_id, student_id)
    if found is None:
        raise NotFoundError()
    authorize(who.context, DOCUMENT_READ, StudentResource(found.tenant_id, found.home_campus_id))
    return await repo.documents_of(db, who.tenant_id, who.context, student_id)


async def student_activity(
    db: AsyncSession, student_id: uuid.UUID, page: PageParams
) -> tuple[list[follow_ups.ActivityView], dict[uuid.UUID, str], int]:
    """The Student 360 timeline: lead history for ``lead.read`` holders, application history
    for ``application.read`` holders (ADR-0021 §11). Returns views, sources and the total."""
    who = await caller(db, STUDENT_READ)
    await authorized_student(db, who, student_id)
    rows, total = await repo.timeline(
        db,
        who.tenant_id,
        who.context,
        student_id,
        include_leads=LEAD_READ.code in who.context.permissions,
        include_applications=APPLICATION_READ.code in who.context.permissions,
        page=page,
    )
    views = await follow_ups.activity_views(db, who, rows)
    return views, {row.id: row.source for row in rows}, total


async def candidates_for(
    db: AsyncSession, who: Caller, application: Application
) -> list[repo.CandidateRow]:
    """Students the approver may link the application to (same mobile key or email)."""
    return await repo.candidates(
        db,
        who.tenant_id,
        who.context,
        mobile_key=application.mobile_key,
        email_normalized=application.email_normalized,
    )


async def resolve_student(
    db: AsyncSession,
    who: Caller,
    application: Application,
    *,
    choice: StudentChoice,
    student_id: uuid.UUID | None,
) -> tuple[Student, bool]:
    """Create the student from the application, or link the explicitly chosen one.

    An existing student must be one the approver may read (its home campus);
    otherwise the answer is the same as for an unknown ID (422). Returns the
    student and whether it was created."""
    if choice is StudentChoice.EXISTING:
        found = await repo.student(db, who.tenant_id, student_id) if student_id else None
        if found is None or not campus_visible(found.home_campus_id, who.context):
            raise ValidationFailedError(details=[STUDENT_NOT_AVAILABLE])
        return found, False
    student = Student(
        tenant_id=who.tenant_id,
        student_number=await next_number(db, SequenceName.STUDENT),
        home_campus_id=application.campus_id,
        status=StudentStatus.ACTIVE.value,
        full_name=application.full_name,
        date_of_birth=application.date_of_birth,
        mobile=application.mobile,
        mobile_key=application.mobile_key,
        email=application.email,
        email_normalized=application.email_normalized,
        city=application.city,
        created_by_membership_id=who.membership_id,
    )
    db.add(student)
    await db.flush()
    await write_audit_event(
        db,
        events.STUDENT_CREATED,
        target=AuditTarget("student", student.id),
        metadata={"from_application": True},
    )
    return student, True
