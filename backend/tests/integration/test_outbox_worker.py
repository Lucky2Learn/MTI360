"""Outbox worker against PostgreSQL (Phase 02-4, ADR-0024).

The worker claims ready messages of every tenant, delivers each outside any
transaction, and settles it with a fenced update. Other tests leave messages
in the shared test database, so every assertion names this test's messages,
and passes use a batch large enough to include them.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from conftest import DatabaseUnderTest
from identity_support import Harness, auth_harness
from public_enquiry_support import Sites, enquiry, isolate, leads_by_email, sites, submit

from app.core.context import Realm, RequestContext
from app.core.outbox import claim, enqueue, mark_sent
from app.core.tenancy import system_context
from app.integrations.email import EmailMessage, FakeEmailSender
from app.modules.enquiries.domain import ACKNOWLEDGEMENT_KIND
from app.modules.tenants.scopes import public_site_transaction
from app.worker import WorkerConfig, run_once

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

CONFIG = WorkerConfig(stale_after=timedelta(minutes=5), poll_seconds=1.0, batch_size=5000)


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        await isolate(harness)
        yield harness  # the harness closes the enquiry limiter and signal


@pytest.fixture
async def s(h: Harness) -> Sites:
    return await sites(h)


async def _enquire(h: Harness, s: Sites, **fields: Any) -> tuple[uuid.UUID, str]:
    body = enquiry(**fields)
    assert (await submit(h, s.host_a, body)).status_code == 202
    (lead,) = await leads_by_email(h, body["email"])
    return lead.id, body["email"]


async def _message(h: Harness, lead_id: uuid.UUID) -> Any:
    rows = await h.owner(
        "SELECT id, status, attempts, max_attempts, last_error, sent_at, failed_at, "
        "available_at, locked_at, locked_by FROM outbox_messages WHERE payload->>'lead_id' = :l",
        l=str(lead_id),
    )
    assert len(rows) == 1
    return rows[0]


def _to(sender: FakeEmailSender, email: str) -> list[EmailMessage]:
    return [message for message in sender.sent if message.to == email]


async def test_the_acknowledgement_is_sent_once(h: Harness, s: Sites) -> None:
    lead_id, email = await _enquire(h, s, course_id=str(s.course_a))
    sender = FakeEmailSender()
    await run_once(h.factory, sender, CONFIG, worker="w1")
    (sent,) = _to(sender, email)
    assert "Western Maritime Academy" in sent.subject
    assert "GPR programme" in sent.body
    assert "Ananya Iyer" in sent.body
    assert sent.template == "enquiry_acknowledgement"
    message = await _message(h, lead_id)
    assert (message.status, message.attempts) == ("SENT", 1)
    assert message.sent_at is not None
    assert message.locked_at is None
    # Idempotent: a later pass does not send it again.
    await run_once(h.factory, sender, CONFIG, worker="w2")
    assert len(_to(sender, email)) == 1


async def test_a_temporary_failure_keeps_the_lead_and_retries_later(h: Harness, s: Sites) -> None:
    lead_id, email = await _enquire(h, s)
    now = datetime.now(UTC)
    await run_once(h.factory, FakeEmailSender(fail=True), CONFIG, worker="w1", now=lambda: now)
    message = await _message(h, lead_id)
    assert (message.status, message.attempts, message.last_error) == (
        "PENDING",
        1,
        "EmailDeliveryError",
    )
    assert message.available_at >= now + timedelta(seconds=59)
    assert len(await leads_by_email(h, email)) == 1  # the lead is never lost

    # Not before its time ...
    sender = FakeEmailSender()
    await run_once(h.factory, sender, CONFIG, worker="w2", now=lambda: now)
    assert _to(sender, email) == []
    # ... then delivered.
    later = now + timedelta(minutes=2)
    await run_once(h.factory, sender, CONFIG, worker="w2", now=lambda: later)
    assert len(_to(sender, email)) == 1
    message = await _message(h, lead_id)
    assert (message.status, message.attempts, message.last_error) == ("SENT", 2, None)


async def test_it_fails_after_the_last_attempt(h: Harness, s: Sites) -> None:
    await isolate(h, outbox_max_attempts=2)
    lead_id, _ = await _enquire(h, s)
    start = datetime.now(UTC)
    for hours in (0, 2):
        moment = start + timedelta(hours=hours)

        def clock(at: datetime = moment) -> datetime:
            return at

        await run_once(h.factory, FakeEmailSender(fail=True), CONFIG, worker="w", now=clock)
    at = start + timedelta(hours=2)
    message = await _message(h, lead_id)
    assert (message.status, message.attempts) == ("FAILED", 2)
    assert message.failed_at is not None
    sender = FakeEmailSender()
    await run_once(h.factory, sender, CONFIG, worker="w", now=lambda: at + timedelta(days=1))
    assert (await _message(h, lead_id)).status == "FAILED"


async def test_a_message_with_nothing_to_send_fails_at_once(h: Harness, s: Sites) -> None:
    lead_id = uuid.uuid7()  # no such lead
    async with public_site_transaction(
        h.factory, context=_public_context(), tenant_id=h.world.tenant_a
    ) as db:
        await enqueue(
            db,
            kind=ACKNOWLEDGEMENT_KIND,
            idempotency_key=f"test:{lead_id}",
            payload={"lead_id": str(lead_id)},
            max_attempts=6,
        )
    await run_once(h.factory, FakeEmailSender(), CONFIG, worker="w")
    message = await _message(h, lead_id)
    assert (message.status, message.attempts, message.last_error) == (
        "FAILED",
        1,
        "NothingToSendError",
    )


async def test_an_idempotency_key_is_enqueued_once(h: Harness) -> None:
    key = f"test:{uuid.uuid7()}"
    results = []
    for _ in range(2):
        async with public_site_transaction(
            h.factory, context=_public_context(), tenant_id=h.world.tenant_a
        ) as db:
            results.append(
                await enqueue(db, kind="test", idempotency_key=key, payload={}, max_attempts=1)
            )
    assert results == [True, False]


async def test_concurrent_workers_deliver_each_message_once(h: Harness, s: Sites) -> None:
    emails = [(await _enquire(h, s))[1] for _ in range(6)]
    sender = FakeEmailSender()
    await asyncio.gather(*(run_once(h.factory, sender, CONFIG, worker=f"w{n}") for n in range(4)))
    for email in emails:
        assert len(_to(sender, email)) == 1, email


async def test_a_crashed_worker_s_message_is_reclaimed_and_its_late_result_ignored(
    h: Harness, s: Sites
) -> None:
    lead_id, email = await _enquire(h, s)
    claimed_at = datetime.now(UTC)
    later = claimed_at + timedelta(minutes=10)  # the claim is stale by then
    async with system_context(h.factory) as db:
        claimed = await claim(
            db, worker="crashed", limit=5000, now=claimed_at, stale_after=CONFIG.stale_after
        )
    mine = next(m for m in claimed if m.payload.get("lead_id") == str(lead_id))
    assert (await _message(h, lead_id)).status == "PROCESSING"

    sender = FakeEmailSender()
    await run_once(h.factory, sender, CONFIG, worker="rescuer", now=lambda: later)
    assert len(_to(sender, email)) == 1
    message = await _message(h, lead_id)
    assert (message.status, message.attempts) == ("SENT", 2)

    # The crashed worker comes back: its claim is gone, so nothing changes.
    async with system_context(h.factory) as db:
        assert not await mark_sent(db, mine, now=datetime.now(UTC))
    assert (await _message(h, lead_id)).attempts == 2


async def test_a_stale_message_without_attempts_left_fails(h: Harness, s: Sites) -> None:
    await isolate(h, outbox_max_attempts=1)
    lead_id, email = await _enquire(h, s)
    claimed_at = datetime.now(UTC)
    later = claimed_at + timedelta(minutes=10)
    async with system_context(h.factory) as db:
        await claim(
            db, worker="crashed", limit=5000, now=claimed_at, stale_after=CONFIG.stale_after
        )
    sender = FakeEmailSender()
    await run_once(h.factory, sender, CONFIG, worker="rescuer", now=lambda: later)
    message = await _message(h, lead_id)
    assert (message.status, message.last_error) == ("FAILED", "StaleProcessing")
    assert _to(sender, email) == []


async def test_an_unexpected_error_is_retried_not_raised(h: Harness, s: Sites) -> None:
    lead_id, _ = await _enquire(h, s)

    class Broken:
        async def send(self, message: EmailMessage) -> None:
            raise ValueError("boom")

    result = await run_once(h.factory, Broken(), CONFIG, worker="w")
    assert result.retried >= 1
    message = await _message(h, lead_id)
    assert (message.status, message.last_error) == ("PENDING", "ValueError")


async def test_worker_logs_name_no_recipient(
    h: Harness, s: Sites, caplog: pytest.LogCaptureFixture
) -> None:
    _, email = await _enquire(h, s)
    with caplog.at_level("INFO", logger="app.worker"):
        await run_once(h.factory, FakeEmailSender(fail=True), CONFIG, worker="w")
    assert caplog.records
    for record in caplog.records:
        assert email not in record.getMessage()
        assert email not in str(record.__dict__)


def _public_context() -> RequestContext:
    return RequestContext(realm=Realm.PUBLIC, request_id=uuid.uuid7())
