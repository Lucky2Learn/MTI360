"""Platform identity rules (T01-06). Pure: no I/O, no framework imports."""

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


MFA_RESET_REASON_MAX_LENGTH: Final = 500
