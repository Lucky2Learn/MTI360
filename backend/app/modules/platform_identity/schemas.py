"""Platform authentication API contracts (T01-06).

Requests reject unknown fields. Responses expose only what the platform UI
needs: no internal IDs, never a password, hash or token. The TOTP secret and
recovery codes appear only in the responses that create them (once).
"""

from datetime import datetime
from typing import Literal

from app.core.schemas import RequestModel, ResponseModel
from app.modules.identity.schemas import (
    Email,
    MfaCodeRequest,
    MfaEnrolmentOut,
    RecoveryCodeRequest,
    RecoveryCodesOut,
    Secret,
    Token,
)

__all__ = [
    "MfaCodeRequest",
    "MfaEnrolmentConfirmedOut",
    "MfaEnrolmentOut",
    "PlatformLoginRequest",
    "PlatformMfaOut",
    "PlatformPasswordResetConfirmRequest",
    "PlatformPasswordResetRequest",
    "PlatformSessionOut",
    "PlatformUserOut",
    "RecoveryCodeRequest",
    "RecoveryCodesOut",
]


class PlatformLoginRequest(RequestModel):
    email: Email
    password: Secret


class PlatformPasswordResetRequest(RequestModel):
    email: Email


class PlatformPasswordResetConfirmRequest(RequestModel):
    token: Token
    new_password: Secret


class PlatformUserOut(ResponseModel):
    display_name: str
    email: str


class PlatformMfaOut(ResponseModel):
    enrolled: bool
    verified_at: datetime | None
    step_up_expires_at: datetime | None
    recovery_codes_remaining: int | None


class PlatformSessionOut(ResponseModel):
    status: Literal["authenticated", "mfa_required", "mfa_enrolment_required"]
    user: PlatformUserOut | None
    """``None`` until MFA is complete."""
    permissions: list[str]
    roles: list[str]
    mfa: PlatformMfaOut
    csrf_token: str


class MfaEnrolmentConfirmedOut(ResponseModel):
    recovery_codes: list[str]
    session: PlatformSessionOut
