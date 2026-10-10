"""Document number formats and the Indian financial-year boundary (ADR-0021 §7; ADR-0022 §3)."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from app.core.sequences import (
    SequenceName,
    financial_year_label,
    financial_year_of,
    financial_year_start,
    format_number,
)
from app.core.sequences.numbering import IST, PERIODS, PREFIXES, Period, calendar_year_of


@pytest.mark.parametrize(
    ("day", "start"),
    [
        (date(2026, 4, 1), 2026),
        (date(2026, 12, 31), 2026),
        (date(2027, 1, 1), 2026),
        (date(2027, 3, 31), 2026),
        (date(2027, 4, 1), 2027),
        (date(2028, 2, 29), 2027),
    ],
)
def test_the_financial_year_starts_on_the_first_of_april(day: date, start: int) -> None:
    assert financial_year_start(day) == start


@pytest.mark.parametrize(
    ("instant", "start"),
    [
        # 31 March 23:59:59 IST and 1 April 00:00:00 IST (UTC+05:30).
        (datetime(2027, 3, 31, 18, 29, 59, tzinfo=UTC), 2026),
        (datetime(2027, 3, 31, 18, 29, 59, 999999, tzinfo=UTC), 2026),
        (datetime(2027, 3, 31, 18, 30, 0, tzinfo=UTC), 2027),
        # The UTC date is still 31 March, the IST date already 1 April.
        (datetime(2027, 3, 31, 20, 0, tzinfo=UTC), 2027),
        # The same instant expressed in another offset gives the same year.
        (datetime(2027, 4, 1, 0, 0, tzinfo=IST), 2027),
        (datetime(2027, 3, 31, 14, 0, tzinfo=timezone(timedelta(hours=-4, minutes=-30))), 2027),
    ],
)
def test_the_boundary_is_midnight_in_india(instant: datetime, start: int) -> None:
    assert financial_year_of(instant) == start


def test_the_ist_offset_is_fixed_at_five_and_a_half_hours() -> None:
    assert IST.utcoffset(None) == timedelta(hours=5, minutes=30)


def test_naive_instants_are_refused() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        financial_year_of(datetime(2027, 4, 1))  # noqa: DTZ001
    with pytest.raises(ValueError, match="timezone-aware"):
        calendar_year_of(datetime(2027, 1, 1))  # noqa: DTZ001


def test_the_calendar_year_is_taken_in_utc() -> None:
    assert calendar_year_of(datetime(2026, 12, 31, 23, 59, tzinfo=UTC)) == 2026
    assert calendar_year_of(datetime(2027, 1, 1, 3, 0, tzinfo=IST)) == 2026


@pytest.mark.parametrize(
    ("start", "label"),
    [(2026, "FY2026-27"), (2000, "FY2000-01"), (2009, "FY2009-10"), (2099, "FY2099-00")],
)
def test_financial_year_labels_name_both_years(start: int, label: str) -> None:
    assert financial_year_label(start) == label


@pytest.mark.parametrize("start", [1999, 10000])
def test_financial_year_labels_refuse_out_of_range_years(start: int) -> None:
    with pytest.raises(ValueError, match="out of range"):
        financial_year_label(start)


def test_existing_admissions_sequences_stay_on_the_calendar_year() -> None:
    assert {name: PERIODS[name] for name in SequenceName} == {
        SequenceName.APPLICATION: Period.CALENDAR_YEAR_UTC,
        SequenceName.ADMISSION: Period.CALENDAR_YEAR_UTC,
        SequenceName.STUDENT: Period.CALENDAR_YEAR_UTC,
    }
    assert set(PREFIXES) == set(SequenceName)
    assert format_number(SequenceName.APPLICATION, 2026, 7) == "APP-2026-00007"
