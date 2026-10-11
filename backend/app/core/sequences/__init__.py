"""Per-tenant document number sequences (ADR-0021 §7; ADR-0022 §3).

* :func:`next_number` — the next gap-free number, in the caller's transaction;
* :mod:`.numbering` — the sequence names, prefixes, period kinds and formats;
* :class:`TenantSequence` — the ``tenant_sequences`` table (migration ``0010``).
"""

from app.core.sequences.allocator import (
    calendar_year_period,
    financial_year_period,
    next_number,
)
from app.core.sequences.models import TenantSequence
from app.core.sequences.numbering import (
    NUMBER_MAX_LENGTH,
    Period,
    SequenceName,
    financial_year_label,
    financial_year_of,
    financial_year_start,
    format_number,
)

__all__ = [
    "NUMBER_MAX_LENGTH",
    "Period",
    "SequenceName",
    "TenantSequence",
    "calendar_year_period",
    "financial_year_label",
    "financial_year_of",
    "financial_year_period",
    "financial_year_start",
    "format_number",
    "next_number",
]
