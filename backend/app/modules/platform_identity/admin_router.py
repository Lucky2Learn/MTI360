"""Platform user administration routes (T01-07). Mounted by ``app.api.platform``.

* ``admin_routes`` (``/api/v1/platform/platform-users*``) — an MFA-verified
  platform session and one ``require_permission`` per route; the service
  authorizes again (step-up for create, update, suspend, reactivate and MFA
  reset, D6-5/D7-4).
* ``invitation_routes`` (``/api/v1/platform/auth/invitations/*``) — public:
  preview and acceptance of a platform invitation with its single-use token
  (D7-3); the realm guard requires a same-origin request.

Invitation emails are sent after the response (D10).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status

from app.core.authz import require_permission
from app.core.pagination import Pagination, SortField, sort_param
from app.core.schemas import Envelope, ListEnvelope
from app.modules.identity.service import send_email_safely
from app.modules.platform_identity.admin import AdminUser, PlatformUserAdmin
from app.modules.platform_identity.admin_schemas import (
    CreatePlatformUserRequest,
    MfaResetOut,
    MfaResetRequest,
    PlatformInvitationAcceptRequest,
    PlatformInvitationPreviewOut,
    PlatformInvitationPreviewRequest,
    PlatformUserAdminOut,
    ReasonedChangeRequest,
    UpdatePlatformUserRequest,
)
from app.modules.platform_identity.domain import PlatformUserStatus
from app.modules.platform_identity.permissions import (
    PLATFORM_USER_CREATE,
    PLATFORM_USER_REACTIVATE,
    PLATFORM_USER_READ,
    PLATFORM_USER_SUSPEND,
    PLATFORM_USER_UPDATE,
)
from app.modules.platform_identity.roles import PlatformRole
from app.modules.platform_identity.router import Info


def platform_users(request: Request) -> PlatformUserAdmin:
    admin: PlatformUserAdmin = request.app.state.platform_users
    return admin


Admin = Annotated[PlatformUserAdmin, Depends(platform_users)]
Sort = Annotated[
    tuple[SortField, ...],
    Depends(
        sort_param(
            allowed={"display_name", "email", "status", "created_at"}, default="display_name"
        )
    ),
]


def user_out(user: AdminUser) -> PlatformUserAdminOut:
    return PlatformUserAdminOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        roles=list(user.roles),
        created_at=user.created_at,
        updated_at=user.updated_at,
        version=user.version,
    )


admin_routes = APIRouter(prefix="/platform-users", tags=["platform-users"])
invitation_routes = APIRouter(prefix="/auth/invitations", tags=["platform-authentication"])


@admin_routes.get("", dependencies=[require_permission(PLATFORM_USER_READ)])
async def list_platform_users(
    admin: Admin,
    page: Pagination,
    sort: Sort,
    q: Annotated[str | None, Query(max_length=200)] = None,
    status_filter: Annotated[PlatformUserStatus | None, Query(alias="status")] = None,
    role: PlatformRole | None = None,
) -> ListEnvelope[PlatformUserAdminOut]:
    """The platform user directory: search by name or email, filter by status and role."""
    result = await admin.list_users(
        search=q.strip() if q else None,
        status=status_filter,
        role=role,
        sort=sort,
        limit=page.limit,
        offset=page.offset,
    )
    return ListEnvelope.build(
        [user_out(user) for user in result.items],
        total=result.total,
        limit=page.limit,
        offset=page.offset,
    )


@admin_routes.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(PLATFORM_USER_CREATE)],
)
async def create_platform_user(
    body: CreatePlatformUserRequest, admin: Admin, background: BackgroundTasks, info: Info
) -> Envelope[PlatformUserAdminOut]:
    """Invite a platform user (``INVITED``); the invitation is emailed after the response."""
    created = await admin.create_user(body.email, body.display_name, body.roles)
    background.add_task(
        send_email_safely, admin.identity.email_sender, created.email, info.request_id
    )
    return Envelope(data=user_out(created.user))


@admin_routes.get("/{user_id}", dependencies=[require_permission(PLATFORM_USER_READ)])
async def read_platform_user(user_id: uuid.UUID, admin: Admin) -> Envelope[PlatformUserAdminOut]:
    return Envelope(data=user_out(await admin.get_user(user_id)))


@admin_routes.patch("/{user_id}", dependencies=[require_permission(PLATFORM_USER_UPDATE)])
async def update_platform_user(
    user_id: uuid.UUID, body: UpdatePlatformUserRequest, admin: Admin
) -> Envelope[PlatformUserAdminOut]:
    """Change the display name and/or roles (step-up; never one's own roles)."""
    updated = await admin.update_user(
        user_id, version=body.version, display_name=body.display_name, roles=body.roles
    )
    return Envelope(data=user_out(updated))


@admin_routes.post("/{user_id}/suspend", dependencies=[require_permission(PLATFORM_USER_SUSPEND)])
async def suspend_platform_user(
    user_id: uuid.UUID, body: ReasonedChangeRequest, admin: Admin
) -> Envelope[PlatformUserAdminOut]:
    """Suspend (step-up, reason); the user's sessions and open invitations end."""
    user = await admin.suspend_user(user_id, reason=body.reason, version=body.version)
    return Envelope(data=user_out(user))


@admin_routes.post(
    "/{user_id}/reactivate", dependencies=[require_permission(PLATFORM_USER_REACTIVATE)]
)
async def reactivate_platform_user(
    user_id: uuid.UUID, body: ReasonedChangeRequest, admin: Admin
) -> Envelope[PlatformUserAdminOut]:
    """Reactivate (step-up, reason); MFA stays required at the next sign-in."""
    user = await admin.reactivate_user(user_id, reason=body.reason, version=body.version)
    return Envelope(data=user_out(user))


@admin_routes.post(
    "/{user_id}/invitation",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[require_permission(PLATFORM_USER_CREATE)],
)
async def resend_platform_invitation(
    user_id: uuid.UUID, admin: Admin, background: BackgroundTasks, info: Info
) -> None:
    """A new invitation for a user who has not joined; the previous link stops working."""
    message = await admin.resend_invitation(user_id)
    background.add_task(send_email_safely, admin.identity.email_sender, message, info.request_id)


@admin_routes.post("/{user_id}/mfa/reset", dependencies=[require_permission(PLATFORM_USER_UPDATE)])
async def reset_platform_user_mfa(
    user_id: uuid.UUID, body: MfaResetRequest, admin: Admin
) -> Envelope[MfaResetOut]:
    """Lost device (D6-3): disables MFA, ends sessions, forces re-enrolment (step-up, reason)."""
    result = await admin.reset_mfa(user_id, body.reason)
    return Envelope(
        data=MfaResetOut(
            factors_disabled=result.factors_disabled, sessions_revoked=result.sessions_revoked
        )
    )


@invitation_routes.post("/preview")
async def preview_platform_invitation(
    body: PlatformInvitationPreviewRequest, admin: Admin, info: Info
) -> Envelope[PlatformInvitationPreviewOut]:
    """The masked email of a usable invitation; one generic 404 otherwise."""
    preview = await admin.preview_invitation(body.token, info)
    return Envelope(data=PlatformInvitationPreviewOut(email=preview.email))


@invitation_routes.post("/accept", status_code=status.HTTP_204_NO_CONTENT)
async def accept_platform_invitation(
    body: PlatformInvitationAcceptRequest, admin: Admin, info: Info
) -> None:
    """Set the first password; sign in next and enrol MFA (D6-1, D6-4)."""
    await admin.accept_invitation(body.token, body.password, info)
