"""Human-facing document numbers (ADR-0021 §7; ADR-0022 §3). Pure: no I/O.

Two kinds of period share ``tenant_sequences.period``:

* **calendar year (UTC)** — applications, admissions and students:
  ``APP-2026-00001`` (ADR-0021 §7, unchanged);
* **Indian financial year (IST)** — fee invoices and receipts:
  ``INV-FY2026-27-00001``. The period is the FY's starting calendar year;
  FY2026-27 runs from 2026-04-01 00:00 to 2027-03-31 23:59:59.999999 IST.

The counter has five digits and widens past 99 999 instead of wrapping. The
database computes the period from its own clock (:mod:`.allocator`); the
functions here format it and state the boundary rule for tests and callers.
"""

from datetime import UTC, date, datetime, timedelta, timezone
from enum import Enum, StrEnum
from typing import Final


class SequenceName(StrEnum):
    APPLICATION = "APPLICATION"
    ADMISSION = "ADMISSION"
    STUDENT = "STUDENT"


class Period(Enum):
    CALENDAR_YEAR_UTC = "calendar_year_utc"
    FINANCIAL_YEAR_IST = "financial_year_ist"


PREFIXES: Final = {
    SequenceName.APPLICATION: "APP",
    SequenceName.ADMISSION: "ADM",
    SequenceName.STUDENT: "STU",
}
PERIODS: Final = {
    SequenceName.APPLICATION: Period.CALENDAR_YEAR_UTC,
    SequenceName.ADMISSION: Period.CALENDAR_YEAR_UTC,
    SequenceName.STUDENT: Period.CALENDAR_YEAR_UTC,
}
NUMBER_DIGITS: Final = 5
NUMBER_MAX_LENGTH: Final = 32
FINANCIAL_YEAR_FIRST_MONTH: Final = 4  # April
# India Standard Time: UTC+05:30, no daylight saving since 1945. A fixed offset
# keeps Python free of time-zone data; the database uses 'Asia/Kolkata'.
IST: Final = timezone(timedelta(hours=5, minutes=30), "IST")
IST_ZONE: Final = "Asia/Kolkata"
PERIOD_MIN: Final = 2000
PERIOD_MAX: Final = 9999


def financial_year_start(day: date) -> int:
    """The starting calendar year of the Indian financial year of ``day`` (a local date)."""
    return day.year if day.month >= FINANCIAL_YEAR_FIRST_MONTH else day.year - 1


def financial_year_of(instant: datetime) -> int:
    """The financial year (start year) of an aware ``instant``, taken in IST."""
    if instant.tzinfo is None:
        raise ValueError("instant must be timezone-aware")
    return financial_year_start(instant.astimezone(IST).date())


def financial_year_label(start: int) -> str:
    """``FY2026-27`` for the financial year starting in April 2026."""
    _check_period(start)
    return f"FY{start}-{(start + 1) % 100:02d}"


def format_number(name: SequenceName, period: int, value: int) -> str:
    """``APP-2026-00001`` or ``INV-FY2026-27-00001``, by the sequence's period kind."""
    _check_period(period)
    if value < 1:
        raise ValueError("sequence value out of range")
    label = (
        str(period) if PERIODS[name] is Period.CALENDAR_YEAR_UTC else financial_year_label(period)
    )
    return f"{PREFIXES[name]}-{label}-{value:0{NUMBER_DIGITS}d}"


def calendar_year_of(instant: datetime) -> int:
    """The calendar year (UTC) of an aware ``instant``."""
    if instant.tzinfo is None:
        raise ValueError("instant must be timezone-aware")
    return instant.astimezone(UTC).year


def _check_period(period: int) -> None:
    if not PERIOD_MIN <= period <= PERIOD_MAX:
        raise ValueError("sequence value out of range")
