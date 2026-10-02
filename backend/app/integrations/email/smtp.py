"""SMTP adapter: standard library ``smtplib`` in a worker thread (T01-04, D11)."""

import smtplib
import ssl
from email.message import EmailMessage as MimeMessage

import anyio

from app.integrations.email.sender import EmailDeliveryError, EmailMessage


class SmtpEmailSender:
    """Sends through one SMTP server; ``STARTTLS`` and login when credentials are set.

    Local development uses Mailpit (no TLS, no credentials). Deployed
    environments must provide credentials (config validation), and then the
    connection is upgraded with ``STARTTLS`` before logging in.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_address: str,
        timeout_seconds: int,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from = from_address
        self._timeout = timeout_seconds

    def _build(self, message: EmailMessage) -> MimeMessage:
        mime = MimeMessage()
        mime["From"] = self._from
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.body)
        return mime

    def _deliver(self, mime: MimeMessage) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as client:
            if self._username:
                client.starttls(context=ssl.create_default_context())
                client.login(self._username, self._password)
            client.send_message(mime)

    async def send(self, message: EmailMessage) -> None:
        mime = self._build(message)
        try:
            with anyio.fail_after(self._timeout + 1):
                await anyio.to_thread.run_sync(self._deliver, mime, abandon_on_cancel=True)
        except (OSError, smtplib.SMTPException, TimeoutError) as error:
            # The exception text can contain server replies; keep only the class.
            raise EmailDeliveryError(type(error).__name__) from None
