"""Platform password-reset and invitation emails (T01-06 D6-2, T01-07 D7-3; T01-04 D15).

The link carries the token in the URL fragment, which browsers never send to
servers. A reset changes the password only: the next sign-in still needs MFA.
"""

from app.integrations.email import EmailMessage
from app.modules.identity.domain import PASSWORD_RESET_TTL
from app.modules.platform_identity.domain import PLATFORM_INVITATION_TTL

PLATFORM_RESET_PATH = "/platform/reset-password"
PLATFORM_INVITATION_PATH = "/platform/accept-invitation"


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


def platform_invitation_link(app_base_url: str, token: str) -> str:
    return f"{app_base_url}{PLATFORM_INVITATION_PATH}#token={token}"


def platform_invitation_email(*, to: str, display_name: str, link: str) -> EmailMessage:
    days = PLATFORM_INVITATION_TTL.days
    body = (
        f"Hello {display_name},\n\n"
        "You have been invited to administer the MTI 360 platform.\n\n"
        f"Choose your password here (the link works once and expires in {days} days):\n"
        f"{link}\n\n"
        "At your first sign-in you will set up an authenticator app; it is required "
        "every time you sign in.\n\n"
        "If you didn't expect this invitation, ignore this email and tell your security team.\n\n"
        "MTI 360\n"
    )
    return EmailMessage(
        to=to,
        subject="Your MTI 360 platform invitation",
        body=body,
        template="platform_invitation",
    )
