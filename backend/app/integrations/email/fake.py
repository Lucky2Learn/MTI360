"""Deterministic in-memory sender for tests (T01-04, D11)."""

from app.integrations.email.sender import EmailDeliveryError, EmailMessage


class FakeEmailSender:
    """Records sent messages; ``fail=True`` makes every send fail."""

    def __init__(self, *, fail: bool = False) -> None:
        self.sent: list[EmailMessage] = []
        self.attempts = 0
        self.fail = fail

    async def send(self, message: EmailMessage) -> None:
        self.attempts += 1
        if self.fail:
            raise EmailDeliveryError("FakeFailure")
        self.sent.append(message)
