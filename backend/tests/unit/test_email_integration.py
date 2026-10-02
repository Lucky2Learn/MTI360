"""Email boundary (T01-04, D11): fake sender, bounded SMTP failure, safe failure logging."""

import logging
import uuid

import pytest

from app.integrations.email import (
    EmailDeliveryError,
    EmailMessage,
    FakeEmailSender,
    SmtpEmailSender,
)
from app.modules.identity.service import send_email_safely
from app.modules.identity.templates import (
    invitation_link,
    password_reset_email,
    reset_link,
)

pytestmark = pytest.mark.anyio

SECRET_TOKEN = "s3cr3t-T0ken-value-that-must-never-be-logged-0"


def _message() -> EmailMessage:
    return password_reset_email(
        to="rao@westernmaritime.example",
        display_name="Captain Rao",
        link=reset_link("https://app.mti360.example", SECRET_TOKEN),
    )


def test_links_carry_the_token_in_the_fragment_only() -> None:
    reset = reset_link("https://app.mti360.example", SECRET_TOKEN)
    invitation = invitation_link("https://app.mti360.example", SECRET_TOKEN)

    assert reset == f"https://app.mti360.example/reset-password#token={SECRET_TOKEN}"
    assert invitation == f"https://app.mti360.example/accept-invitation#token={SECRET_TOKEN}"
    for link in (reset, invitation):
        path_and_query = link.split("#", 1)[0]
        assert SECRET_TOKEN not in path_and_query


def test_messages_never_expose_the_recipient_or_body_in_their_repr() -> None:
    message = _message()

    assert repr(message) == "EmailMessage(template='password_reset')"
    assert SECRET_TOKEN in message.body
    assert "30 minutes" in message.body


async def test_the_fake_sender_records_or_fails_on_demand() -> None:
    sender = FakeEmailSender()
    await sender.send(_message())
    failing = FakeEmailSender(fail=True)

    with pytest.raises(EmailDeliveryError):
        await failing.send(_message())
    assert [m.template for m in sender.sent] == ["password_reset"]
    assert failing.attempts == 1
    assert failing.sent == []


async def test_smtp_failures_are_bounded_and_reveal_no_details() -> None:
    # Port 9 (discard) on loopback refuses the connection immediately.
    sender = SmtpEmailSender(
        host="127.0.0.1",
        port=9,
        username="",
        password="",
        from_address="no-reply@mti360.example",
        timeout_seconds=2,
    )

    with pytest.raises(EmailDeliveryError) as raised:
        await sender.send(_message())
    assert SECRET_TOKEN not in str(raised.value)
    assert "rao@" not in str(raised.value)


async def test_a_failed_post_response_send_is_logged_without_secrets(
    caplog: pytest.LogCaptureFixture,
) -> None:
    request_id = uuid.uuid7()
    with caplog.at_level(logging.ERROR, logger="app.identity"):
        await send_email_safely(FakeEmailSender(fail=True), _message(), request_id)

    (record,) = [r for r in caplog.records if r.getMessage() == "email.send_failed"]
    assert record.template == "password_reset"  # type: ignore[attr-defined]
    assert record.request_id == str(request_id)  # type: ignore[attr-defined]
    rendered = caplog.text + repr(record.__dict__)
    assert SECRET_TOKEN not in rendered
    assert "rao@westernmaritime.example" not in rendered
