"""Transactional outbox (Phase 02-4, ADR-0024).

* :class:`OutboxMessage` — the ``outbox_messages`` table (migration ``0012``);
* :mod:`.store` — enqueue in the business transaction; claim, mark sent or retry
  (the worker, ``python -m app.worker``);
* :class:`OutboxSignal` — the Redis wake-up hint;
* :mod:`.states` — statuses and the retry schedule.
"""

from app.core.outbox.models import OutboxMessage
from app.core.outbox.signal import OutboxSignal
from app.core.outbox.states import OutboxStatus, error_name, retry_delay
from app.core.outbox.store import (
    Claimed,
    claim,
    enqueue,
    fail_exhausted,
    mark_retry,
    mark_sent,
)

__all__ = [
    "Claimed",
    "OutboxMessage",
    "OutboxSignal",
    "OutboxStatus",
    "claim",
    "enqueue",
    "error_name",
    "fail_exhausted",
    "mark_retry",
    "mark_sent",
    "retry_delay",
]
