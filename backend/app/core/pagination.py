"""Pagination and sorting parameters (T01-01; T01-00 decision D13).

Collections use offset pagination with a total, matching the design-system
Pagination component::

    GET /api/v1/campuses?limit=25&offset=50&sort=name,-created_at

* ``limit``: 1 to 100, default 25. ``offset``: 0 to 10 000 (deeper pages need a
  filter; cursor pagination is reserved for high-volume feeds).
* ``sort``: comma-separated fields from an explicit allow-list; ``-`` means
  descending; at most three fields, no duplicates.
* Filters are explicit, typed query parameters declared by each endpoint;
  unknown or invalid values are a ``422 VALIDATION_ERROR``.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Annotated, Final

from fastapi import Depends, Query

from app.core.errors import ErrorDetail, ValidationFailedError

DEFAULT_PAGE_SIZE: Final = 25
MAX_PAGE_SIZE: Final = 100
MAX_OFFSET: Final = 10_000
MAX_SORT_FIELDS: Final = 3


@dataclass(frozen=True, slots=True)
class PageParams:
    limit: int
    offset: int


def page_params(
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=MAX_OFFSET)] = 0,
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


Pagination = Annotated[PageParams, Depends(page_params)]


@dataclass(frozen=True, slots=True)
class SortField:
    name: str
    descending: bool = False


def _sort_error(message: str) -> ValidationFailedError:
    return ValidationFailedError(
        details=[ErrorDetail(field="sort", code="invalid_sort", message=message)]
    )


def parse_sort(value: str | None, *, allowed: Iterable[str], default: str) -> tuple[SortField, ...]:
    """Parse ``sort`` against an allow-list. The rejected value is never echoed."""
    allowed_names = frozenset(allowed)
    raw = value if value is not None and value.strip() else default
    fields: list[SortField] = []
    for part in (item.strip() for item in raw.split(",")):
        descending = part.startswith("-")
        name = part.removeprefix("-")
        if name not in allowed_names:
            supported = ", ".join(sorted(allowed_names))
            raise _sort_error(f"Unsupported sort field. Supported fields: {supported}.")
        if any(existing.name == name for existing in fields):
            raise _sort_error("Each sort field may be used once.")
        fields.append(SortField(name=name, descending=descending))
    if len(fields) > MAX_SORT_FIELDS:
        raise _sort_error(f"Sort by at most {MAX_SORT_FIELDS} fields.")
    return tuple(fields)


def sort_param(
    *, allowed: Iterable[str], default: str
) -> Callable[[str | None], tuple[SortField, ...]]:
    """Dependency factory: ``Depends(sort_param(allowed={"name"}, default="name"))``."""
    allowed_names = frozenset(allowed)
    parse_sort(None, allowed=allowed_names, default=default)  # validate the default once

    def dependency(
        sort: Annotated[str | None, Query(max_length=200)] = None,
    ) -> tuple[SortField, ...]:
        return parse_sort(sort, allowed=allowed_names, default=default)

    return dependency
