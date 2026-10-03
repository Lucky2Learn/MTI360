"""Platform identity rules (T01-06, T01-07). Pure: no I/O, no framework imports."""

from datetime import timedelta
from enum import StrEnum
from typing import Final


class PlatformUserStatus(StrEnum):
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class PlatformSessionRevokeReason(StrEnum):
    LOGOUT = "logout"
    ROTATED = "rotated"
    PASSWORD_RESET = "password_reset"  # noqa: S105 - a revoke reason, not a secret
    MFA_FAILED = "mfa_failed"
    MFA_RESET = "mfa_reset"
    BREAK_GLASS = "break_glass"
    ADMIN_SUSPENDED = "admin_suspended"  # T01-07, D7-4


MFA_RESET_REASON_MAX_LENGTH: Final = 500
ADMIN_REASON_MAX_LENGTH: Final = 500
"""Reasons for suspensions, reactivations and MFA resets (D6-3, D7-4)."""
PLATFORM_INVITATION_TTL: Final = timedelta(days=7)
"""Platform user invitations (D7-3): the T01-04 D05 lifetime."""
DISPLAY_NAME_MAX_LENGTH: Final = 200


def clean_reason(reason: str) -> str | None:
    """The reason with whitespace collapsed, or ``None`` if empty or too long."""
    cleaned = " ".join(reason.split())
    if not cleaned or len(cleaned) > ADMIN_REASON_MAX_LENGTH:
        return None
    return cleaned


def clean_display_name(name: str) -> str | None:
    cleaned = " ".join(name.split())
    if not cleaned or len(cleaned) > DISPLAY_NAME_MAX_LENGTH:
        return None
    return cleaned


def reactivated_status(*, invited: bool, accepted: bool) -> PlatformUserStatus:
    """Reactivation restores ``INVITED`` for a user who never accepted an invitation.

    A user created by invitation who never accepted it has no credential; one
    created by the bootstrap CLI has no invitation and a credential. Either
    way MFA stays required at sign-in (D7-4).
    """
    return PlatformUserStatus.INVITED if invited and not accepted else PlatformUserStatus.ACTIVE
