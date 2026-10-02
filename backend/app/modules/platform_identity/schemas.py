"""Platform authentication API contracts (T01-06).

Requests reject unknown fields. Responses expose only what the platform UI
needs: no internal IDs, never a password, hash or token. The TOTP secret and
recovery codes appear only in the responses that create them (once).
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import StringConstraints

from app.core.schemas import RequestModel, ResponseModel
from app.modules.identity.schemas import Email, Secret, Token

MfaCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=6, max_length=7)]
RecoveryCode = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=10, max_length=13)
]


class PlatformLoginRequest(RequestModel):
    email: Email
    password: Secret


class MfaCodeRequest(RequestModel):
    code: MfaCode


class RecoveryCodeRequest(RequestModel):
    recovery_code: RecoveryCode


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


class MfaEnrolmentOut(ResponseModel):
    """Shown once: the secret for manual setup and the ``otpauth://`` URI (no QR, D6-4)."""

    secret: str
    otpauth_uri: str


class MfaEnrolmentConfirmedOut(ResponseModel):
    recovery_codes: list[str]
    session: PlatformSessionOut


class RecoveryCodesOut(ResponseModel):
    recovery_codes: list[str]
