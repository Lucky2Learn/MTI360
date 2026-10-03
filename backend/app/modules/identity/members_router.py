"""Tenant member administration routes (T01-08). Mounted by ``app.api.tenant``.

``/api/v1/members*`` — a ready tenant session (``Access.AUTHENTICATED``) and
one ``require_permission`` per route; the service authorizes again. The
tenant is always the session's; identifiers in the path are targets within
it (another tenant's member is not found). Invitation emails are sent after
the response (D10).
"""

import uuid
from typing import Annotated, Literal, cast

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status

from app.core.authz import require_permission
from app.core.context import current_context
from app.core.pagination import Pagination, SortField, sort_param
from app.core.schemas import Envelope, ListEnvelope
from app.modules.access.permissions import ROLE_ASSIGN
from app.modules.identity.domain import MembershipStatus
from app.modules.identity.members import Member, MemberAdmin
from app.modules.identity.members_schemas import (
    AssignRoleRequest,
    CampusScopeRequest,
    InvitedMemberOut,
    InviteMemberRequest,
    MemberOut,
    MemberRoleOut,
    MemberUserOut,
    VersionRequest,
)
from app.modules.identity.permissions import (
    MEMBER_INVITE,
    MEMBER_READ,
    MEMBER_REVOKE,
    MEMBER_SUSPEND,
    MEMBER_UPDATE,
)
from app.modules.identity.service import send_email_safely


def member_admin(request: Request) -> MemberAdmin:
    admin: MemberAdmin = request.app.state.members
    return admin


Admin = Annotated[MemberAdmin, Depends(member_admin)]
Sort = Annotated[
    tuple[SortField, ...],
    Depends(
        sort_param(
            allowed={"display_name", "email", "status", "created_at"}, default="display_name"
        )
    ),
]


def member_out(member: Member) -> MemberOut:
    return MemberOut(
        id=member.id,
        user=MemberUserOut(display_name=member.display_name, email=member.email),
        status=member.status,
        campus_scope=member.campus_scope,
        campus_ids=list(member.campus_ids),
        roles=[MemberRoleOut(id=r.id, name=r.name, is_system=r.is_system) for r in member.roles],
        invited_at=member.created_at,
        joined_at=member.joined_at,
        version=member.version,
    )


member_routes = APIRouter(prefix="/members", tags=["tenant-members"])


@member_routes.get("", dependencies=[require_permission(MEMBER_READ)])
async def list_members(
    admin: Admin,
    page: Pagination,
    sort: Sort,
    q: Annotated[str | None, Query(max_length=200)] = None,
    status_filter: Annotated[MembershipStatus | None, Query(alias="status")] = None,
) -> ListEnvelope[MemberOut]:
    """The institute's members: search by name or email, filter by status."""
    result = await admin.list_members(
        search=q.strip() if q else None,
        status=status_filter,
        sort=sort,
        limit=page.limit,
        offset=page.offset,
    )
    return ListEnvelope.build(
        [member_out(member) for member in result.items],
        total=result.total,
        limit=page.limit,
        offset=page.offset,
    )


@member_routes.post(
    "/invitations",
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(MEMBER_INVITE)],
)
async def invite_member(
    body: InviteMemberRequest, admin: Admin, background: BackgroundTasks
) -> Envelope[InvitedMemberOut]:
    """Invite a person (new or existing account) with initial roles and campus scope."""
    invited = await admin.invite(
        raw_email=body.email,
        display_name=body.display_name,
        role_ids=body.role_ids,
        campus_scope=body.campus_scope,
        campus_ids=body.campus_ids,
    )
    background.add_task(
        send_email_safely, admin.email_sender, invited.email, current_context().request_id
    )
    return Envelope(
        data=InvitedMemberOut(
            member=member_out(invited.member),
            account=cast(Literal["new", "existing"], invited.account),
        )
    )


@member_routes.get("/{membership_id}", dependencies=[require_permission(MEMBER_READ)])
async def read_member(membership_id: uuid.UUID, admin: Admin) -> Envelope[MemberOut]:
    return Envelope(data=member_out(await admin.get_member(membership_id)))


@member_routes.post(
    "/{membership_id}/invitation/resend",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[require_permission(MEMBER_INVITE)],
)
async def resend_member_invitation(
    membership_id: uuid.UUID, admin: Admin, background: BackgroundTasks
) -> None:
    """A new invitation while the member has not joined; the previous link stops working."""
    message = await admin.resend_invitation(membership_id)
    background.add_task(
        send_email_safely, admin.email_sender, message, current_context().request_id
    )


@member_routes.post("/{membership_id}/reinvite", dependencies=[require_permission(MEMBER_INVITE)])
async def reinvite_member(
    membership_id: uuid.UUID, body: VersionRequest, admin: Admin, background: BackgroundTasks
) -> Envelope[MemberOut]:
    """Re-invite a removed member (same membership, new invitation)."""
    invited = await admin.reinvite(membership_id, version=body.version)
    background.add_task(
        send_email_safely, admin.email_sender, invited.email, current_context().request_id
    )
    return Envelope(data=member_out(invited.member))


@member_routes.post("/{membership_id}/suspend", dependencies=[require_permission(MEMBER_SUSPEND)])
async def suspend_member(
    membership_id: uuid.UUID, body: VersionRequest, admin: Admin
) -> Envelope[MemberOut]:
    """Suspend; access to the institute ends at the member's next request."""
    return Envelope(data=member_out(await admin.suspend(membership_id, version=body.version)))


@member_routes.post("/{membership_id}/reinstate", dependencies=[require_permission(MEMBER_SUSPEND)])
async def reinstate_member(
    membership_id: uuid.UUID, body: VersionRequest, admin: Admin
) -> Envelope[MemberOut]:
    return Envelope(data=member_out(await admin.reinstate(membership_id, version=body.version)))


@member_routes.post("/{membership_id}/revoke", dependencies=[require_permission(MEMBER_REVOKE)])
async def revoke_member(
    membership_id: uuid.UUID, body: VersionRequest, admin: Admin
) -> Envelope[MemberOut]:
    """Remove from the institute; open invitations stop working."""
    return Envelope(data=member_out(await admin.revoke(membership_id, version=body.version)))


@member_routes.put(
    "/{membership_id}/campus-scope", dependencies=[require_permission(MEMBER_UPDATE)]
)
async def set_member_campus_scope(
    membership_id: uuid.UUID, body: CampusScopeRequest, admin: Admin
) -> Envelope[MemberOut]:
    """All campuses, or a selection of this institute's campuses."""
    member = await admin.set_campus_scope(
        membership_id, scope=body.campus_scope, campus_ids=body.campus_ids, version=body.version
    )
    return Envelope(data=member_out(member))


@member_routes.post("/{membership_id}/roles", dependencies=[require_permission(ROLE_ASSIGN)])
async def assign_member_role(
    membership_id: uuid.UUID, body: AssignRoleRequest, admin: Admin
) -> Envelope[MemberOut]:
    return Envelope(data=member_out(await admin.assign_role(membership_id, body.role_id)))


@member_routes.delete(
    "/{membership_id}/roles/{role_id}", dependencies=[require_permission(ROLE_ASSIGN)]
)
async def remove_member_role(
    membership_id: uuid.UUID, role_id: uuid.UUID, admin: Admin
) -> Envelope[MemberOut]:
    return Envelope(data=member_out(await admin.remove_role(membership_id, role_id)))
