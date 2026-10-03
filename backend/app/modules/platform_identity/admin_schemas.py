"""Platform user administration API contracts (T01-07; D7-2 … D7-5, D6-3).

Requests reject unknown fields (``status``, ``id`` or ``email`` cannot be
mass-assigned on update). Responses never contain a password, hash, token,
MFA secret or session detail.
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints

from app.core.schemas import RequestModel, ResponseModel
from app.modules.identity.schemas import DisplayName, Email, Secret, Token
from app.modules.platform_identity.domain import PlatformUserStatus
from app.modules.platform_identity.roles import PlatformRole

Reason = Annotated[str, StringConstraints(min_length=1, max_length=1000)]
"""Whitespace is collapsed and the result limited to 500 characters by the service."""
Version = Annotated[int, Field(ge=1)]
Roles = Annotated[list[PlatformRole], Field(min_length=1, max_length=len(PlatformRole))]


class PlatformUserAdminOut(ResponseModel):
    id: uuid.UUID
    email: str
    display_name: str
    status: PlatformUserStatus
    roles: list[PlatformRole]
    created_at: datetime
    updated_at: datetime
    version: int


class CreatePlatformUserRequest(RequestModel):
    email: Email
    display_name: DisplayName
    roles: Roles


class UpdatePlatformUserRequest(RequestModel):
    version: Version
    display_name: DisplayName | None = None
    roles: Roles | None = None


class ReasonedChangeRequest(RequestModel):
    reason: Reason
    version: Version


class MfaResetRequest(RequestModel):
    reason: Reason


class MfaResetOut(ResponseModel):
    factors_disabled: int
    sessions_revoked: int


class PlatformInvitationPreviewRequest(RequestModel):
    token: Token


class PlatformInvitationAcceptRequest(RequestModel):
    token: Token
    password: Secret


class PlatformInvitationPreviewOut(ResponseModel):
    email: str
    """Masked: the first character of the local part and the full domain."""
