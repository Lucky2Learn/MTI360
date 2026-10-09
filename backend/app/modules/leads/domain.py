"""Lead rules (Phase 02-1; blueprint §7-§11, ADR-0020 §3-§5). Pure: no I/O.

* Statuses are the APP-FLOW §10 set (INC-44). ``APPLICATION`` and
  ``ADMITTED`` are set only by the application flow (02-2) through
  :data:`APPLICATION_START`, never by the transition endpoint.
* Duplicate keys: ``email_normalized`` (trimmed, lower case) and
  ``mobile_key`` (the last 10 digits). They only produce a warning.
"""

import re
from datetime import date
from enum import StrEnum
from typing import Final

from app.core.transitions import TransitionTable
from app.modules.identity.domain import InvalidEmailError, normalize_email

NAME_MAX_LENGTH: Final = 200
MOBILE_MAX_LENGTH: Final = 32
MOBILE_KEY_LENGTH: Final = 10
MOBILE_MIN_DIGITS: Final = 6
MOBILE_MAX_DIGITS: Final = 15
EMAIL_MAX_LENGTH: Final = 254
CITY_MAX_LENGTH: Final = 120
QUALIFICATION_MAX_LENGTH: Final = 200
REASON_MAX_LENGTH: Final = 500
NOTE_MAX_LENGTH: Final = 4000
FOLLOW_UP_TEXT_MAX_LENGTH: Final = 1000
EARLIEST_BIRTH_DATE: Final = date(1900, 1, 1)
DUPLICATE_CANDIDATE_LIMIT: Final = 5
_MOBILE = re.compile(r"[0-9+\-() ]+")


class LeadStatus(StrEnum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    COUNSELLING = "COUNSELLING"
    INTERESTED = "INTERESTED"
    APPLICATION = "APPLICATION"
    ADMITTED = "ADMITTED"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    LOST = "LOST"
    DEFERRED = "DEFERRED"
    DUPLICATE = "DUPLICATE"


PIPELINE: Final = (
    LeadStatus.NEW,
    LeadStatus.CONTACTED,
    LeadStatus.QUALIFIED,
    LeadStatus.COUNSELLING,
    LeadStatus.INTERESTED,
)
"""The open statuses in pipeline order (the board columns)."""
OPEN_STATUSES: Final = frozenset(PIPELINE)
PROGRESSED_STATUSES: Final = frozenset({LeadStatus.APPLICATION, LeadStatus.ADMITTED})
CLOSED_STATUSES: Final = frozenset(
    {LeadStatus.NOT_ELIGIBLE, LeadStatus.LOST, LeadStatus.DEFERRED, LeadStatus.DUPLICATE}
)
REASON_REQUIRED: Final = frozenset({LeadStatus.NOT_ELIGIBLE, LeadStatus.LOST, LeadStatus.DEFERRED})
INITIAL_STATUS: Final = LeadStatus.NEW


def _staff_moves() -> dict[LeadStatus, set[LeadStatus]]:
    moves: dict[LeadStatus, set[LeadStatus]] = {}
    for status in OPEN_STATUSES:
        moves[status] = set(OPEN_STATUSES | CLOSED_STATUSES)
    for status in CLOSED_STATUSES:
        moves[status] = set(OPEN_STATUSES)  # reopen
    return moves


LEAD_TRANSITIONS: Final = TransitionTable[LeadStatus](_staff_moves())
"""Moves staff may make (``POST /leads/{id}/transition``): never to or from
``APPLICATION`` / ``ADMITTED``, never between two closed statuses."""

APPLICATION_START: Final = TransitionTable[LeadStatus](
    {status: {LeadStatus.APPLICATION} for status in OPEN_STATUSES}
)
"""The system move of 02-2: an application was started for an open lead."""


class TransitionProblem(StrEnum):
    INVALID = "invalid_transition"
    REASON_REQUIRED = "reason_required"
    DUPLICATE_TARGET = "duplicate_target_invalid"


def transition_problem(
    current: LeadStatus, target: LeadStatus, *, reason: str | None, has_duplicate_target: bool
) -> TransitionProblem | None:
    """Why staff may not move ``current`` → ``target`` (``None`` when allowed).

    Closing as not eligible, lost or deferred, and reopening a closed lead,
    need a reason; closing as a duplicate needs the other lead.
    """
    if not LEAD_TRANSITIONS.allows(current, target):
        return TransitionProblem.INVALID
    if target is LeadStatus.DUPLICATE and not has_duplicate_target:
        return TransitionProblem.DUPLICATE_TARGET
    if (target in REASON_REQUIRED or current in CLOSED_STATUSES) and not reason:
        return TransitionProblem.REASON_REQUIRED
    return None


class LeadSource(StrEnum):
    WEBSITE = "WEBSITE"
    WHATSAPP = "WHATSAPP"
    PHONE = "PHONE"
    WALK_IN = "WALK_IN"
    INSTAGRAM = "INSTAGRAM"
    FACEBOOK = "FACEBOOK"
    YOUTUBE = "YOUTUBE"
    GOOGLE = "GOOGLE"
    REFERRAL = "REFERRAL"
    EDUCATION_PORTAL = "EDUCATION_PORTAL"
    OTHER = "OTHER"


class FollowUpKind(StrEnum):
    """Labels only: nothing is sent (no communication in 02-1)."""

    CALL = "CALL"
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"
    MEETING = "MEETING"
    VISIT = "VISIT"
    OTHER = "OTHER"


class FollowUpStatus(StrEnum):
    OPEN = "OPEN"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class ActivityKind(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    ASSIGNED = "ASSIGNED"
    FOLLOW_UP_SCHEDULED = "FOLLOW_UP_SCHEDULED"
    FOLLOW_UP_COMPLETED = "FOLLOW_UP_COMPLETED"
    FOLLOW_UP_CANCELLED = "FOLLOW_UP_CANCELLED"
    NOTE = "NOTE"
    APPLICATION_STARTED = "APPLICATION_STARTED"
    """An application was started from this lead (Phase 02-2; ADR-0021 §10)."""


class FollowUpFilter(StrEnum):
    OVERDUE = "overdue"
    TODAY = "today"
    UPCOMING = "upcoming"
    NONE = "none"


# --- Normalisation ----------------------------------------------------------------------


def clean_name(raw: str) -> str | None:
    """Whitespace-collapsed name of 1-200 characters, or ``None``."""
    name = " ".join(raw.split())
    return name if 0 < len(name) <= NAME_MAX_LENGTH else None


def clean_mobile(raw: str | None) -> str | None:
    """The mobile as entered (single spaces), ``None`` when empty; ``ValueError`` if implausible."""
    if raw is None or not raw.strip():
        return None
    mobile = " ".join(raw.split())
    digits = sum(character.isdigit() for character in mobile)
    if (
        len(mobile) > MOBILE_MAX_LENGTH
        or not _MOBILE.fullmatch(mobile)
        or not MOBILE_MIN_DIGITS <= digits <= MOBILE_MAX_DIGITS
    ):
        raise ValueError("not a phone number")
    return mobile


def mobile_key(mobile: str | None) -> str | None:
    """The last 10 digits (all digits when fewer), so ``+91 98200 12345`` = ``098200 12345``."""
    if mobile is None:
        return None
    digits = "".join(character for character in mobile if character.isdigit())
    return digits[-MOBILE_KEY_LENGTH:] or None


def search_digits(query: str) -> str | None:
    """The digits of a search term when it looks like a phone number (at least 4 digits)."""
    digits = "".join(character for character in query if character.isdigit())
    return digits if len(digits) >= 4 and not any(c.isalpha() for c in query) else None


def clean_email(raw: str | None) -> tuple[str, str] | None:
    """``(email as entered, normalized)``, ``None`` when empty; ``ValueError`` if invalid."""
    if raw is None or not raw.strip():
        return None
    entered = raw.strip()
    try:
        normalized = normalize_email(entered)
    except InvalidEmailError:
        raise ValueError("not an email address") from None
    return entered, normalized


def clean_optional(raw: str | None, max_length: int) -> str | None:
    """Optional single-line text, whitespace-collapsed; ``ValueError`` when too long."""
    if raw is None:
        return None
    value = " ".join(raw.split())
    if len(value) > max_length:
        raise ValueError("too long")
    return value or None


def clean_text(raw: str | None, max_length: int) -> str | None:
    """Optional multi-line text, trimmed; ``ValueError`` when too long."""
    if raw is None:
        return None
    value = raw.strip()
    if len(value) > max_length:
        raise ValueError("too long")
    return value or None


def birth_date_valid(value: date | None, today: date) -> bool:
    return value is None or EARLIEST_BIRTH_DATE <= value < today
