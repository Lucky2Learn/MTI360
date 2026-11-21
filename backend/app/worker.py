"""Outbox worker (Phase 02-4, ADR-0024). Run from ``backend/``::

    python -m app.worker            # until stopped (Ctrl+C / SIGTERM)
    python -m app.worker --once     # one pass, then exit (operations, tests)

Each pass, in the system realm:

1. stale ``PROCESSING`` messages with no attempt left become ``FAILED``;
2. up to :data:`BATCH_SIZE` ready messages are claimed (``SKIP LOCKED``, so
   any number of workers can run side by side);
3. each is delivered **outside** any database transaction: its handler builds
   the email from current data (tenant-scoped), the sender delivers it;
4. the outcome is recorded with a fenced update: ``SENT``; ``PENDING`` again
   after 1, 2, 4 … 60 minutes for a temporary failure (``EmailDeliveryError``,
   or any unexpected error); ``FAILED`` after ``OUTBOX_MAX_ATTEMPTS`` or for a
   permanent failure (nothing to send, unknown kind).

The business data never depends on delivery: a lead stays whatever happens
to its acknowledgement. Between passes the worker waits for the Redis signal
(``OutboxSignal``) or ``OUTBOX_POLL_SECONDS``, whichever comes first.

Logs carry the message ID, kind, tenant, attempt and error class; never a
recipient, subject or body.
"""

import argparse
import asyncio
import contextlib
import logging
import os
import signal
import socket
import sys
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import ConfigurationError, Settings, load_settings
from app.core.db import create_engine, create_sessionmaker
from app.core.logging import configure_logging
from app.core.outbox import (
    Claimed,
    OutboxSignal,
    OutboxStatus,
    claim,
    error_name,
    fail_exhausted,
    mark_retry,
    mark_sent,
    retry_delay,
)
from app.core.tenancy import system_context
from app.integrations.email import EmailMessage, EmailSender, SmtpEmailSender
from app.modules.enquiries.acknowledgement import NothingToSendError, build_acknowledgement
from app.modules.enquiries.domain import ACKNOWLEDGEMENT_KIND

logger = logging.getLogger("app.worker")

BATCH_SIZE: Final = 20

type Builder = Callable[
    [async_sessionmaker[AsyncSession], uuid.UUID, Mapping[str, Any]], Awaitable[EmailMessage]
]

BUILDERS: Final[Mapping[str, Builder]] = {ACKNOWLEDGEMENT_KIND: build_acknowledgement}
"""Outbox kind → the email it delivers."""

PERMANENT_ERRORS: Final = (NothingToSendError,)


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    stale_after: timedelta
    poll_seconds: float
    batch_size: int = BATCH_SIZE


@dataclass(slots=True)
class PassResult:
    claimed: int = 0
    sent: int = 0
    retried: int = 0
    failed: int = 0
    lost: int = 0
    """Claims taken over by another worker meanwhile (nothing recorded)."""


def worker_id() -> str:
    return f"{socket.gethostname()[:40]}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def _log(event: str, message: Claimed, **extra: object) -> None:
    logger.info(
        event,
        extra={
            "outbox_id": str(message.id),
            "kind": message.kind,
            "tenant_id": str(message.tenant_id),
            "attempt": message.attempts,
            **extra,
        },
    )


async def _deliver(
    factory: async_sessionmaker[AsyncSession],
    sender: EmailSender,
    message: Claimed,
    builders: Mapping[str, Builder],
) -> None:
    builder = builders.get(message.kind)
    if builder is None:
        raise NothingToSendError()
    email = await builder(factory, message.tenant_id, message.payload)
    await sender.send(email)


async def run_once(
    factory: async_sessionmaker[AsyncSession],
    sender: EmailSender,
    config: WorkerConfig,
    *,
    worker: str,
    builders: Mapping[str, Builder] = BUILDERS,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> PassResult:
    """One pass: reap, claim, deliver, settle. Never raises for a message's failure."""
    result = PassResult()
    async with system_context(factory) as db:
        result.failed += await fail_exhausted(db, now=now(), stale_after=config.stale_after)
        claimed = await claim(
            db, worker=worker, limit=config.batch_size, now=now(), stale_after=config.stale_after
        )
    result.claimed = len(claimed)
    for message in claimed:
        error: BaseException | None = None
        try:
            await _deliver(factory, sender, message, builders)
        except Exception as caught:
            error = caught
        at = now()
        async with system_context(factory) as db:
            if error is None:
                if await mark_sent(db, message, now=at):
                    result.sent += 1
                    _log("outbox.sent", message)
                else:
                    result.lost += 1
                    _log("outbox.claim_lost", message)
                continue
            permanent = isinstance(error, PERMANENT_ERRORS)
            retry_at = None if permanent else at + retry_delay(message.attempts)
            outcome = await mark_retry(
                db, message, now=at, error=error_name(error), retry_at=retry_at
            )
        if outcome is OutboxStatus.PENDING:
            result.retried += 1
            _log("outbox.retry", message, error_type=error_name(error))
        elif outcome is OutboxStatus.FAILED:
            result.failed += 1
            logger.warning(
                "outbox.failed",
                extra={
                    "outbox_id": str(message.id),
                    "kind": message.kind,
                    "tenant_id": str(message.tenant_id),
                    "attempt": message.attempts,
                    "error_type": error_name(error),
                    "permanent": permanent,
                },
            )
        else:
            result.lost += 1
            _log("outbox.claim_lost", message)
    return result


async def run_forever(
    factory: async_sessionmaker[AsyncSession],
    sender: EmailSender,
    config: WorkerConfig,
    wake: OutboxSignal,
    *,
    stop: asyncio.Event,
) -> None:
    worker = worker_id()
    logger.info("outbox.worker_started", extra={"worker": worker})
    while not stop.is_set():
        try:
            result = await run_once(factory, sender, config, worker=worker)
        except Exception as error:
            logger.error("outbox.pass_failed", extra={"error_type": error_name(error)})
            result = PassResult()
        if result.claimed < config.batch_size:
            waiting = asyncio.ensure_future(wake.wait(config.poll_seconds))
            stopping = asyncio.ensure_future(stop.wait())
            await asyncio.wait({waiting, stopping}, return_when=asyncio.FIRST_COMPLETED)
            for task in (waiting, stopping):
                task.cancel()
    logger.info("outbox.worker_stopped", extra={"worker": worker})


def _sender(settings: Settings) -> SmtpEmailSender:
    return SmtpEmailSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password.get_secret_value(),
        from_address=settings.email_from_address,
        timeout_seconds=settings.smtp_timeout_seconds,
    )


def worker_config(settings: Settings) -> WorkerConfig:
    return WorkerConfig(
        stale_after=timedelta(seconds=settings.outbox_stale_seconds),
        poll_seconds=float(settings.outbox_poll_seconds),
    )


async def _main(settings: Settings, *, once: bool) -> None:
    engine = create_engine(settings)
    factory = create_sessionmaker(engine)
    sender = _sender(settings)
    config = worker_config(settings)
    try:
        if once:
            result = await run_once(factory, sender, config, worker=worker_id())
            logger.info(
                "outbox.pass_completed",
                extra={
                    "claimed": result.claimed,
                    "sent": result.sent,
                    "retried": result.retried,
                    "failed": result.failed,
                },
            )
            return
        wake = OutboxSignal.from_url(settings.redis_url.get_secret_value())
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for name in ("SIGINT", "SIGTERM"):
            # Windows has no loop signal handlers: Ctrl+C raises KeyboardInterrupt there.
            if hasattr(signal, name):
                with contextlib.suppress(NotImplementedError):
                    loop.add_signal_handler(getattr(signal, name), stop.set)
        try:
            await run_forever(factory, sender, config, wake, stop=stop)
        finally:
            await wake.close()
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.worker", description=__doc__)
    parser.add_argument("--once", action="store_true", help="Run one pass and exit.")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
    except ConfigurationError as error:
        sys.stderr.write(f"{error}\n")
        return 3
    configure_logging(settings.log_level)
    try:
        asyncio.run(_main(settings, once=args.once))
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    sys.exit(main())
