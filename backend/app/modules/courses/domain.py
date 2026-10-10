"""Course rules (Phase 02-1; blueprint §4-§5). Pure: no I/O, no framework imports."""

import re
from enum import StrEnum
from typing import Final

from app.core.transitions import TransitionTable

CODE_PATTERN: Final = "^[A-Z0-9][A-Z0-9-]*$"
"""The campus-code format (INC-41): upper case, digits and hyphens."""
CODE_MAX_LENGTH: Final = 32
NAME_MAX_LENGTH: Final = 200
TEXT_MAX_LENGTH: Final = 2000
DURATION_MAX: Final = 1000
_CODE = re.compile(CODE_PATTERN)


class CourseCategory(StrEnum):
    PRE_SEA = "PRE_SEA"
    POST_SEA = "POST_SEA"
    OTHER = "OTHER"


class CourseStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class DurationUnit(StrEnum):
    DAYS = "DAYS"
    WEEKS = "WEEKS"
    MONTHS = "MONTHS"
    YEARS = "YEARS"


INITIAL_STATUS: Final = CourseStatus.DRAFT

COURSE_TRANSITIONS: Final = TransitionTable[CourseStatus](
    {
        CourseStatus.DRAFT: {CourseStatus.ACTIVE, CourseStatus.ARCHIVED},
        CourseStatus.ACTIVE: {CourseStatus.ARCHIVED},
        CourseStatus.ARCHIVED: {CourseStatus.ACTIVE},
    }
)


def normalize_code(raw: str) -> str | None:
    """The canonical code (trimmed, upper case), or ``None`` when the format is wrong."""
    code = raw.strip().upper()
    if not code or len(code) > CODE_MAX_LENGTH or not _CODE.fullmatch(code):
        return None
    return code


def clean_name(raw: str) -> str | None:
    """Whitespace-collapsed name of 1-200 characters, or ``None``."""
    name = " ".join(raw.split())
    return name if 0 < len(name) <= NAME_MAX_LENGTH else None


def clean_text(raw: str | None) -> str | None:
    """Optional free text: trimmed; empty becomes ``None``. Length is checked by the caller."""
    if raw is None:
        return None
    text = raw.strip()
    return text or None


def duration_valid(value: int | None, unit: DurationUnit | None) -> bool:
    """Both set (1 to 1000) or both empty."""
    if value is None and unit is None:
        return True
    return value is not None and unit is not None and 0 < value <= DURATION_MAX
