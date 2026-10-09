"""Application rules (Phase 02-2; ADR-0021 §3-§4, INC-47). Pure: no I/O.

* Statuses are the APP-FLOW §16 set. ``DOCUMENT_VERIFICATION`` and
  ``ELIGIBLE`` are reserved (in the database CHECK, never set): verification
  is tracked per document and eligibility is part of the review decision.
* Staff edit an application only while it is ``DRAFT`` or
  ``CORRECTION_REQUIRED``; ``submit`` sends it for review; reviewers decide
  through :data:`REVIEW_TRANSITIONS`; ``admit`` is the only way to
  ``ADMITTED``.
* Contact details reuse the lead rules (mobile key, normalised email), so a
  student can later be matched on the same keys.
"""

import re
from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from typing import Any, Final

from app.core.transitions import TransitionTable

NAME_MAX_LENGTH: Final = 200
ADDRESS_MAX_LENGTH: Final = 500
CITY_MAX_LENGTH: Final = 120
STATE_MAX_LENGTH: Final = 120
POSTAL_CODE_MAX_LENGTH: Final = 16
QUALIFICATION_MAX_LENGTH: Final = 200
TEXT_MAX_LENGTH: Final = 2000
REASON_MAX_LENGTH: Final = 500
NUMBER_MAX_LENGTH: Final = 32
INDOS_PATTERN: Final = "^[A-Z0-9]{6,16}$"
CDC_PATTERN: Final = "^[A-Z0-9][A-Z0-9/-]{3,31}$"
POSTAL_PATTERN: Final = "^[A-Za-z0-9][A-Za-z0-9 -]{1,15}$"
_INDOS = re.compile(INDOS_PATTERN)
_CDC = re.compile(CDC_PATTERN)
_POSTAL = re.compile(POSTAL_PATTERN)


class ApplicationStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    DOCUMENT_VERIFICATION = "DOCUMENT_VERIFICATION"
    """Reserved (INC-47): verification is tracked per document."""
    ELIGIBLE = "ELIGIBLE"
    """Reserved (INC-47): eligibility is part of the review decision."""
    CORRECTION_REQUIRED = "CORRECTION_REQUIRED"
    APPROVED = "APPROVED"
    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"


INITIAL_STATUS: Final = ApplicationStatus.DRAFT
EDITABLE: Final = frozenset({ApplicationStatus.DRAFT, ApplicationStatus.CORRECTION_REQUIRED})
"""Staff may change the details, course and campus, and submit."""
IN_REVIEW: Final = frozenset({ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW})
DOCUMENTS_OPEN: Final = EDITABLE | IN_REVIEW
"""Documents may be uploaded or replaced."""
CLOSED: Final = frozenset({ApplicationStatus.REJECTED, ApplicationStatus.NOT_ELIGIBLE})
FINAL: Final = CLOSED | {ApplicationStatus.ADMITTED}
REASON_REQUIRED: Final = frozenset(
    {
        ApplicationStatus.CORRECTION_REQUIRED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.NOT_ELIGIBLE,
    }
)

_DECISIONS: Final = frozenset(
    {
        ApplicationStatus.APPROVED,
        ApplicationStatus.CORRECTION_REQUIRED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.NOT_ELIGIBLE,
    }
)
REVIEW_TRANSITIONS: Final = TransitionTable[ApplicationStatus](
    {
        ApplicationStatus.SUBMITTED: _DECISIONS | {ApplicationStatus.UNDER_REVIEW},
        ApplicationStatus.UNDER_REVIEW: _DECISIONS,
    }
)
"""Moves a reviewer may make (``POST /applications/{id}/review``)."""


class ReviewProblem(StrEnum):
    INVALID = "invalid_transition"
    REASON_REQUIRED = "reason_required"
    DOCUMENTS_PENDING = "documents_not_verified"


def review_problem(
    current: ApplicationStatus,
    target: ApplicationStatus,
    *,
    reason: str | None,
    unverified_documents: int,
) -> ReviewProblem | None:
    """Why a reviewer may not move ``current`` → ``target`` (``None`` when allowed).

    Approval needs every current document verified (ADR-0021 Y4: no checklist,
    so an application without documents may be approved)."""
    if not REVIEW_TRANSITIONS.allows(current, target):
        return ReviewProblem.INVALID
    if target in REASON_REQUIRED and not reason:
        return ReviewProblem.REASON_REQUIRED
    if target is ApplicationStatus.APPROVED and unverified_documents:
        return ReviewProblem.DOCUMENTS_PENDING
    return None


class ActivityKind(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    SUBMITTED = "SUBMITTED"
    STATUS_CHANGED = "STATUS_CHANGED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_VERIFIED = "DOCUMENT_VERIFIED"
    DOCUMENT_REJECTED = "DOCUMENT_REJECTED"
    ADMITTED = "ADMITTED"


DETAIL_FIELDS: Final = (
    "full_name",
    "date_of_birth",
    "mobile",
    "email",
    "address",
    "city",
    "state",
    "postal_code",
    "highest_qualification",
    "education_details",
    "indos_number",
    "cdc_number",
    "eligibility_notes",
)
"""The applicant's details as entered (``PATCH``; prefilled from a lead on create)."""
LEAD_PREFILL: Final = (
    "full_name",
    "mobile",
    "email",
    "date_of_birth",
    "city",
    "highest_qualification",
)
"""Fields copied from the lead when the request leaves them out (ADR-0021 §3)."""
SUBMIT_REQUIRED: Final = ("full_name", "date_of_birth", "highest_qualification")
"""Plus a contact (mobile or email) and the declaration."""


def clean_identifier(raw: str | None, pattern: re.Pattern[str]) -> str | None:
    """Upper-cased, spaces removed; ``None`` when empty; ``ValueError`` when malformed."""
    if raw is None:
        return None
    value = "".join(raw.split()).upper()
    if not value:
        return None
    if not pattern.fullmatch(value):
        raise ValueError("malformed identifier")
    return value


def clean_indos(raw: str | None) -> str | None:
    """An INDoS number (the Indian seafarer database number): 6-16 letters and digits."""
    return clean_identifier(raw, _INDOS)


def clean_cdc(raw: str | None) -> str | None:
    """A Continuous Discharge Certificate number: letters, digits, ``/`` and ``-``."""
    return clean_identifier(raw, _CDC)


def clean_postal_code(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = " ".join(raw.split())
    if not value:
        return None
    if not _POSTAL.fullmatch(value):
        raise ValueError("malformed postal code")
    return value


def missing_for_submit(values: Mapping[str, Any], *, declared: bool) -> list[str]:
    """The fields that must be completed before the application can be submitted."""
    missing = [field for field in SUBMIT_REQUIRED if not values.get(field)]
    if not values.get("mobile") and not values.get("email"):
        missing.append("contact")
    if not declared:
        missing.append("declaration")
    return missing


def birth_date_plausible(value: date | None, today: date) -> bool:
    """In the past and after 1900 (the lead rule)."""
    return value is None or date(1900, 1, 1) <= value < today
