"""Lead data access (Phase 02-1; blueprint §8, §10, §17, §19, §23).

ORM statements on tenant-scoped models: the trusted tenant is stated
explicitly in every statement, added again by the ORM tenant filter (also to
outer-joined and aliased entities), and enforced by Row-Level Security.

Campus scope is **not** in the database: every list, the duplicate check and
the assignee query apply :func:`app.core.authz.campus_visibility`, the SQL
form of ``authorize()`` for campus-scoped permissions (D-B1).
"""

import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Final

from sqlalchemy import ColumnElement, and_, exists, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.authz import campus_visibility
from app.core.context import RequestContext
from app.core.pagination import PageParams, SortField
from app.core.search import escape_like
from app.modules.access.models import MembershipRole, RolePermission
from app.modules.courses.models import Course
from app.modules.identity.domain import CampusScope, MembershipStatus, UserStatus
from app.modules.identity.models import MembershipCampus, TenantMembership, User
from app.modules.institute.models import Campus
from app.modules.leads.domain import (
    DUPLICATE_CANDIDATE_LIMIT,
    MOBILE_KEY_LENGTH,
    FollowUpStatus,
    LeadSource,
    LeadStatus,
)
from app.modules.leads.models import Lead, LeadActivity, LeadFollowUp

ASSIGNEE_LIMIT: Final = 200
OPEN = FollowUpStatus.OPEN.value

OwnerMembership = aliased(TenantMembership, name="owner_membership")
OwnerUser = aliased(User, name="owner_user")
CreatorMembership = aliased(TenantMembership, name="creator_membership")
CreatorUser = aliased(User, name="creator_user")
DuplicateOf = aliased(Lead, name="duplicate_of")


# --- Caller and members --------------------------------------------------------------------


async def membership_of(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> uuid.UUID | None:
    """The caller's membership in the trusted tenant."""
    found: uuid.UUID | None = await db.scalar(
        select(TenantMembership.id).where(
            TenantMembership.tenant_id == tenant_id, TenantMembership.user_id == user_id
        )
    )
    return found


def _holds_permission(tenant_id: uuid.UUID, code: str) -> ColumnElement[bool]:
    """The membership holds ``code`` through one of its roles (a campus-scoped permission
    is effective for every scope, as in ``access.service.effective_permissions``)."""
    return exists().where(
        MembershipRole.tenant_id == tenant_id,
        MembershipRole.membership_id == TenantMembership.id,
        RolePermission.tenant_id == tenant_id,
        RolePermission.role_id == MembershipRole.role_id,
        RolePermission.permission_code == code,
    )


def _covers_campus(tenant_id: uuid.UUID, campus_id: uuid.UUID | None) -> ColumnElement[bool]:
    """All campuses, or a permitted campus: the lead's one, or any for a pool lead."""
    permitted = [
        MembershipCampus.tenant_id == tenant_id,
        MembershipCampus.membership_id == TenantMembership.id,
        MembershipCampus.removed_at.is_(None),
    ]
    if campus_id is not None:
        permitted.append(MembershipCampus.campus_id == campus_id)
    return or_(
        TenantMembership.campus_scope == CampusScope.ALL.value,
        exists().where(*permitted),
    )


@dataclass(frozen=True, slots=True)
class Member:
    membership_id: uuid.UUID
    display_name: str


async def eligible_members(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    permission_code: str,
    campus_id: uuid.UUID | None,
    membership_id: uuid.UUID | None = None,
) -> list[Member]:
    """ACTIVE members (active identity) holding ``permission_code`` whose campus scope covers
    ``campus_id``: the assignee rule of blueprint §10, for the picker and for one check."""
    statement = (
        select(TenantMembership.id, User.display_name)
        .join(User, User.id == TenantMembership.user_id)
        .where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status == MembershipStatus.ACTIVE.value,
            User.status == UserStatus.ACTIVE.value,
            _holds_permission(tenant_id, permission_code),
            _covers_campus(tenant_id, campus_id),
        )
        .order_by(func.lower(User.display_name), TenantMembership.id)
        .limit(ASSIGNEE_LIMIT)
    )
    if membership_id is not None:
        statement = statement.where(TenantMembership.id == membership_id)
    return [Member(row.id, row.display_name) for row in await db.execute(statement)]


async def display_names(
    db: AsyncSession, tenant_id: uuid.UUID, membership_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if not membership_ids:
        return {}
    rows = await db.execute(
        select(TenantMembership.id, User.display_name)
        .join(User, User.id == TenantMembership.user_id)
        .where(TenantMembership.tenant_id == tenant_id, TenantMembership.id.in_(membership_ids))
    )
    return {row.id: row.display_name for row in rows}


async def campus_names(
    db: AsyncSession, tenant_id: uuid.UUID, campus_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if not campus_ids:
        return {}
    rows = await db.execute(
        select(Campus.id, Campus.name).where(
            Campus.tenant_id == tenant_id, Campus.id.in_(campus_ids)
        )
    )
    return {row.id: row.name for row in rows}


async def campus_exists(db: AsyncSession, tenant_id: uuid.UUID, campus_id: uuid.UUID) -> bool:
    found = await db.scalar(
        select(Campus.id).where(Campus.tenant_id == tenant_id, Campus.id == campus_id)
    )
    return found is not None


async def course_status(db: AsyncSession, tenant_id: uuid.UUID, course_id: uuid.UUID) -> str | None:
    status: str | None = await db.scalar(
        select(Course.status).where(Course.tenant_id == tenant_id, Course.id == course_id)
    )
    return status


# --- Leads ---------------------------------------------------------------------------------


async def lead(db: AsyncSession, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> Lead | None:
    found: Lead | None = await db.scalar(
        select(Lead).where(Lead.tenant_id == tenant_id, Lead.id == lead_id)
    )
    return found


def _next_follow_up(tenant_id: uuid.UUID) -> Any:
    return (
        select(func.min(LeadFollowUp.due_at))
        .where(
            LeadFollowUp.tenant_id == tenant_id,
            LeadFollowUp.lead_id == Lead.id,
            LeadFollowUp.status == OPEN,
        )
        .correlate(Lead)
        .scalar_subquery()
    )


def _overdue_follow_ups(tenant_id: uuid.UUID) -> Any:
    return (
        select(func.count())
        .where(
            LeadFollowUp.tenant_id == tenant_id,
            LeadFollowUp.lead_id == Lead.id,
            LeadFollowUp.status == OPEN,
            LeadFollowUp.due_at < func.now(),
        )
        .correlate(Lead)
        .scalar_subquery()
    )


def _open_follow_up(tenant_id: uuid.UUID, *conditions: ColumnElement[bool]) -> ColumnElement[bool]:
    return exists().where(
        LeadFollowUp.tenant_id == tenant_id,
        LeadFollowUp.lead_id == Lead.id,
        LeadFollowUp.status == OPEN,
        *conditions,
    )


@dataclass(frozen=True, slots=True)
class LeadFilters:
    search: str | None = None
    search_digits: str | None = None
    statuses: Collection[LeadStatus] = ()
    owner: uuid.UUID | None = None
    unassigned: bool = False
    campus: uuid.UUID | None = None
    pool: bool = False
    course: uuid.UUID | None = None
    sources: Collection[LeadSource] = ()
    follow_up: str | None = None
    """``overdue`` / ``today`` / ``upcoming`` / ``none`` (``FollowUpFilter``)."""
    day_start: datetime | None = None
    day_end: datetime | None = None
    """The caller's "today" (``follow_up=today`` / ``upcoming``)."""
    created_from: datetime | None = None
    created_before: datetime | None = None


def _filter_conditions(
    tenant_id: uuid.UUID, context: RequestContext, filters: LeadFilters
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = [
        Lead.tenant_id == tenant_id,
        campus_visibility(Lead.campus_id, context),
    ]
    if filters.search:
        pattern = f"%{escape_like(filters.search)}%"
        matches: list[ColumnElement[bool]] = [
            Lead.full_name.ilike(pattern, escape="\\"),
            Lead.email_normalized.like(f"{escape_like(filters.search.lower())}%", escape="\\"),
        ]
        if filters.search_digits:
            matches.append(Lead.mobile_key.like(f"%{filters.search_digits[-MOBILE_KEY_LENGTH:]}%"))
        conditions.append(or_(*matches))
    if filters.statuses:
        conditions.append(Lead.status.in_(sorted(s.value for s in filters.statuses)))
    if filters.unassigned:
        conditions.append(Lead.owner_membership_id.is_(None))
    elif filters.owner is not None:
        conditions.append(Lead.owner_membership_id == filters.owner)
    if filters.pool:
        conditions.append(Lead.campus_id.is_(None))
    elif filters.campus is not None:
        conditions.append(Lead.campus_id == filters.campus)
    if filters.course is not None:
        conditions.append(Lead.interested_course_id == filters.course)
    if filters.sources:
        conditions.append(Lead.source.in_(sorted(s.value for s in filters.sources)))
    if filters.follow_up == "overdue":
        conditions.append(_open_follow_up(tenant_id, LeadFollowUp.due_at < func.now()))
    elif filters.follow_up == "today" and filters.day_start and filters.day_end:
        conditions.append(
            _open_follow_up(
                tenant_id,
                LeadFollowUp.due_at >= filters.day_start,
                LeadFollowUp.due_at < filters.day_end,
            )
        )
    elif filters.follow_up == "upcoming" and filters.day_end:
        conditions.append(_open_follow_up(tenant_id, LeadFollowUp.due_at >= filters.day_end))
    elif filters.follow_up == "none":
        conditions.append(~_open_follow_up(tenant_id))
    if filters.created_from is not None:
        conditions.append(Lead.created_at >= filters.created_from)
    if filters.created_before is not None:
        conditions.append(Lead.created_at < filters.created_before)
    return conditions


@dataclass(frozen=True, slots=True)
class LeadListRow:
    id: uuid.UUID
    full_name: str
    mobile: str | None
    email: str | None
    status: str
    source: str
    course_code: str | None
    course_name: str | None
    campus_id: uuid.UUID | None
    campus_code: str | None
    owner_membership_id: uuid.UUID | None
    owner_name: str | None
    next_follow_up_at: datetime | None
    overdue_follow_ups: int
    created_at: datetime
    updated_at: datetime
    version: int


async def search_leads(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    context: RequestContext,
    filters: LeadFilters,
    page: PageParams,
    sort: Sequence[SortField],
) -> tuple[list[LeadListRow], int]:
    conditions = _filter_conditions(tenant_id, context, filters)
    total = await db.scalar(select(func.count()).select_from(Lead).where(*conditions))
    next_follow_up = _next_follow_up(tenant_id).label("next_follow_up_at")
    columns = {
        "created_at": Lead.created_at,
        "updated_at": Lead.updated_at,
        "full_name": func.lower(Lead.full_name),
        "next_follow_up_at": next_follow_up,
    }
    order = [
        (columns[f.name].desc() if f.descending else columns[f.name].asc()).nulls_last()
        for f in sort
    ]
    statement = (
        select(
            Lead.id,
            Lead.full_name,
            Lead.mobile,
            Lead.email,
            Lead.status,
            Lead.source,
            Course.code.label("course_code"),
            Course.name.label("course_name"),
            Lead.campus_id,
            Campus.code.label("campus_code"),
            Lead.owner_membership_id,
            OwnerUser.display_name.label("owner_name"),
            next_follow_up,
            _overdue_follow_ups(tenant_id).label("overdue_follow_ups"),
            Lead.created_at,
            Lead.updated_at,
            Lead.version,
        )
        .outerjoin(
            Course,
            and_(Course.tenant_id == Lead.tenant_id, Course.id == Lead.interested_course_id),
        )
        .outerjoin(Campus, and_(Campus.tenant_id == Lead.tenant_id, Campus.id == Lead.campus_id))
        .outerjoin(
            OwnerMembership,
            and_(
                OwnerMembership.tenant_id == Lead.tenant_id,
                OwnerMembership.id == Lead.owner_membership_id,
            ),
        )
        .outerjoin(OwnerUser, OwnerUser.id == OwnerMembership.user_id)
        .where(*conditions)
        .order_by(*order, Lead.id.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    rows = [LeadListRow(**row._mapping) for row in await db.execute(statement)]
    return rows, int(total or 0)


@dataclass(frozen=True, slots=True)
class LeadDetailRow:
    lead: Lead
    course_code: str | None
    course_name: str | None
    course_status: str | None
    campus_code: str | None
    campus_name: str | None
    owner_name: str | None
    owner_active: bool | None
    creator_name: str | None
    duplicate_name: str | None
    duplicate_campus_id: uuid.UUID | None
    next_follow_up_at: datetime | None
    overdue_follow_ups: int


async def lead_detail(
    db: AsyncSession, tenant_id: uuid.UUID, lead_id: uuid.UUID
) -> LeadDetailRow | None:
    """One lead with its display references (authorization is the caller's job)."""
    owner_active = and_(
        OwnerMembership.status == MembershipStatus.ACTIVE.value,
        OwnerUser.status == UserStatus.ACTIVE.value,
    )
    statement = (
        select(
            Lead,
            Course.code,
            Course.name,
            Course.status,
            Campus.code,
            Campus.name,
            OwnerUser.display_name,
            owner_active,
            CreatorUser.display_name,
            DuplicateOf.full_name,
            DuplicateOf.campus_id,
            _next_follow_up(tenant_id),
            _overdue_follow_ups(tenant_id),
        )
        .outerjoin(
            Course,
            and_(Course.tenant_id == Lead.tenant_id, Course.id == Lead.interested_course_id),
        )
        .outerjoin(Campus, and_(Campus.tenant_id == Lead.tenant_id, Campus.id == Lead.campus_id))
        .outerjoin(
            OwnerMembership,
            and_(
                OwnerMembership.tenant_id == Lead.tenant_id,
                OwnerMembership.id == Lead.owner_membership_id,
            ),
        )
        .outerjoin(OwnerUser, OwnerUser.id == OwnerMembership.user_id)
        .outerjoin(
            CreatorMembership,
            and_(
                CreatorMembership.tenant_id == Lead.tenant_id,
                CreatorMembership.id == Lead.created_by_membership_id,
            ),
        )
        .outerjoin(CreatorUser, CreatorUser.id == CreatorMembership.user_id)
        .outerjoin(
            DuplicateOf,
            and_(
                DuplicateOf.tenant_id == Lead.tenant_id,
                DuplicateOf.id == Lead.duplicate_of_lead_id,
            ),
        )
        .where(Lead.tenant_id == tenant_id, Lead.id == lead_id)
        .execution_options(populate_existing=True)
    )
    row = (await db.execute(statement)).one_or_none()
    if row is None:
        return None
    return LeadDetailRow(
        lead=row[0],
        course_code=row[1],
        course_name=row[2],
        course_status=row[3],
        campus_code=row[4],
        campus_name=row[5],
        owner_name=row[6],
        owner_active=row[7] if row[6] is not None else None,
        creator_name=row[8],
        duplicate_name=row[9],
        duplicate_campus_id=row[10],
        next_follow_up_at=row[11],
        overdue_follow_ups=int(row[12] or 0),
    )


@dataclass(frozen=True, slots=True)
class DuplicateRow:
    id: uuid.UUID
    full_name: str
    status: str
    course_name: str | None
    campus_name: str | None
    owner_name: str | None
    created_at: datetime
    mobile_match: bool
    email_match: bool


async def duplicate_candidates(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    context: RequestContext,
    *,
    mobile_key: str | None,
    email_normalized: str | None,
    exclude: uuid.UUID | None,
) -> list[DuplicateRow]:
    """Visible leads (tenant + campus rule) sharing a key; never ``DUPLICATE`` ones (§8)."""
    keys: list[ColumnElement[bool]] = []
    mobile_match: ColumnElement[bool] = literal(False)
    email_match: ColumnElement[bool] = literal(False)
    if mobile_key:
        mobile_match = Lead.mobile_key == mobile_key
        keys.append(mobile_match)
    if email_normalized:
        email_match = Lead.email_normalized == email_normalized
        keys.append(email_match)
    if not keys:
        return []
    conditions = [
        Lead.tenant_id == tenant_id,
        campus_visibility(Lead.campus_id, context),
        Lead.status != LeadStatus.DUPLICATE.value,
        or_(*keys),
    ]
    if exclude is not None:
        conditions.append(Lead.id != exclude)
    statement = (
        select(
            Lead.id,
            Lead.full_name,
            Lead.status,
            Course.name.label("course_name"),
            Campus.name.label("campus_name"),
            OwnerUser.display_name.label("owner_name"),
            Lead.created_at,
            mobile_match.label("mobile_match"),
            email_match.label("email_match"),
        )
        .outerjoin(
            Course,
            and_(Course.tenant_id == Lead.tenant_id, Course.id == Lead.interested_course_id),
        )
        .outerjoin(Campus, and_(Campus.tenant_id == Lead.tenant_id, Campus.id == Lead.campus_id))
        .outerjoin(
            OwnerMembership,
            and_(
                OwnerMembership.tenant_id == Lead.tenant_id,
                OwnerMembership.id == Lead.owner_membership_id,
            ),
        )
        .outerjoin(OwnerUser, OwnerUser.id == OwnerMembership.user_id)
        .where(*conditions)
        .order_by(Lead.created_at.desc(), Lead.id.desc())
        .limit(DUPLICATE_CANDIDATE_LIMIT)
    )
    return [DuplicateRow(**row._mapping) for row in await db.execute(statement)]


# --- Follow-ups and activity ---------------------------------------------------------------


async def follow_up(
    db: AsyncSession, tenant_id: uuid.UUID, follow_up_id: uuid.UUID
) -> LeadFollowUp | None:
    found: LeadFollowUp | None = await db.scalar(
        select(LeadFollowUp).where(
            LeadFollowUp.tenant_id == tenant_id, LeadFollowUp.id == follow_up_id
        )
    )
    return found


async def follow_ups_of(
    db: AsyncSession, tenant_id: uuid.UUID, lead_id: uuid.UUID, status: FollowUpStatus | None
) -> list[LeadFollowUp]:
    statement = select(LeadFollowUp).where(
        LeadFollowUp.tenant_id == tenant_id, LeadFollowUp.lead_id == lead_id
    )
    if status is not None:
        statement = statement.where(LeadFollowUp.status == status.value)
    statement = statement.order_by(LeadFollowUp.due_at, LeadFollowUp.id)
    return list((await db.scalars(statement)).all())


async def activities_of(
    db: AsyncSession, tenant_id: uuid.UUID, lead_id: uuid.UUID, page: PageParams
) -> tuple[list[LeadActivity], int]:
    conditions = (LeadActivity.tenant_id == tenant_id, LeadActivity.lead_id == lead_id)
    total = await db.scalar(select(func.count()).select_from(LeadActivity).where(*conditions))
    rows = await db.scalars(
        select(LeadActivity)
        .where(*conditions)
        .order_by(LeadActivity.created_at.desc(), LeadActivity.id.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    return list(rows.all()), int(total or 0)


def day_bounds(day: date, utc_offset_minutes: int) -> tuple[datetime, datetime]:
    """``[day 00:00, next day 00:00)`` of the caller's local day, in UTC."""
    start = datetime(day.year, day.month, day.day, tzinfo=UTC) - timedelta(
        minutes=utc_offset_minutes
    )
    return start, start + timedelta(days=1)
