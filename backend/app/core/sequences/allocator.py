"""Transactional, gap-free number allocation (ADR-0021 §7; ADR-0022 §3).

One ``INSERT … ON CONFLICT DO UPDATE … RETURNING`` in the caller's
transaction: the row lock serialises concurrent callers of one tenant,
sequence and period, and a rolled-back transaction rolls the increment back
(no gaps). The period comes from the database clock, ``now()``: the
transaction's start, so a document stamped with ``now()`` in the same
transaction always agrees with its number. The tenant comes from the trusted
context only.
"""

from typing import Any, cast

from sqlalchemy import ColumnElement, Integer, Table, case, extract, func, select
from sqlalchemy import cast as sql_cast
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import current_context
from app.core.ids import new_id
from app.core.sequences.models import TenantSequence
from app.core.sequences.numbering import (
    FINANCIAL_YEAR_FIRST_MONTH,
    IST_ZONE,
    PERIODS,
    Period,
    SequenceName,
    format_number,
)

SEQUENCES = cast(Table, TenantSequence.__table__)


def calendar_year_period(instant: Any) -> ColumnElement[int]:
    """SQL: the calendar year of the ``timestamptz`` ``instant`` in UTC."""
    return sql_cast(extract("year", func.timezone("UTC", instant)), Integer)


def financial_year_period(instant: Any) -> ColumnElement[int]:
    """SQL: the Indian financial year (start year) of the ``timestamptz`` ``instant``.

    ``d = (instant AT TIME ZONE 'Asia/Kolkata')::date``; the start year is
    ``year(d)`` from April, ``year(d) - 1`` before it (ADR-0022 §3).
    """
    local = func.timezone(IST_ZONE, instant)
    year = sql_cast(extract("year", local), Integer)
    month = sql_cast(extract("month", local), Integer)
    return case((month >= FINANCIAL_YEAR_FIRST_MONTH, year), else_=year - 1)


PERIOD_EXPRESSIONS = {
    Period.CALENDAR_YEAR_UTC: calendar_year_period,
    Period.FINANCIAL_YEAR_IST: financial_year_period,
}


async def next_number(db: AsyncSession, name: SequenceName) -> str:
    """The next number of ``name`` for the current tenant and period, e.g. ``APP-2026-00001``."""
    tenant_id = current_context().tenant_id
    if tenant_id is None:
        raise RuntimeError("numbers are issued only with a trusted tenant")
    clock = await db.scalar(select(PERIOD_EXPRESSIONS[PERIODS[name]](func.now())))
    if clock is None:  # pragma: no cover - now() is never NULL
        raise RuntimeError("the database clock gave no period")
    period = int(clock)
    statement = (
        insert(SEQUENCES)
        .values(id=new_id(), tenant_id=tenant_id, name=name.value, period=period, last_value=1)
        .on_conflict_do_update(
            index_elements=["tenant_id", "name", "period"],
            set_={"last_value": SEQUENCES.c.last_value + 1, "updated_at": func.now()},
        )
        .returning(SEQUENCES.c.last_value)
    )
    value = int((await db.execute(statement)).scalar_one())
    return format_number(name, period, value)
