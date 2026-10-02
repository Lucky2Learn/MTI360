"""Email integration (T01-04): the EmailSender boundary and its adapters."""

from app.integrations.email.fake import FakeEmailSender
from app.integrations.email.sender import EmailDeliveryError, EmailMessage, EmailSender
from app.integrations.email.smtp import SmtpEmailSender

__all__ = [
    "EmailDeliveryError",
    "EmailMessage",
    "EmailSender",
    "FakeEmailSender",
    "SmtpEmailSender",
]
