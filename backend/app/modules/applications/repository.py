"""Application data access (Phase 02-2; ADR-0021 §3-§4).

The trusted tenant is stated in every statement, added again by the ORM tenant
filter and enforced by Row-Level Security. Campus scope is applied with
:func:`app.core.authz.campus_visibility` (D-B1); applications always have a
campus (L6).
"""

import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.authz import campus_visibility
from app.core.context import RequestContext
from app.core.pagination import PageParams, SortField
from app.core.search import escape_like
from app.modules.applications.domain import CLOSED, ApplicationStatus
from app.modules.applications.models import Application, ApplicationActivity
from app.modules.courses.models import Course
from app.modules.documents.domain import NOT_VERIFIED, DocumentStatus
from app.modules.documents.models import ApplicationDocument
from app.modules.identity.models import TenantMembership, User
from app.modules.institute.models import Campus
from app.modules.leads.models import Lead
from app.modules.students.models import Admission, Student

Owner = aliased(TenantMembership, name="application_owner")
OwnerUser = aliased(User, name="application_owner_user")
Creator = aliased(TenantMembership, name="application_creator")
CreatorUser = aliased(User, name="application_creator_user")
Reviewer = aliased(TenantMembership, name="application_reviewer")
ReviewerUser = aliased(User, name="application_reviewer_user")
Declarer = aliased(TenantMembership, name="application_declarer")
DeclarerUser = aliased(User, name="application_declarer_user")


async def application(
    db: AsyncSession, tenant_id: uuid.UUID, application_id: uuid.UUID, *, lock: bool = False
) -> Application | None:
    """One application; ``lock`` takes a row lock (admission and review serialise on it)."""
    statement = select(Application).where(
        Application.tenant_id == tenant_id, Application.id == application_id
    )
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    found: Application | None = await db.scalar(statement)
    return found


async def open_application_for(
    db: AsyncSession, tenant_id: uuid.UUID, lead_id: uuid.UUID, course_id: uuid.UUID
) -> bool:
    """Whether the lead already has an application for the course that is not closed."""
    found = await db.scalar(
        select(Application.id).where(
            Application.tenant_id == tenant_id,
            Application.lead_id == lead_id,
            Application.course_id == course_id,
            Application.status.not_in(sorted(s.value for s in CLOSED)),
        )
    )
    return found is not None


def unverified_documents(tenant_id: uuid.UUID, application_id: Any) -> Any:
    """Current documents of the application that are not verified (they block approval)."""
    return (
        select(func.count())
        .where(
            ApplicationDocument.tenant_id == tenant_id,
            ApplicationDocument.application_id == application_id,
            ApplicationDocument.replaced_at.is_(None),
            ApplicationDocument.status.in_(sorted(s.value for s in NOT_VERIFIED)),
        )
        .scalar_subquery()
    )


async def unverified_count(
    db: AsyncSession, tenant_id: uuid.UUID, application_id: uuid.UUID
) -> int:
    return int(await db.scalar(select(unverified_documents(tenant_id, application_id))) or 0)


@dataclass(frozen=True, slots=True)
class ApplicationFilters:
    search: str | None = None
    statuses: Collection[ApplicationStatus] = ()
    campus: uuid.UUID | None = None
    course: uuid.UUID | None = None
    lead: uuid.UUID | None = None
    owner: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ApplicationListRow:
    id: uuid.UUID
    number: str
    full_name: str
    status: str
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


async def search_applications(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    context: RequestContext,
    filters: ApplicationFilters,
    page: PageParams,
    sort: Sequence[SortField],
) -> tuple[list[ApplicationListRow], int]:
    conditions: list[ColumnElement[bool]] = [
        Application.tenant_id == tenant_id,
        campus_visibility(Application.campus_id, context),
    ]
    if filters.search:
        pattern = f"%{escape_like(filters.search)}%"
        conditions.append(
            or_(
                Application.full_name.ilike(pattern, escape="\\"),
                Application.number.ilike(pattern, escape="\\"),
            )
        )
    if filters.statuses:
        conditions.append(Application.status.in_(sorted(s.value for s in filters.statuses)))
    if filters.campus is not None:
        conditions.append(Application.campus_id == filters.campus)
    if filters.course is not None:
        conditions.append(Application.course_id == filters.course)
    if filters.lead is not None:
        conditions.append(Application.lead_id == filters.lead)
    if filters.owner is not None:
        conditions.append(Application.owner_membership_id == filters.owner)
    total = await db.scalar(select(func.count()).select_from(Application).where(*conditions))
    columns = {
        "created_at": Application.created_at,
        "updated_at": Application.updated_at,
        "submitted_at": Application.submitted_at,
        "full_name": func.lower(Application.full_name),
        "number": Application.number,
    }
    order = [
        (columns[f.name].desc() if f.descending else columns[f.name].asc()).nulls_last()
        for f in sort
    ]
    statement = (
        select(
            Application.id,
            Application.number,
            Application.full_name,
            Application.status,
            Application.lead_id,
            Course.code.label("course_code"),
            Course.name.label("course_name"),
            Application.campus_id,
            Campus.code.label("campus_code"),
            OwnerUser.display_name.label("owner_name"),
            unverified_documents(tenant_id, Application.id).label("documents_pending"),
            Application.submitted_at,
            Application.created_at,
            Application.updated_at,
            Application.version,
        )
        .join(
            Course,
            and_(Course.tenant_id == Application.tenant_id, Course.id == Application.course_id),
        )
        .join(
            Campus,
            and_(Campus.tenant_id == Application.tenant_id, Campus.id == Application.campus_id),
        )
        .outerjoin(
            Owner,
            and_(
                Owner.tenant_id == Application.tenant_id,
                Owner.id == Application.owner_membership_id,
            ),
        )
        .outerjoin(OwnerUser, OwnerUser.id == Owner.user_id)
        .where(*conditions)
        .order_by(*order, Application.id.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    rows = [ApplicationListRow(**row._mapping) for row in await db.execute(statement)]
    return rows, int(total or 0)


@dataclass(frozen=True, slots=True)
class ApplicationDetailRow:
    application: Application
    course_code: str
    course_name: str
    course_status: str
    campus_code: str
    campus_name: str
    lead_name: str | None
    lead_status: str | None
    lead_campus_id: uuid.UUID | None
    owner_name: str | None
    creator_name: str | None
    reviewer_name: str | None
    declarer_name: str | None
    admission_id: uuid.UUID | None
    admission_number: str | None
    student_id: uuid.UUID | None
    student_number: str | None
    student_campus_id: uuid.UUID | None
    documents_total: int
    documents_verified: int
    documents_pending: int


def _documents(tenant_id: uuid.UUID, *statuses: DocumentStatus) -> Any:
    conditions = [
        ApplicationDocument.tenant_id == tenant_id,
        ApplicationDocument.application_id == Application.id,
        ApplicationDocument.replaced_at.is_(None),
    ]
    if statuses:
        conditions.append(ApplicationDocument.status.in_([s.value for s in statuses]))
    return select(func.count()).where(*conditions).correlate(Application).scalar_subquery()


def _member(alias: Any, user: Any, column: Any) -> tuple[Any, Any, Any, Any]:
    return (
        alias,
        and_(alias.tenant_id == Application.tenant_id, alias.id == column),
        user,
        user.id == alias.user_id,
    )


async def application_detail(
    db: AsyncSession, tenant_id: uuid.UUID, application_id: uuid.UUID
) -> ApplicationDetailRow | None:
    """One application with its display references (authorization is the caller's job)."""
    statement = (
        select(
            Application,
            Course.code,
            Course.name,
            Course.status,
            Campus.code,
            Campus.name,
            Lead.full_name,
            Lead.status,
            Lead.campus_id,
            OwnerUser.display_name,
            CreatorUser.display_name,
            ReviewerUser.display_name,
            DeclarerUser.display_name,
            Admission.id,
            Admission.admission_number,
            Student.id,
            Student.student_number,
            Student.home_campus_id,
            _documents(tenant_id),
            _documents(tenant_id, DocumentStatus.VERIFIED),
            _documents(tenant_id, *NOT_VERIFIED),
        )
        .join(
            Course,
            and_(Course.tenant_id == Application.tenant_id, Course.id == Application.course_id),
        )
        .join(
            Campus,
            and_(Campus.tenant_id == Application.tenant_id, Campus.id == Application.campus_id),
        )
        .outerjoin(
            Lead, and_(Lead.tenant_id == Application.tenant_id, Lead.id == Application.lead_id)
        )
        .outerjoin(
            Admission,
            and_(
                Admission.tenant_id == Application.tenant_id,
                Admission.application_id == Application.id,
            ),
        )
        .outerjoin(
            Student,
            and_(Student.tenant_id == Admission.tenant_id, Student.id == Admission.student_id),
        )
    )
    for alias, on, user, user_on in (
        _member(Owner, OwnerUser, Application.owner_membership_id),
        _member(Creator, CreatorUser, Application.created_by_membership_id),
        _member(Reviewer, ReviewerUser, Application.reviewed_by_membership_id),
        _member(Declarer, DeclarerUser, Application.declared_by_membership_id),
    ):
        statement = statement.outerjoin(alias, on).outerjoin(user, user_on)
    statement = statement.where(
        Application.tenant_id == tenant_id, Application.id == application_id
    ).execution_options(populate_existing=True)
    row = (await db.execute(statement)).one_or_none()
    if row is None:
        return None
    return ApplicationDetailRow(
        application=row[0],
        course_code=row[1],
        course_name=row[2],
        course_status=row[3],
        campus_code=row[4],
        campus_name=row[5],
        lead_name=row[6],
        lead_status=row[7],
        lead_campus_id=row[8],
        owner_name=row[9],
        creator_name=row[10],
        reviewer_name=row[11],
        declarer_name=row[12],
        admission_id=row[13],
        admission_number=row[14],
        student_id=row[15],
        student_number=row[16],
        student_campus_id=row[17],
        documents_total=int(row[18] or 0),
        documents_verified=int(row[19] or 0),
        documents_pending=int(row[20] or 0),
    )


async def activities_of(
    db: AsyncSession, tenant_id: uuid.UUID, application_id: uuid.UUID, page: PageParams
) -> tuple[list[ApplicationActivity], int]:
    conditions = (
        ApplicationActivity.tenant_id == tenant_id,
        ApplicationActivity.application_id == application_id,
    )
    total = await db.scalar(
        select(func.count()).select_from(ApplicationActivity).where(*conditions)
    )
    rows = await db.scalars(
        select(ApplicationActivity)
        .where(*conditions)
        .order_by(ApplicationActivity.created_at.desc(), ApplicationActivity.id.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    return list(rows.all()), int(total or 0)
