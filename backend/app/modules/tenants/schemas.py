"""Platform tenant administration API contracts (T01-07; D7-1, D7-6 … D7-8).

Requests reject unknown fields: a tenant ID, status or version cannot be
supplied where the schema does not declare it. Responses never contain a
token or another member of the tenant; the owner block is the primary
administrator only.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.core.schemas import RequestModel, ResponseModel
from app.modules.identity.domain import MembershipStatus
from app.modules.identity.schemas import DisplayName, Email
from app.modules.platform_identity.admin_schemas import Reason, Version
from app.modules.tenants.domain import TenantStatus

Name = Annotated[str, StringConstraints(min_length=1, max_length=200)]
CampusCode = Annotated[str, StringConstraints(min_length=1, max_length=32)]


class TenantOwnerOut(ResponseModel):
    display_name: str
    email: str
    status: MembershipStatus
    """``INVITED`` until the administrator accepts the invitation."""


class TenantOut(ResponseModel):
    id: uuid.UUID
    name: str
    status: TenantStatus
    created_at: datetime
    updated_at: datetime
    version: int


class TenantDetailOut(TenantOut):
    owner: TenantOwnerOut | None


class CampusOut(ResponseModel):
    id: uuid.UUID
    name: str
    code: str


class ProvisionedTenantOut(ResponseModel):
    tenant: TenantDetailOut
    campus: CampusOut
    owner_account: Literal["new", "existing"]


class CampusRequest(RequestModel):
    name: Name
    code: CampusCode


class OwnerRequest(RequestModel):
    email: Email
    display_name: DisplayName


class ProvisionTenantRequest(RequestModel):
    name: Name
    campus: CampusRequest
    owner: OwnerRequest


class TenantTransitionRequest(RequestModel):
    reason: Reason
    version: Version = Field(description="The tenant's current version (optimistic concurrency).")
