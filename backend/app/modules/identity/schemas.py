"""Authentication API contracts (T01-04; UI contract §15, identity-authentication.md).

Requests reject unknown fields (``RequestModel``: a ``tenant_id``, ``user_id``
or ``status`` can never be smuggled in). Passwords and tokens keep every
character (no stripping) and are bounded; tokens must match the token format.
Responses expose only what the UI needs: no internal IDs except the institute
and campus IDs used as selectors, and never a token, hash or credential.
"""

import uuid
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.core.schemas import RequestModel, ResponseModel
from app.modules.identity.domain import EMAIL_MAX_LENGTH
from app.modules.identity.tokens import TOKEN_PATTERN

Email = Annotated[str, StringConstraints(min_length=3, max_length=EMAIL_MAX_LENGTH)]
Secret = Annotated[str, StringConstraints(strip_whitespace=False, min_length=1, max_length=1024)]
Token = Annotated[str, StringConstraints(strip_whitespace=False, pattern=TOKEN_PATTERN)]
DisplayName = Annotated[str, StringConstraints(min_length=1, max_length=200)]
MfaCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=6, max_length=7)]
RecoveryCode = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=10, max_length=13)
]


class LoginRequest(RequestModel):
    email: Email
    password: Secret


class PasswordResetRequest(RequestModel):
    email: Email


class PasswordResetConfirmRequest(RequestModel):
    token: Token
    new_password: Secret


class InvitationTokenRequest(RequestModel):
    token: Token


class InvitationAcceptRequest(RequestModel):
    token: Token
    display_name: DisplayName | None = None
    password: Secret | None = None


class MfaCodeRequest(RequestModel):
    code: MfaCode


class RecoveryCodeRequest(RequestModel):
    recovery_code: RecoveryCode


class TenantSelectionRequest(RequestModel):
    tenant_id: uuid.UUID


class CampusSelectionRequest(RequestModel):
    # Required key: an explicit null selects "All campuses" where allowed.
    campus_id: uuid.UUID | None = Field(...)


class UserOut(ResponseModel):
    display_name: str
    email: str


class InstituteOut(ResponseModel):
    id: uuid.UUID
    name: str
    is_trial: bool


class CampusOut(ResponseModel):
    id: uuid.UUID
    name: str
    code: str


class RoleOut(ResponseModel):
    """A role for display (T01-05 UI contract §8.5): no ID."""

    name: str
    is_system: bool


class SessionOut(ResponseModel):
    status: Literal[
        "ready", "institute_selection_required", "campus_selection_required", "mfa_required"
    ]
    user: UserOut
    active_institute: InstituteOut | None
    institutes: list[InstituteOut]
    active_campus: CampusOut | None
    campus_options: list[CampusOut]
    all_campuses_allowed: bool
    campus_selection_required: bool
    csrf_token: str
    permissions: list[str]
    """Sorted permission codes in the active institute (T01-05); empty without one."""
    roles: list[RoleOut]
    mfa_enabled: bool
    """The user has a confirmed TOTP factor (T01-06)."""


class MfaEnrolmentOut(ResponseModel):
    """Shown once: the secret for manual setup and the ``otpauth://`` URI (no QR, D6-4)."""

    secret: str
    otpauth_uri: str


class RecoveryCodesOut(ResponseModel):
    recovery_codes: list[str]


class InvitationPreviewOut(ResponseModel):
    institute_name: str
    email_masked: str
    account: Literal["new", "existing"]
