"""Platform password-reset email (T01-06, D6-2; the T01-04 D15 pattern).

The link carries the token in the URL fragment, which browsers never send to
servers. A reset changes the password only: the next sign-in still needs MFA.
"""

from app.integrations.email import EmailMessage
from app.modules.identity.domain import PASSWORD_RESET_TTL

PLATFORM_RESET_PATH = "/platform/reset-password"


def platform_reset_link(app_base_url: str, token: str) -> str:
    return f"{app_base_url}{PLATFORM_RESET_PATH}#token={token}"


def platform_password_reset_email(*, to: str, display_name: str, link: str) -> EmailMessage:
    minutes = int(PASSWORD_RESET_TTL.total_seconds() // 60)
    body = (
        f"Hello {display_name},\n\n"
        "We received a request to reset the password of your MTI 360 platform account.\n\n"
        f"Choose a new password here (the link works once and expires in {minutes} minutes):\n"
        f"{link}\n\n"
        "Your authenticator app is still required when you sign in.\n\n"
        "If you didn't ask for this, you can ignore this email and tell your security team.\n\n"
        "MTI 360\n"
    )
    return EmailMessage(
        to=to,
        subject="Reset your MTI 360 platform password",
        body=body,
        template="platform_password_reset",
    )
