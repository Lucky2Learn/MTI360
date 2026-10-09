"""Business activity timelines (Phase 02-1; ADR-0020 §8).

A user-visible, append-only history of one business record (a lead today; an
application or a student later). Each record type has its **own** table with
real composite tenant foreign keys (``lead_activities``, …), never one
polymorphic table, and this helper writes all of them the same way:

* in the caller's transaction, so the change and its activity commit together;
* the tenant comes from the trusted context, never from arguments;
* ``details`` holds code-chosen keys with statuses, IDs, field names, counts
  and short reasons; personal values (names, mobiles, emails) never go there.

Activity is not audit: ``audit_events`` (ADR-0013) records security and
administration facts for auditors; activity is the work history staff read.
"""

import json
import re
import uuid
from collections.abc import Mapping
from typing import Any, Final

from sqlalchemy import Table, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import current_context
from app.core.ids import new_id

MAX_DETAIL_BYTES: Final = 4096
MAX_DETAIL_KEYS: Final = 16
_KEY = re.compile(r"[a-z][a-z0-9_]{0,63}")

type DetailValue = str | int | bool | list[str] | None


class ActivityDetailsError(ValueError):
    """Details that break the contract (a programming error). Never echoes values."""


def activity_details(values: Mapping[str, object]) -> dict[str, DetailValue]:
    """Validated ``details``: flat, small, JSON-safe; UUIDs stored as text."""
    if len(values) > MAX_DETAIL_KEYS:
        raise ActivityDetailsError("too many activity detail keys")
    result: dict[str, DetailValue] = {}
    for key, value in values.items():
        if not _KEY.fullmatch(key):
            raise ActivityDetailsError("activity detail key is not a lower-case identifier")
        if isinstance(value, uuid.UUID):
            result[key] = str(value)
        elif value is None or isinstance(value, str | bool | int):
            result[key] = value
        elif isinstance(value, list | tuple) and all(isinstance(item, str) for item in value):
            result[key] = [str(item) for item in value]
        else:
            raise ActivityDetailsError(f"unsupported activity detail value for {key!r}")
    if len(json.dumps(result).encode()) > MAX_DETAIL_BYTES:
        raise ActivityDetailsError("activity details are too large")
    return result


async def record_activity(
    db: AsyncSession,
    table: Table,
    *,
    subject_column: str,
    subject_id: uuid.UUID,
    kind: str,
    actor_membership_id: uuid.UUID | None,
    details: Mapping[str, object] | None = None,
    body: str | None = None,
) -> uuid.UUID:
    """Append one activity row to ``table`` in the current transaction; return its ID."""
    tenant_id = current_context().tenant_id
    if tenant_id is None:
        raise RuntimeError("activity is recorded only with a trusted tenant")
    row: dict[str, Any] = {
        "id": new_id(),
        "tenant_id": tenant_id,
        subject_column: subject_id,
        "kind": kind,
        "actor_membership_id": actor_membership_id,
        "details": activity_details(details or {}),
    }
    if body is not None:  # only timelines with notes have a body column (Phase 02-2)
        row["body"] = body
    await db.execute(insert(table).values(**row))
    return row["id"]  # type: ignore[no-any-return]
