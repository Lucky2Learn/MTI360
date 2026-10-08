"""Course data access (Phase 02-1).

ORM statements through :class:`TenantScopedRepository`: the trusted tenant is
applied explicitly, by the ORM tenant filter and by Row-Level Security.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Final

from sqlalchemy import ColumnElement, func, or_, select

from app.core.pagination import PageParams, SortField
from app.core.search import escape_like
from app.core.tenancy import TenantScopedRepository
from app.modules.courses.domain import CourseCategory, CourseStatus
from app.modules.courses.models import Course

SORT_COLUMNS: Final = {
    "name": Course.name,
    "code": Course.code,
    "updated_at": Course.updated_at,
}


@dataclass(frozen=True, slots=True)
class CourseFilters:
    search: str | None = None
    statuses: Collection[CourseStatus] = ()
    category: CourseCategory | None = None


class CourseRepository(TenantScopedRepository[Course]):
    model = Course

    async def code_taken(self, code: str) -> bool:
        found = await self._session.scalar(self.select().where(Course.code == code))
        return found is not None

    def _conditions(self, filters: CourseFilters) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if filters.search:
            pattern = f"%{escape_like(filters.search)}%"
            conditions.append(
                or_(
                    Course.name.ilike(pattern, escape="\\"),
                    Course.code.ilike(pattern, escape="\\"),
                )
            )
        if filters.statuses:
            conditions.append(Course.status.in_(sorted(s.value for s in filters.statuses)))
        if filters.category is not None:
            conditions.append(Course.category == filters.category.value)
        return conditions

    async def search(
        self, filters: CourseFilters, page: PageParams, sort: Sequence[SortField]
    ) -> tuple[list[Course], int]:
        conditions = self._conditions(filters)
        total = await self._session.scalar(
            select(func.count())
            .select_from(Course)
            .where(Course.tenant_id == self.tenant_id, *conditions)
        )
        order = [
            SORT_COLUMNS[field.name].desc() if field.descending else SORT_COLUMNS[field.name]
            for field in sort
        ]
        statement = (
            self.select()
            .where(*conditions)
            .order_by(*order, Course.id)
            .limit(page.limit)
            .offset(page.offset)
        )
        return list((await self._session.scalars(statement)).all()), int(total or 0)
