"""The database computes the same periods as the documented rule (ADR-0021 §7; ADR-0022 §3).

The allocator takes the period from PostgreSQL's clock with the
``Asia/Kolkata`` time zone; the Python rule uses a fixed UTC+05:30 offset.
Both must agree at the financial-year boundary and across a whole year.
"""

from datetime import UTC, datetime, timedelta

import pytest
from conftest import DatabaseUnderTest
from sqlalchemy import DateTime, literal, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.sequences import calendar_year_period, financial_year_of, financial_year_period
from app.core.sequences.numbering import calendar_year_of

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

BOUNDARIES = (
    datetime(2027, 3, 31, 18, 29, 59, 999999, tzinfo=UTC),
    datetime(2027, 3, 31, 18, 30, tzinfo=UTC),
    datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC),
    datetime(2027, 1, 1, tzinfo=UTC),
    datetime(2099, 3, 31, 18, 30, tzinfo=UTC),
)


def _sweep() -> list[datetime]:
    """Every six hours of 2026-27, offset so that some samples fall just before midnight IST."""
    start = datetime(2026, 3, 30, 18, 29, 30, tzinfo=UTC)
    return [start + timedelta(hours=6 * step) for step in range(4 * 368)]


async def test_the_database_matches_the_financial_and_calendar_year_rules(
    test_database: DatabaseUnderTest,
) -> None:
    instants = (*BOUNDARIES, *_sweep())
    engine = create_async_engine(test_database.app_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            for instant in instants:
                value = literal(instant, DateTime(timezone=True))
                row = (
                    await connection.execute(
                        select(financial_year_period(value), calendar_year_period(value))
                    )
                ).one()
                assert (row[0], row[1]) == (
                    financial_year_of(instant),
                    calendar_year_of(instant),
                ), instant
    finally:
        await engine.dispose()
