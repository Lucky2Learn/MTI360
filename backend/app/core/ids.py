"""Identifier generation (T01-01; tenancy.md §9).

Primary keys are application-generated UUIDv7 values: globally unique, roughly
time-ordered (good B-tree locality) and not guessable in sequence. Sequential
database IDs are never exposed. Human-facing numbers (for example admission
numbers) are separate per-tenant sequences owned by their module.
"""

import uuid


def new_id() -> uuid.UUID:
    """Return a new UUIDv7 (Python 3.14 standard library, RFC 9562)."""
    return uuid.uuid7()
