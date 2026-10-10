"""Student and admission data access (Phase 02-2; ADR-0021 §2, §6, §11).

The trusted tenant is stated in every statement, added again by the ORM tenant
filter and enforced by Row-Level Security. Campus scope is applied with
:func:`app.core.authz.campus_visibility`: a student by its home campus; its
admissions, documents and activity by their own campuses (the student's
record never discloses another campus's application to a restricted member).
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final

from sqlalchemy import ColumnElement, and_, func, literal, null, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.authz import campus_visibility
from app.core.context import RequestContext
from app.core.pagination import PageParams, SortField
from app.core.search import escape_like
from app.modules.applications.models import Application, ApplicationActivity
from app.modules.courses.models import Course
from app.modules.documents.models import ApplicationDocument, StoredFile
from app.modules.identity.models import TenantMembership, User
from app.modules.institute.models import Campus
from app.modules.leads.models import Lead, LeadActivity
from app.modules.students.domain import STUDENT_CANDIDATE_LIMIT
from app.modules.students.models import Admission, Student

ApproverMembership = aliased(TenantMembership, name="approver_membership")
ApproverUser = aliased(User, name="approver_user")
CreatorMembership = aliased(TenantMembership, name="student_creator_membership")
CreatorUser = aliased(User, name="student_creator_user")
SORTS: Final = ("created_at", "full_name", "student_number")


async def student(db: AsyncSession, tenant_id: uuid.UUID, student_id: uuid.UUID) -> Student | None:
    found: Student | None = await db.scalar(
        select(Student).where(Student.tenant_id == tenant_id, Student.id == student_id)
    )
    return found


@dataclass(frozen=True, slots=True)
class StudentListRow:
    id: uuid.UUID
    student_number: str
    full_name: str
    mobile: str | None
    email: str | None
    status: str
    campus_id: uuid.UUID
    campus_code: str
    admissions: int
    latest_course: str | None
    created_at: datetime


def _admissions_count(tenant_id: uuid.UUID) -> Any:
    return (
        select(func.count())
        .where(Admission.tenant_id == tenant_id, Admission.student_id == Student.id)
        .correlate(Student)
        .scalar_subquery()
    )


def _latest_course(tenant_id: uuid.UUID) -> Any:
    return (
        select(Course.name)
        .join(
            Admission,
            and_(Admission.tenant_id == Course.tenant_id, Admission.course_id == Course.id),
        )
        .where(Admission.tenant_id == tenant_id, Admission.student_id == Student.id)
        .order_by(Admission.created_at.desc())
        .limit(1)
        .correlate(Student)
        .scalar_subquery()
    )


async def search_students(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    context: RequestContext,
    *,
    search: str | None,
    campus: uuid.UUID | None,
    page: PageParams,
    sort: Sequence[SortField],
) -> tuple[list[StudentListRow], int]:
    conditions: list[ColumnElement[bool]] = [
        Student.tenant_id == tenant_id,
        campus_visibility(Student.home_campus_id, context),
    ]
    if search:
        pattern = f"%{escape_like(search)}%"
        conditions.append(
            or_(
                Student.full_name.ilike(pattern, escape="\\"),
                Student.student_number.ilike(pattern, escape="\\"),
                Student.email_normalized.like(f"{escape_like(search.lower())}%", escape="\\"),
            )
        )
    if campus is not None:
        conditions.append(Student.home_campus_id == campus)
    total = await db.scalar(select(func.count()).select_from(Student).where(*conditions))
    columns = {
        "created_at": Student.created_at,
        "full_name": func.lower(Student.full_name),
        "student_number": Student.student_number,
    }
    order = [columns[f.name].desc() if f.descending else columns[f.name].asc() for f in sort]
    statement = (
        select(
            Student.id,
            Student.student_number,
            Student.full_name,
            Student.mobile,
            Student.email,
            Student.status,
            Student.home_campus_id.label("campus_id"),
            Campus.code.label("campus_code"),
            _admissions_count(tenant_id).label("admissions"),
            _latest_course(tenant_id).label("latest_course"),
            Student.created_at,
        )
        .join(
            Campus, and_(Campus.tenant_id == Student.tenant_id, Campus.id == Student.home_campus_id)
        )
        .where(*conditions)
        .order_by(*order, Student.id.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    rows = [StudentListRow(**row._mapping) for row in await db.execute(statement)]
    return rows, int(total or 0)


@dataclass(frozen=True, slots=True)
class StudentDetailRow:
    student: Student
    campus_code: str
    campus_name: str
    creator_name: str | None


async def student_detail(
    db: AsyncSession, tenant_id: uuid.UUID, student_id: uuid.UUID
) -> StudentDetailRow | None:
    statement = (
        select(Student, Campus.code, Campus.name, CreatorUser.display_name)
        .join(
            Campus, and_(Campus.tenant_id == Student.tenant_id, Campus.id == Student.home_campus_id)
        )
        .outerjoin(
            CreatorMembership,
            and_(
                CreatorMembership.tenant_id == Student.tenant_id,
                CreatorMembership.id == Student.created_by_membership_id,
            ),
        )
        .outerjoin(CreatorUser, CreatorUser.id == CreatorMembership.user_id)
        .where(Student.tenant_id == tenant_id, Student.id == student_id)
        .execution_options(populate_existing=True)
    )
    row = (await db.execute(statement)).one_or_none()
    if row is None:
        return None
    return StudentDetailRow(row[0], row[1], row[2], row[3])


@dataclass(frozen=True, slots=True)
class AdmissionRow:
    id: uuid.UUID
    admission_number: str
    status: str
    application_id: uuid.UUID
    application_number: str
    course_id: uuid.UUID
    course_code: str
    course_name: str
    course_category: str
    campus_id: uuid.UUID
    campus_code: str
    campus_name: str
    approved_at: datetime
    approver_name: str | None


async def admissions_of(
    db: AsyncSession, tenant_id: uuid.UUID, context: RequestContext, student_id: uuid.UUID
) -> list[AdmissionRow]:
    statement = (
        select(
            Admission.id,
            Admission.admission_number,
            Admission.status,
            Admission.application_id,
            Application.number.label("application_number"),
            Admission.course_id,
            Course.code.label("course_code"),
            Course.name.label("course_name"),
            Course.category.label("course_category"),
            Admission.campus_id,
            Campus.code.label("campus_code"),
            Campus.name.label("campus_name"),
            Admission.approved_at,
            ApproverUser.display_name.label("approver_name"),
        )
        .join(
            Application,
            and_(
                Application.tenant_id == Admission.tenant_id,
                Application.id == Admission.application_id,
            ),
        )
        .join(
            Course, and_(Course.tenant_id == Admission.tenant_id, Course.id == Admission.course_id)
        )
        .join(
            Campus, and_(Campus.tenant_id == Admission.tenant_id, Campus.id == Admission.campus_id)
        )
        .outerjoin(
            ApproverMembership,
            and_(
                ApproverMembership.tenant_id == Admission.tenant_id,
                ApproverMembership.id == Admission.approved_by_membership_id,
            ),
        )
        .outerjoin(ApproverUser, ApproverUser.id == ApproverMembership.user_id)
        .where(
            Admission.tenant_id == tenant_id,
            Admission.student_id == student_id,
            campus_visibility(Admission.campus_id, context),
        )
        .order_by(Admission.approved_at.desc(), Admission.id.desc())
    )
    return [AdmissionRow(**row._mapping) for row in await db.execute(statement)]


@dataclass(frozen=True, slots=True)
class CandidateRow:
    id: uuid.UUID
    student_number: str
    full_name: str
    date_of_birth: date | None
    campus_code: str
    created_at: datetime
    mobile_match: bool
    email_match: bool


async def candidates(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    context: RequestContext,
    *,
    mobile_key: str | None,
    email_normalized: str | None,
) -> list[CandidateRow]:
    """Visible students sharing a contact key: offered for an explicit link, never auto-linked."""
    keys: list[ColumnElement[bool]] = []
    mobile_match: ColumnElement[bool] = literal(False)
    email_match: ColumnElement[bool] = literal(False)
    if mobile_key:
        mobile_match = Student.mobile_key == mobile_key
        keys.append(mobile_match)
    if email_normalized:
        email_match = Student.email_normalized == email_normalized
        keys.append(email_match)
    if not keys:
        return []
    statement = (
        select(
            Student.id,
            Student.student_number,
            Student.full_name,
            Student.date_of_birth,
            Campus.code.label("campus_code"),
            Student.created_at,
            mobile_match.label("mobile_match"),
            email_match.label("email_match"),
        )
        .join(
            Campus, and_(Campus.tenant_id == Student.tenant_id, Campus.id == Student.home_campus_id)
        )
        .where(
            Student.tenant_id == tenant_id,
            campus_visibility(Student.home_campus_id, context),
            or_(*keys),
        )
        .order_by(Student.created_at.desc(), Student.id.desc())
        .limit(STUDENT_CANDIDATE_LIMIT)
    )
    return [CandidateRow(**row._mapping) for row in await db.execute(statement)]


@dataclass(frozen=True, slots=True)
class StudentDocumentRow:
    id: uuid.UUID
    application_id: uuid.UUID
    application_number: str
    document_type: str
    status: str
    file_name: str
    content_type: str
    size_bytes: int
    created_at: datetime


async def documents_of(
    db: AsyncSession, tenant_id: uuid.UUID, context: RequestContext, student_id: uuid.UUID
) -> list[StudentDocumentRow]:
    """The current documents of the student's admitted applications in the caller's campuses."""
    statement = (
        select(
            ApplicationDocument.id,
            ApplicationDocument.application_id,
            Application.number.label("application_number"),
            ApplicationDocument.document_type,
            ApplicationDocument.status,
            StoredFile.file_name,
            StoredFile.content_type,
            StoredFile.size_bytes,
            ApplicationDocument.created_at,
        )
        .join(
            Admission,
            and_(
                Admission.tenant_id == ApplicationDocument.tenant_id,
                Admission.application_id == ApplicationDocument.application_id,
            ),
        )
        .join(
            Application,
            and_(
                Application.tenant_id == ApplicationDocument.tenant_id,
                Application.id == ApplicationDocument.application_id,
            ),
        )
        .join(
            StoredFile,
            and_(
                StoredFile.tenant_id == ApplicationDocument.tenant_id,
                StoredFile.id == ApplicationDocument.stored_file_id,
            ),
        )
        .where(
            ApplicationDocument.tenant_id == tenant_id,
            Admission.student_id == student_id,
            ApplicationDocument.replaced_at.is_(None),
            campus_visibility(Application.campus_id, context),
        )
        .order_by(ApplicationDocument.document_type, ApplicationDocument.created_at.desc())
    )
    return [StudentDocumentRow(**row._mapping) for row in await db.execute(statement)]


@dataclass(frozen=True, slots=True)
class TimelineRow:
    id: uuid.UUID
    source: str
    subject_id: uuid.UUID
    kind: str
    actor_membership_id: uuid.UUID | None
    details: dict[str, Any]
    body: str | None
    created_at: datetime


async def timeline(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    context: RequestContext,
    student_id: uuid.UUID,
    *,
    include_leads: bool,
    include_applications: bool,
    page: PageParams,
) -> tuple[list[TimelineRow], int]:
    """The Student 360 history: the source leads' and the admitted applications' activity,
    each only for holders of its read permission and within the caller's campuses."""
    applications = (
        select(Application.id, Application.lead_id)
        .join(
            Admission,
            and_(
                Admission.tenant_id == Application.tenant_id,
                Admission.application_id == Application.id,
            ),
        )
        .where(
            Application.tenant_id == tenant_id,
            Admission.student_id == student_id,
            campus_visibility(Application.campus_id, context),
        )
        .subquery()
    )
    parts: list[Any] = []
    if include_applications:
        parts.append(
            select(
                ApplicationActivity.id,
                literal("application").label("source"),
                ApplicationActivity.application_id.label("subject_id"),
                ApplicationActivity.kind,
                ApplicationActivity.actor_membership_id,
                ApplicationActivity.details,
                null().label("body"),
                ApplicationActivity.created_at,
            ).where(
                ApplicationActivity.tenant_id == tenant_id,
                ApplicationActivity.application_id.in_(select(applications.c.id)),
            )
        )
    if include_leads:
        parts.append(
            select(
                LeadActivity.id,
                literal("lead").label("source"),
                LeadActivity.lead_id.label("subject_id"),
                LeadActivity.kind,
                LeadActivity.actor_membership_id,
                LeadActivity.details,
                LeadActivity.body,
                LeadActivity.created_at,
            )
            .join(
                Lead,
                and_(Lead.tenant_id == LeadActivity.tenant_id, Lead.id == LeadActivity.lead_id),
            )
            .where(
                LeadActivity.tenant_id == tenant_id,
                LeadActivity.lead_id.in_(
                    select(applications.c.lead_id).where(applications.c.lead_id.is_not(None))
                ),
                campus_visibility(Lead.campus_id, context),
            )
        )
    if not parts:
        return [], 0
    combined = (union_all(*parts) if len(parts) > 1 else parts[0]).subquery()
    total = await db.scalar(select(func.count()).select_from(combined))
    rows = await db.execute(
        select(combined)
        .order_by(combined.c.created_at.desc(), combined.c.id.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    return [TimelineRow(**row._mapping) for row in rows], int(total or 0)
