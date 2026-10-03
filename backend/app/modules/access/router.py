"""Tenant roles and the permission catalogue (T01-08). Mounted by ``app.api.tenant``.

``/api/v1/roles*`` and ``/api/v1/permissions`` over the T01-05 access service
(custom roles only; system roles are immutable, D-B2; no escalation,
ADR-0011 §5), in the request transaction (``DbSession``). Role assignment is
on the member routes (``/api/v1/members/{id}/roles``).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.authz import require_permission
from app.core.db.session import DbSession
from app.core.schemas import Envelope, ListEnvelope
from app.modules.access import service
from app.modules.access.permissions import ROLE_CREATE, ROLE_DELETE, ROLE_READ, ROLE_UPDATE
from app.modules.access.repository import RoleDetail
from app.modules.access.schemas import (
    CreateRoleRequest,
    PermissionOut,
    RoleOut,
    UpdateRoleRequest,
)


def role_out(role: RoleDetail) -> RoleOut:
    return RoleOut(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=list(role.permissions),
        member_count=role.member_count,
        version=role.version,
    )


role_routes = APIRouter(tags=["tenant-roles"])


@role_routes.get("/permissions", dependencies=[require_permission(ROLE_READ)])
async def list_permissions() -> ListEnvelope[PermissionOut]:
    """The tenant permissions a custom role may hold."""
    items = [
        PermissionOut(
            code=p.code,
            scope=p.scope.value if p.scope else "tenant",
            description=p.description,
            module=p.module,
        )
        for p in service.permission_catalogue()
    ]
    return ListEnvelope.build(items, total=len(items), limit=len(items), offset=0)


@role_routes.get("/roles", dependencies=[require_permission(ROLE_READ)])
async def list_roles(db: DbSession) -> ListEnvelope[RoleOut]:
    """System roles first, then custom roles by name."""
    roles = await service.list_roles(db)
    return ListEnvelope.build(
        [role_out(role) for role in roles], total=len(roles), limit=len(roles), offset=0
    )


@role_routes.get("/roles/{role_id}", dependencies=[require_permission(ROLE_READ)])
async def read_role(role_id: uuid.UUID, db: DbSession) -> Envelope[RoleOut]:
    return Envelope(data=role_out(await service.get_role(db, role_id)))


@role_routes.post(
    "/roles", status_code=status.HTTP_201_CREATED, dependencies=[require_permission(ROLE_CREATE)]
)
async def create_role(body: CreateRoleRequest, db: DbSession) -> Envelope[RoleOut]:
    """A custom role with permissions the caller holds (no escalation)."""
    role_id = await service.create_role(
        db, name=body.name, description=body.description, permissions=body.permissions
    )
    return Envelope(data=role_out(await service.get_role(db, role_id)))


@role_routes.patch("/roles/{role_id}", dependencies=[require_permission(ROLE_UPDATE)])
async def update_role(
    role_id: uuid.UUID, body: UpdateRoleRequest, db: DbSession
) -> Envelope[RoleOut]:
    await service.update_role(
        db,
        role_id,
        expected_version=body.version,
        name=body.name,
        description=body.description,
        permissions=body.permissions,
    )
    return Envelope(data=role_out(await service.get_role(db, role_id)))


@role_routes.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_permission(ROLE_DELETE)],
)
async def delete_role(
    role_id: uuid.UUID, db: DbSession, version: Annotated[int, Query(ge=1)]
) -> None:
    """Delete an unassigned custom role (409 while members hold it)."""
    await service.delete_role(db, role_id, expected_version=version)
