"""Identity and authentication rules (T01-04). Pure: no I/O, no framework imports.

Sources: ADR-0010 (identity/credential split, passwords, lockout), the T01-04
decision record ``docs/architecture/identity-authentication.md`` (D04 campus
semantics, D05 invitations, D17 limits, D19 invitation preview) and the
frozen UI contract ``docs/ui/T01-04-IDENTITY-AUTHENTICATION-UI.md``.
"""

import re
import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Final

# --- Statuses ------------------------------------------------------------------------


class UserStatus(StrEnum):
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class MembershipStatus(StrEnum):
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class CampusScope(StrEnum):
    ALL = "ALL"
    SELECTED = "SELECTED"


class SessionRevokeReason(StrEnum):
    LOGOUT = "logout"
    ROTATED = "rotated"
    PASSWORD_RESET = "password_reset"  # noqa: S105 - a revoke reason, not a secret


SESSION_REALM_TENANT: Final = "tenant"

# --- Email (D12: the only login identifier) -----------------------------------------

EMAIL_MAX_LENGTH: Final = 254
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class InvalidEmailError(ValueError):
    pass


def normalize_email(raw: str) -> str:
    """Canonical form: trimmed and lower-cased; raises on an implausible address."""
    email = raw.strip().lower()
    if len(email) > EMAIL_MAX_LENGTH or not _EMAIL_PATTERN.fullmatch(email):
        raise InvalidEmailError("not an email address")
    return email


def mask_email(email: str) -> str:
    """``r•••@westernmaritime.edu``: first character of the local part, full domain."""
    local, _, domain = email.partition("@")
    return f"{local[:1]}•••@{domain}"


# --- Passwords (ADR-0010 §7: 12 to 128 characters, blocklist, no composition rules) --------

PASSWORD_MIN_LENGTH: Final = 12
PASSWORD_MAX_LENGTH: Final = 128


class PasswordProblem(StrEnum):
    TOO_SHORT = "password_too_short"
    TOO_LONG = "password_too_long"
    COMMON = "password_too_common"


PASSWORD_MESSAGES: Final = {
    PasswordProblem.TOO_SHORT: f"Use at least {PASSWORD_MIN_LENGTH} characters.",
    PasswordProblem.TOO_LONG: f"Use {PASSWORD_MAX_LENGTH} characters or fewer.",
    PasswordProblem.COMMON: "This password is too common. Choose a different one.",
}


def password_problem(password: str, blocklist: Collection[str]) -> PasswordProblem | None:
    """The first rule ``password`` breaks, or ``None``. Length counts characters."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return PasswordProblem.TOO_SHORT
    if len(password) > PASSWORD_MAX_LENGTH:
        return PasswordProblem.TOO_LONG
    if password.casefold() in blocklist:
        return PasswordProblem.COMMON
    return None


# --- Lockout (ADR-0010 §6, D17) -----------------------------------------------------------

LOCKOUT_THRESHOLD: Final = 5
_LOCKOUT_STEPS: Final = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(minutes=60),
)


def lockout_duration(failed_attempts: int) -> timedelta | None:
    """Lock for 1, 5, 15, then 60 minutes (cap) from the 5th consecutive failure."""
    if failed_attempts < LOCKOUT_THRESHOLD:
        return None
    step = min(failed_attempts - LOCKOUT_THRESHOLD, len(_LOCKOUT_STEPS) - 1)
    return _LOCKOUT_STEPS[step]


# --- Rate limits (D17) ----------------------------------------------------------------

IP_LIMIT_ATTEMPTS: Final = 20
IP_LIMIT_WINDOW_SECONDS: Final = 5 * 60
ACCOUNT_LIMIT_ATTEMPTS: Final = 10
ACCOUNT_LIMIT_WINDOW_SECONDS: Final = 15 * 60

# --- Token lifetimes ---------------------------------------------------------------------

PASSWORD_RESET_TTL: Final = timedelta(minutes=30)
INVITATION_TTL: Final = timedelta(days=7)

# --- Campus selection (D04) ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CampusState:
    """The session's campus after applying the D04 rules."""

    usable: bool
    """False only for a SELECTED membership without any permitted campus (rule 5)."""
    active_campus_id: uuid.UUID | None
    """``None`` means "All campuses" when ``all_campuses_allowed``, else "not chosen"."""
    all_campuses_allowed: bool
    selection_required: bool


def resolve_campus(
    scope: CampusScope,
    permitted: Sequence[uuid.UUID],
    current: uuid.UUID | None,
) -> CampusState:
    """Apply D04 rules 1 to 5 and 8 to the permitted campuses and the current choice."""
    if scope is CampusScope.SELECTED and not permitted:
        return CampusState(False, None, False, False)
    all_allowed = scope is CampusScope.ALL and len(permitted) >= 2
    if current is not None and current in permitted:
        return CampusState(True, current, all_allowed, False)
    if len(permitted) == 1:
        return CampusState(True, permitted[0], False, False)
    if scope is CampusScope.ALL:
        return CampusState(True, None, all_allowed, False)
    return CampusState(True, None, False, True)


def membership_usable(
    status: MembershipStatus, tenant_accessible: bool, campus: CampusState
) -> bool:
    """A membership can open an institute: active, tenant accessible, campus usable."""
    return status is MembershipStatus.ACTIVE and tenant_accessible and campus.usable
