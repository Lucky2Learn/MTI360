"""Student, admission and numbering rules (Phase 02-2; ADR-0021 §2, §6-§7). Pure: no I/O.

* A **student** is the person across courses; an **admission** is the
  decision for one application. Both carry a campus (L6).
* Numbers come from per-tenant, per-year sequences and read
  ``<PREFIX>-<YYYY>-<nnnnn>`` (wider when a year exceeds 99 999).
"""

from enum import StrEnum
from typing import Final


class SequenceName(StrEnum):
    APPLICATION = "APPLICATION"
    ADMISSION = "ADMISSION"
    STUDENT = "STUDENT"


PREFIXES: Final = {
    SequenceName.APPLICATION: "APP",
    SequenceName.ADMISSION: "ADM",
    SequenceName.STUDENT: "STU",
}
NUMBER_DIGITS: Final = 5
NUMBER_MAX_LENGTH: Final = 32


def format_number(name: SequenceName, year: int, value: int) -> str:
    """``APP-2026-00001``; the counter widens past 99 999 instead of wrapping."""
    if value < 1 or not 2000 <= year <= 9999:
        raise ValueError("sequence value out of range")
    return f"{PREFIXES[name]}-{year}-{value:0{NUMBER_DIGITS}d}"


class StudentStatus(StrEnum):
    ACTIVE = "ACTIVE"


class AdmissionStatus(StrEnum):
    ADMITTED = "ADMITTED"
    """``ENROLLED`` and ``CANCELLED`` arrive with batches and finance (L3)."""


class StudentChoice(StrEnum):
    """How the approver resolves the person at admission (ADR-0021 Y6): never automatic."""

    NEW = "new"
    EXISTING = "existing"


STUDENT_CANDIDATE_LIMIT: Final = 5
