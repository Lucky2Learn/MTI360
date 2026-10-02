"""Email delivery boundary (T01-04 decision D11; backend-foundation.md §5).

Application code depends only on :class:`EmailSender`. Adapters:

* :class:`app.integrations.email.smtp.SmtpEmailSender` — standard-library
  SMTP (Mailpit locally), run in a worker thread with a bounded timeout;
* :class:`app.integrations.email.fake.FakeEmailSender` — records messages for
  deterministic tests.

Sending happens only after the business transaction has committed and after
the response (FastAPI background task). A failed send never undoes the
committed state and is at most once until a transactional outbox exists.
Messages can carry secret links (password reset), so neither the body nor the
recipient is ever logged.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EmailMessage:
    """A plain-text message. ``template`` names it for logs (never the body)."""

    to: str
    subject: str
    body: str
    template: str

    def __repr__(self) -> str:  # never expose the recipient or a secret link
        return f"EmailMessage(template={self.template!r})"


class EmailDeliveryError(Exception):
    """Delivery failed. The message never contains the body or recipient."""


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None:
        """Deliver ``message``; raise :class:`EmailDeliveryError` on failure."""
        ...
