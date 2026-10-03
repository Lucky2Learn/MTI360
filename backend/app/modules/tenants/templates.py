"""Owner invitation email (T01-07, D7-1/D7-7/D7-8; the T01-04 D15 link pattern).

The link is the tenant invitation link of T01-04 (token in the URL fragment):
the owner accepts through the existing invitation flow, which asks a new
account for a name and password and never changes an existing account.
"""

from app.integrations.email import EmailMessage
from app.modules.identity.domain import INVITATION_TTL
from app.modules.identity.templates import invitation_link

__all__ = ["invitation_link", "owner_invitation_email"]


def owner_invitation_email(
    *, to: str, display_name: str, institute: str, link: str
) -> EmailMessage:
    days = INVITATION_TTL.days
    body = (
        f"Hello {display_name},\n\n"
        f"You have been invited to administer {institute} on MTI 360.\n\n"
        f"Accept the invitation here (the link works once and expires in {days} days):\n"
        f"{link}\n\n"
        "If you didn't expect this invitation, you can ignore this email.\n\n"
        "MTI 360\n"
    )
    return EmailMessage(
        to=to,
        subject=f"You're invited to administer {institute} on MTI 360",
        body=body,
        template="tenant_owner_invitation",
    )
