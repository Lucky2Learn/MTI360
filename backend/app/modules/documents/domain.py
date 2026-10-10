"""Application document rules (Phase 02-2; ADR-0021 §5, PRD §39). Pure: no I/O.

* Types are a fixed list (ADR-0021 Y4; per-course checklists are deferred).
* ``UPLOADED`` (the application is a draft or back for correction) →
  ``UNDER_REVIEW`` (submitted) → ``VERIFIED`` or ``REJECTED`` (reason).
* A document is never deleted: a re-upload is a new row that replaces it.
  A verified document cannot be replaced.
"""

from enum import StrEnum
from typing import Final

from app.core.transitions import TransitionTable

REASON_MAX_LENGTH: Final = 500


class DocumentType(StrEnum):
    PASSPORT = "PASSPORT"
    CDC = "CDC"
    INDOS = "INDOS"
    MARKSHEET_10 = "MARKSHEET_10"
    MARKSHEET_12 = "MARKSHEET_12"
    MEDICAL_CERTIFICATE = "MEDICAL_CERTIFICATE"
    PHOTO = "PHOTO"
    ID_PROOF = "ID_PROOF"
    OTHER = "OTHER"


class DocumentStatus(StrEnum):
    UPLOADED = "UPLOADED"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


VERIFICATION: Final = TransitionTable[DocumentStatus](
    {DocumentStatus.UNDER_REVIEW: {DocumentStatus.VERIFIED, DocumentStatus.REJECTED}}
)
"""Verifier decisions: only a document under review is decided."""
REPLACEABLE: Final = frozenset(
    {DocumentStatus.UPLOADED, DocumentStatus.UNDER_REVIEW, DocumentStatus.REJECTED}
)
NOT_VERIFIED: Final = REPLACEABLE
"""Current documents that block approval of the application."""
