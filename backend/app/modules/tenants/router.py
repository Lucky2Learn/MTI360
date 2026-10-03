"""Platform tenant administration routes (T01-07). Mounted by ``app.api.platform``.

``/api/v1/platform/tenants*`` — an MFA-verified platform session and one
``require_permission`` per route (step-up for suspend and reactivate, D6-5).
The tenant in the path is a **target** only; it never becomes the request's
tenant. The owner invitation email is sent after the response (D10).
"""

import uuid
from typing import Annotated, Literal, cast

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status

from app.core.authz import require_permission
from app.core.pagination import Pagination, SortField, sort_param
from app.core.schemas import Envelope, ListEnvelope
from app.modules.identity.service import send_email_safely
from app.modules.platform_identity.router import Info
from app.modules.tenants.domain import TenantStatus
from app.modules.tenants.permissions import (
    TENANT_CREATE,
    TENANT_REACTIVATE,
    TENANT_READ,
    TENANT_SUSPEND,
)
from app.modules.tenants.repository import TenantRow
from app.modules.tenants.schemas import (
    CampusOut,
    ProvisionedTenantOut,
    ProvisionTenantRequest,
    TenantDetailOut,
    TenantOut,
    TenantOwnerOut,
    TenantTransitionRequest,
)
from app.modules.tenants.service import ProvisionRequest, TenantAdmin, TenantDetail


def tenant_admin(request: Request) -> TenantAdmin:
    admin: TenantAdmin = request.app.state.tenant_admin
    return admin


Admin = Annotated[TenantAdmin, Depends(tenant_admin)]
Sort = Annotated[
    tuple[SortField, ...],
    Depends(sort_param(allowed={"name", "status", "created_at"}, default="-created_at")),
]


def tenant_out(row: TenantRow) -> TenantOut:
    return TenantOut(
        id=row.id,
        name=row.name,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        version=row.version,
    )


def detail_out(detail: TenantDetail) -> TenantDetailOut:
    owner = detail.owner
    return TenantDetailOut(
        **tenant_out(detail.tenant).model_dump(),
        owner=TenantOwnerOut(
            display_name=owner.display_name, email=owner.email, status=owner.membership_status
        )
        if owner
        else None,
    )


tenant_routes = APIRouter(prefix="/tenants", tags=["platform-tenants"])


@tenant_routes.get("", dependencies=[require_permission(TENANT_READ)])
async def list_tenants(
    admin: Admin,
    page: Pagination,
    sort: Sort,
    q: Annotated[str | None, Query(max_length=200)] = None,
    status_filter: Annotated[TenantStatus | None, Query(alias="status")] = None,
) -> ListEnvelope[TenantOut]:
    """Every institute: search by name, filter by status."""
    result = await admin.list_tenants(
        search=q.strip() if q else None,
        status=status_filter,
        sort=sort,
        limit=page.limit,
        offset=page.offset,
    )
    return ListEnvelope.build(
        [tenant_out(row) for row in result.items],
        total=result.total,
        limit=page.limit,
        offset=page.offset,
    )


@tenant_routes.post(
    "", status_code=status.HTTP_201_CREATED, dependencies=[require_permission(TENANT_CREATE)]
)
async def provision_tenant(
    body: ProvisionTenantRequest, admin: Admin, background: BackgroundTasks, info: Info
) -> Envelope[ProvisionedTenantOut]:
    """Create an institute (``TRIAL``), its primary campus, system roles and owner invitation."""
    result = await admin.provision(
        ProvisionRequest(
            name=body.name,
            campus_name=body.campus.name,
            campus_code=body.campus.code,
            owner_email=body.owner.email,
            owner_display_name=body.owner.display_name,
        )
    )
    background.add_task(send_email_safely, admin.email_sender, result.email, info.request_id)
    return Envelope(
        data=ProvisionedTenantOut(
            tenant=detail_out(result.detail),
            campus=CampusOut(id=result.campus.id, name=result.campus.name, code=result.campus.code),
            owner_account=cast(Literal["new", "existing"], result.owner_account),
        )
    )


@tenant_routes.get("/{tenant_id}", dependencies=[require_permission(TENANT_READ)])
async def read_tenant(tenant_id: uuid.UUID, admin: Admin) -> Envelope[TenantDetailOut]:
    return Envelope(data=detail_out(await admin.get_tenant(tenant_id)))


@tenant_routes.post("/{tenant_id}/suspend", dependencies=[require_permission(TENANT_SUSPEND)])
async def suspend_tenant(
    tenant_id: uuid.UUID, body: TenantTransitionRequest, admin: Admin
) -> Envelope[TenantDetailOut]:
    """Suspend (step-up, reason); every live session in the institute ends."""
    detail = await admin.suspend(tenant_id, reason=body.reason, version=body.version)
    return Envelope(data=detail_out(detail))


@tenant_routes.post("/{tenant_id}/reactivate", dependencies=[require_permission(TENANT_REACTIVATE)])
async def reactivate_tenant(
    tenant_id: uuid.UUID, body: TenantTransitionRequest, admin: Admin
) -> Envelope[TenantDetailOut]:
    """Reactivate a suspended institute (step-up, reason); ended sessions stay ended."""
    detail = await admin.reactivate(tenant_id, reason=body.reason, version=body.version)
    return Envelope(data=detail_out(detail))


@tenant_routes.post(
    "/{tenant_id}/owner-invitation/resend",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[require_permission(TENANT_CREATE)],
)
async def resend_owner_invitation(
    tenant_id: uuid.UUID, admin: Admin, background: BackgroundTasks, info: Info
) -> None:
    """A new owner invitation while the administrator has not joined (D7-8)."""
    message = await admin.resend_owner_invitation(tenant_id)
    background.add_task(send_email_safely, admin.email_sender, message, info.request_id)
