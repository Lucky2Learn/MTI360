"""Campus visibility of lists (Phase 02-1; D-B1, ADR-0020 §7).

``authorize()`` decides about one loaded resource. Lists, the lead duplicate
check and the assignee query need the same rule as a SQL predicate, so a
restricted member never receives a row that ``authorize()`` would answer
with 404:

* all-campus members: no campus predicate;
* restricted members: ``campus_id IS NULL OR campus_id IN (:campus_ids)``.
  A resource without a campus (an institute-wide lead) is visible to every
  holder of the campus-scoped permission, exactly as ``authorize()`` step 8.

:func:`campus_visible` is the same rule for one value; a unit test compares
both with ``authorize()``.
"""

import uuid
from typing import Any

from sqlalchemy import ColumnElement, or_, true

from app.core.context import RequestContext


def campus_visible(campus_id: uuid.UUID | None, context: RequestContext) -> bool:
    """Whether a resource of ``campus_id`` is within the member's campuses."""
    return context.all_campuses or campus_id is None or campus_id in context.campus_ids


def campus_visibility(column: Any, context: RequestContext) -> ColumnElement[bool]:
    """The SQL form of :func:`campus_visible` for a nullable campus column."""
    if context.all_campuses:
        return true()
    if not context.campus_ids:
        return column.is_(None)  # type: ignore[no-any-return]
    return or_(column.is_(None), column.in_(sorted(context.campus_ids)))
