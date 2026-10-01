"""Security events: buffered during the request, committed after it (T01-02; ADR-0013 §5).

Security events (failed sign-in, denied access, lockout, …) must survive the
rollback of the request that caused them, so they cannot share its
transaction (T01-00 decision D22). They must also never hold a second
connection while the request transaction holds one: under a brute-force
attack every failing request would need two pooled connections. Hence:

1. :func:`record_security_event` validates the event (type, category,
   target, redacted metadata) and appends it to a request-local, in-memory
   buffer, with the trusted context of the request. No database access.
2. The request transaction commits or rolls back and releases its
   connection.
3. :func:`flush_security_events` writes the buffer in a fresh, short
   transaction with the same trusted context (``SET LOCAL``) and commits it.
4. The response is sent.

The realm guard (``app/api/realms.py``) opens :func:`security_event_scope`
as a function-scoped dependency, so its exit — the flush — runs after the
``DbSession`` dependency has finished and before the response, including
error responses.

A failed flush is logged without metadata or exception text and swallowed:
the response the request already determined is unchanged, nothing is
retried, and the committed request transaction stays committed. There is no
outbox, queue or retry in T01-02 (ADR-0013 §6).
"""

import logging
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Final

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit.events import AuditCategory, AuditEventType, AuditTarget
from app.core.audit.writer import AUDIT_TABLE, audit_row
from app.core.context import MissingContextError, RequestContext
from app.core.db.session import context_transaction

logger = logging.getLogger("app.audit")

MAX_BUFFERED_EVENTS: Final = 32
"""Per request. Further events are dropped and counted in the log."""


@dataclass(slots=True)
class SecurityEventBuffer:
    """The security events of one request, already validated and redacted."""

    context: RequestContext
    rows: list[dict[str, Any]] = field(default_factory=list)
    dropped: int = 0


_buffer: ContextVar[SecurityEventBuffer | None] = ContextVar("mti360_security_events", default=None)


def record_security_event(
    event_type: AuditEventType,
    *,
    target: AuditTarget | None = None,
    metadata: Mapping[str, object] | None = None,
) -> None:
    """Buffer a security event of the current request (no database access)."""
    buffer = _buffer.get()
    if buffer is None:
        raise MissingContextError("no security-event scope is open")
    row = audit_row(buffer.context, event_type, target=target, metadata=metadata)
    if event_type.category is not AuditCategory.SECURITY:
        raise ValueError("record_security_event() records security events only")
    if len(buffer.rows) >= MAX_BUFFERED_EVENTS:
        buffer.dropped += 1
        return
    buffer.rows.append(row)


async def flush_security_events(
    factory: async_sessionmaker[AsyncSession], buffer: SecurityEventBuffer
) -> None:
    """Commit the buffered events in a fresh transaction; never raises ``Exception``."""
    rows, buffer.rows = buffer.rows, []
    if buffer.dropped:
        logger.warning("audit.security_events_dropped", extra={"event_count": buffer.dropped})
        buffer.dropped = 0
    if not rows:
        return
    try:
        async with context_transaction(factory, buffer.context) as session:
            await session.execute(insert(AUDIT_TABLE), rows)
    except Exception as error:
        # Never the metadata, the SQL or the exception text (it can contain values).
        logger.error(
            "audit.security_flush_failed",
            extra={"event_count": len(rows), "error_type": type(error).__name__},
        )


@asynccontextmanager
async def security_event_scope(
    factory: async_sessionmaker[AsyncSession], context: RequestContext
) -> AsyncIterator[SecurityEventBuffer]:
    """Open the request's buffer; flush it when the scope ends, however it ends."""
    buffer = SecurityEventBuffer(context=context)
    _buffer.set(buffer)
    try:
        yield buffer
    finally:
        _buffer.set(None)
        await flush_security_events(factory, buffer)
