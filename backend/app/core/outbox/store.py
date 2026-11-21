"""Outbox persistence: enqueue in the business transaction, then claim and settle.

* :func:`enqueue` runs in the caller's transaction with its trusted tenant;
  a repeated idempotency key adds nothing.
* The worker's statements run in the **system realm** (``system_context``
  without a tenant; the ``outbox_messages_system`` policy). They are Core
  statements, so the tenant ORM filter does not apply; Row-Level Security does.
* :func:`claim` takes up to ``limit`` ready messages with
  ``FOR UPDATE SKIP LOCKED``, so concurrent workers never take the same one.
  ``PROCESSING`` messages whose lock is older than ``stale_after`` (a crashed
  worker) are taken again; with no attempt left they become ``FAILED``.
* :func:`mark_sent` and :func:`mark_retry` are **fenced**: they change the
  message only if it is still locked by this worker with this claim's
  ``locked_at``. A worker whose claim was taken over changes nothing.

Delivery is at least once: a worker that sends and then crashes before
:func:`mark_sent` leaves the message to be sent again after ``stale_after``.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import Table, and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import current_context
from app.core.ids import new_id
from app.core.outbox.models import OutboxMessage
from app.core.outbox.states import OutboxStatus

MESSAGES = cast(Table, OutboxMessage.__table__)


@dataclass(frozen=True, slots=True)
class Claimed:
    id: uuid.UUID
    tenant_id: uuid.UUID
    kind: str
    payload: Mapping[str, Any]
    attempts: int
    """Including this one."""
    max_attempts: int
    locked_by: str
    locked_at: datetime


async def enqueue(
    db: AsyncSession,
    *,
    kind: str,
    idempotency_key: str,
    payload: Mapping[str, Any],
    max_attempts: int,
) -> bool:
    """Add a ``PENDING`` message for the current tenant; ``False`` if the key exists."""
    tenant_id = current_context().tenant_id
    if tenant_id is None:
        raise RuntimeError("outbox messages are enqueued only with a trusted tenant")
    inserted = await db.execute(
        insert(MESSAGES)
        .values(
            id=new_id(),
            tenant_id=tenant_id,
            kind=kind,
            idempotency_key=idempotency_key,
            payload=dict(payload),
            max_attempts=max_attempts,
        )
        .on_conflict_do_nothing(index_elements=["tenant_id", "idempotency_key"])
        .returning(MESSAGES.c.id)
    )
    return inserted.first() is not None


async def fail_exhausted(db: AsyncSession, *, now: datetime, stale_after: timedelta) -> int:
    """Stale ``PROCESSING`` messages with no attempt left become ``FAILED``; return how many."""
    result = await db.execute(
        update(MESSAGES)
        .where(
            MESSAGES.c.status == OutboxStatus.PROCESSING.value,
            MESSAGES.c.locked_at < now - stale_after,
            MESSAGES.c.attempts >= MESSAGES.c.max_attempts,
        )
        .values(
            status=OutboxStatus.FAILED.value,
            failed_at=now,
            last_error="StaleProcessing",
            locked_at=None,
            locked_by=None,
            updated_at=now,
        )
        .returning(MESSAGES.c.id)
    )
    return len(result.all())


async def claim(
    db: AsyncSession,
    *,
    worker: str,
    limit: int,
    now: datetime,
    stale_after: timedelta,
) -> list[Claimed]:
    """Lock up to ``limit`` ready or stale messages for ``worker`` (see the module docs)."""
    ready = (
        select(MESSAGES.c.id)
        .where(
            or_(
                and_(
                    MESSAGES.c.status == OutboxStatus.PENDING.value,
                    MESSAGES.c.available_at <= now,
                ),
                and_(
                    MESSAGES.c.status == OutboxStatus.PROCESSING.value,
                    MESSAGES.c.locked_at < now - stale_after,
                    MESSAGES.c.attempts < MESSAGES.c.max_attempts,
                ),
            )
        )
        .order_by(MESSAGES.c.available_at, MESSAGES.c.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    rows = await db.execute(
        update(MESSAGES)
        .where(MESSAGES.c.id.in_(ready))
        .values(
            status=OutboxStatus.PROCESSING.value,
            attempts=MESSAGES.c.attempts + 1,
            locked_at=now,
            locked_by=worker,
            updated_at=now,
        )
        .returning(
            MESSAGES.c.id,
            MESSAGES.c.tenant_id,
            MESSAGES.c.kind,
            MESSAGES.c.payload,
            MESSAGES.c.attempts,
            MESSAGES.c.max_attempts,
            MESSAGES.c.locked_by,
            MESSAGES.c.locked_at,
        )
    )
    claimed = [Claimed(*row) for row in rows.all()]
    return sorted(claimed, key=lambda message: (message.locked_at, message.id))


def _fenced(message: Claimed) -> Any:
    return and_(
        MESSAGES.c.id == message.id,
        MESSAGES.c.status == OutboxStatus.PROCESSING.value,
        MESSAGES.c.locked_by == message.locked_by,
        MESSAGES.c.locked_at == message.locked_at,
    )


async def mark_sent(db: AsyncSession, message: Claimed, *, now: datetime) -> bool:
    """``SENT``; ``False`` when the claim was lost (nothing changes)."""
    result = await db.execute(
        update(MESSAGES)
        .where(_fenced(message))
        .values(
            status=OutboxStatus.SENT.value,
            sent_at=now,
            last_error=None,
            locked_at=None,
            locked_by=None,
            updated_at=now,
        )
        .returning(MESSAGES.c.id)
    )
    return result.first() is not None


async def mark_retry(
    db: AsyncSession,
    message: Claimed,
    *,
    now: datetime,
    error: str,
    retry_at: datetime | None,
) -> OutboxStatus | None:
    """Back to ``PENDING`` at ``retry_at``, or ``FAILED`` when ``retry_at`` is ``None``
    or no attempt is left. ``None`` when the claim was lost (nothing changes)."""
    exhausted = retry_at is None or message.attempts >= message.max_attempts
    status = OutboxStatus.FAILED if exhausted else OutboxStatus.PENDING
    result = await db.execute(
        update(MESSAGES)
        .where(_fenced(message))
        .values(
            status=status.value,
            last_error=error,
            available_at=func.coalesce(retry_at, MESSAGES.c.available_at),
            failed_at=now if exhausted else None,
            locked_at=None,
            locked_by=None,
            updated_at=now,
        )
        .returning(MESSAGES.c.id)
    )
    return status if result.first() is not None else None
