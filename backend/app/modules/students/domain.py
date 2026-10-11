"""Student, admission and numbering rules (Phase 02-2; ADR-0021 §2, §6-§7). Pure: no I/O.

* A **student** is the person across courses; an **admission** is the
  decision for one application. Both carry a campus (L6).
* Numbers come from the per-tenant sequences of :mod:`app.core.sequences`
  and read ``<PREFIX>-<YYYY>-<nnnnn>`` (wider when a year exceeds 99 999).
"""

from enum import StrEnum
from typing import Final


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
