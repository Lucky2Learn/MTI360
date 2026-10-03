"""Tenant member administration API contracts (T01-08; D8-1, D8-3, D8-4).

Requests reject unknown fields: a ``tenant_id``, ``user_id``, ``status`` or
``invited_by`` can never be supplied. Responses never contain a token or a
credential; the user block is the member's name and email only.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from app.core.schemas import RequestModel, ResponseModel
from app.modules.identity.domain import CampusScope, MembershipStatus
from app.modules.identity.schemas import DisplayName, Email

Version = Annotated[int, Field(ge=1)]


class MemberUserOut(ResponseModel):
    display_name: str
    email: str


class MemberRoleOut(ResponseModel):
    id: uuid.UUID
    name: str
    is_system: bool


class MemberOut(ResponseModel):
    id: uuid.UUID
    user: MemberUserOut
    status: MembershipStatus
    campus_scope: CampusScope
    campus_ids: list[uuid.UUID]
    """Only for ``SELECTED``; empty for ``ALL``."""
    roles: list[MemberRoleOut]
    invited_at: datetime
    joined_at: datetime | None
    version: int


class InvitedMemberOut(ResponseModel):
    member: MemberOut
    account: Literal["new", "existing"]


class InviteMemberRequest(RequestModel):
    email: Email
    display_name: DisplayName
    """Used for a new account; an existing account keeps its own name."""
    role_ids: Annotated[list[uuid.UUID], Field(max_length=20)] = Field(default_factory=list)
    campus_scope: CampusScope = CampusScope.ALL
    campus_ids: Annotated[list[uuid.UUID], Field(max_length=100)] = Field(default_factory=list)


class VersionRequest(RequestModel):
    version: Version


class CampusScopeRequest(RequestModel):
    campus_scope: CampusScope
    campus_ids: Annotated[list[uuid.UUID], Field(max_length=100)] = Field(default_factory=list)
    version: Version


class AssignRoleRequest(RequestModel):
    role_id: uuid.UUID
