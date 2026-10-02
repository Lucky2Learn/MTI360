"""Plain-text authentication emails and links (T01-04, D15; UI contract §6.1).

Links point at the frontend (``APP_BASE_URL``) and carry the token in the URL
**fragment** (``#token=…``): browsers never send fragments to servers, so the
token cannot reach request logs, proxies or ``Referer`` headers. The frontend
reads it, removes it from the address bar and POSTs it.
"""

from app.integrations.email import EmailMessage
from app.modules.identity.domain import PASSWORD_RESET_TTL

RESET_PATH = "/reset-password"
INVITATION_PATH = "/accept-invitation"


def reset_link(app_base_url: str, token: str) -> str:
    return f"{app_base_url}{RESET_PATH}#token={token}"


def invitation_link(app_base_url: str, token: str) -> str:
    return f"{app_base_url}{INVITATION_PATH}#token={token}"


def password_reset_email(*, to: str, display_name: str, link: str) -> EmailMessage:
    minutes = int(PASSWORD_RESET_TTL.total_seconds() // 60)
    body = (
        f"Hello {display_name},\n\n"
        "We received a request to reset the password of your MTI 360 account.\n\n"
        f"Choose a new password here (the link works once and expires in {minutes} minutes):\n"
        f"{link}\n\n"
        "If you didn't ask for this, you can ignore this email: your password stays the same.\n\n"
        "MTI 360\n"
    )
    return EmailMessage(
        to=to, subject="Reset your MTI 360 password", body=body, template="password_reset"
    )
