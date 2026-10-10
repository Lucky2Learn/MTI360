"""Finance-lite data access (Phase 02-5; ADR-0022).

ORM statements through :class:`TenantScopedRepository` and explicit tenant
predicates: the trusted tenant is applied by the repository, by the ORM
tenant filter and by Row-Level Security. Campus visibility of invoices and
payments uses :func:`app.core.authz.campus_visibility` on the fee invoice's
campus, so a restricted member never receives a row ``authorize()`` would
answer with 404.
"""

import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Final

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams, SortField
from app.core.search import escape_like
from app.core.tenancy import TenantScopedRepository
from app.modules.courses.models import Course
from app.modules.finance.domain import FeeStructureStatus
from app.modules.finance.models import FeeStructure

STRUCTURE_SORT_COLUMNS: Final = {
    "name": FeeStructure.name,
    "updated_at": FeeStructure.updated_at,
    "created_at": FeeStructure.created_at,
}


@dataclass(frozen=True, slots=True)
class CourseRef:
    id: uuid.UUID
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class StructureRow:
    structure: FeeStructure
    course: CourseRef


@dataclass(frozen=True, slots=True)
class StructureFilters:
    search: str | None = None
    statuses: Collection[FeeStructureStatus] = ()
    course_id: uuid.UUID | None = None


class FeeStructureRepository(TenantScopedRepository[FeeStructure]):
    model = FeeStructure

    async def locked(self, structure_id: uuid.UUID) -> FeeStructure | None:
        found: FeeStructure | None = await self._session.scalar(
            self.select().where(FeeStructure.id == structure_id).with_for_update()
        )
        return found

    async def active_for(self, course_id: uuid.UUID, *, lock: bool = False) -> FeeStructure | None:
        statement = self.select().where(
            FeeStructure.course_id == course_id,
            FeeStructure.status == FeeStructureStatus.ACTIVE.value,
        )
        if lock:
            statement = statement.with_for_update()
        found: FeeStructure | None = await self._session.scalar(statement)
        return found

    def _conditions(self, filters: StructureFilters) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if filters.search:
            pattern = f"%{escape_like(filters.search)}%"
            conditions.append(
                or_(
                    FeeStructure.name.ilike(pattern, escape="\\"),
                    Course.name.ilike(pattern, escape="\\"),
                    Course.code.ilike(pattern, escape="\\"),
                )
            )
        if filters.statuses:
            conditions.append(FeeStructure.status.in_(sorted(s.value for s in filters.statuses)))
        if filters.course_id is not None:
            conditions.append(FeeStructure.course_id == filters.course_id)
        return conditions

    def _joined(self) -> ColumnElement[bool]:
        return (Course.tenant_id == FeeStructure.tenant_id) & (Course.id == FeeStructure.course_id)

    async def search(
        self, filters: StructureFilters, page: PageParams, sort: Sequence[SortField]
    ) -> tuple[list[StructureRow], int]:
        conditions = self._conditions(filters)
        total = await self._session.scalar(
            select(func.count())
            .select_from(FeeStructure)
            .join(Course, self._joined())
            .where(FeeStructure.tenant_id == self.tenant_id, *conditions)
        )
        order = [
            STRUCTURE_SORT_COLUMNS[field.name].desc()
            if field.descending
            else STRUCTURE_SORT_COLUMNS[field.name]
            for field in sort
        ]
        statement = (
            select(FeeStructure, Course.id, Course.code, Course.name)
            .join(Course, self._joined())
            .where(FeeStructure.tenant_id == self.tenant_id, *conditions)
            .order_by(*order, FeeStructure.id)
            .limit(page.limit)
            .offset(page.offset)
        )
        rows = (await self._session.execute(statement)).all()
        return [StructureRow(row[0], CourseRef(row[1], row[2], row[3])) for row in rows], int(
            total or 0
        )


async def course_ref(
    db: AsyncSession, tenant_id: uuid.UUID, course_id: uuid.UUID
) -> tuple[CourseRef, str] | None:
    """The course of the trusted tenant and its status, or ``None``."""
    row = (
        await db.execute(
            select(Course.id, Course.code, Course.name, Course.status).where(
                Course.tenant_id == tenant_id, Course.id == course_id
            )
        )
    ).one_or_none()
    if row is None:
        return None
    return CourseRef(row[0], row[1], row[2]), str(row[3])
