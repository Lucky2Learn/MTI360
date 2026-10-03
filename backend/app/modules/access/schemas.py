"""Tenant role API contracts (T01-08). Requests reject unknown fields (no ``is_system``)."""

import uuid
from typing import Annotated

from pydantic import Field, StringConstraints

from app.core.schemas import RequestModel, ResponseModel

RoleName = Annotated[str, StringConstraints(min_length=1, max_length=100)]
Description = Annotated[str, StringConstraints(max_length=500)]
PermissionCodes = Annotated[
    list[Annotated[str, StringConstraints(max_length=100)]], Field(max_length=200)
]


class PermissionOut(ResponseModel):
    code: str
    scope: str
    description: str
    module: str


class RoleOut(ResponseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_system: bool
    permissions: list[str]
    member_count: int
    version: int


class CreateRoleRequest(RequestModel):
    name: RoleName
    description: Description | None = None
    permissions: PermissionCodes


class UpdateRoleRequest(RequestModel):
    version: Annotated[int, Field(ge=1)]
    name: RoleName | None = None
    description: Description | None = None
    permissions: PermissionCodes | None = None
