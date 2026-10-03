"""Institute summary and campus routes (T01-08). Mounted by ``app.api.tenant``.

``/api/v1/institute`` (``tenant.profile.read``) and ``/api/v1/campuses*``
(``campus.read`` / ``campus.create`` / ``campus.update``) in the request
transaction (``DbSession``). A campus outside the member's campuses is not
found (D-B1); the active campus is never the authorization boundary.
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, status
from pydantic import Field, StringConstraints

from app.core.authz import require_permission
from app.core.db.session import DbSession
from app.core.schemas import Envelope, ListEnvelope, RequestModel, ResponseModel
from app.modules.institute import service
from app.modules.institute.models import Campus
from app.modules.institute.permissions import CAMPUS_CREATE, CAMPUS_READ, CAMPUS_UPDATE
from app.modules.tenants.domain import TenantStatus
from app.modules.tenants.permissions import TENANT_PROFILE_READ

Name = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class InstituteOut(ResponseModel):
    name: str
    status: TenantStatus
    trial: bool


class CampusOut(ResponseModel):
    id: uuid.UUID
    name: str
    code: str
    created_at: datetime
    updated_at: datetime
    version: int


class CreateCampusRequest(RequestModel):
    name: Name
    code: Annotated[str, StringConstraints(min_length=1, max_length=32)]


class UpdateCampusRequest(RequestModel):
    name: Name
    version: Annotated[int, Field(ge=1)]


def campus_out(campus: Campus) -> CampusOut:
    return CampusOut.model_validate(campus)


institute_routes = APIRouter(tags=["tenant-institute"])


@institute_routes.get("/institute", dependencies=[require_permission(TENANT_PROFILE_READ)])
async def read_institute(db: DbSession) -> Envelope[InstituteOut]:
    summary = await service.institute(db)
    return Envelope(
        data=InstituteOut(
            name=summary.name, status=summary.status, trial=summary.status is TenantStatus.TRIAL
        )
    )


@institute_routes.get("/campuses", dependencies=[require_permission(CAMPUS_READ)])
async def list_campuses(db: DbSession) -> ListEnvelope[CampusOut]:
    campuses = await service.list_campuses(db)
    return ListEnvelope.build(
        [campus_out(campus) for campus in campuses],
        total=len(campuses),
        limit=len(campuses),
        offset=0,
    )


@institute_routes.post(
    "/campuses",
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(CAMPUS_CREATE)],
)
async def create_campus(body: CreateCampusRequest, db: DbSession) -> Envelope[CampusOut]:
    campus = await service.create_campus(db, name=body.name, code=body.code)
    return Envelope(data=campus_out(campus))


@institute_routes.get("/campuses/{campus_id}", dependencies=[require_permission(CAMPUS_READ)])
async def read_campus(campus_id: uuid.UUID, db: DbSession) -> Envelope[CampusOut]:
    return Envelope(data=campus_out(await service.get_campus(db, campus_id)))


@institute_routes.patch("/campuses/{campus_id}", dependencies=[require_permission(CAMPUS_UPDATE)])
async def update_campus(
    campus_id: uuid.UUID, body: UpdateCampusRequest, db: DbSession
) -> Envelope[CampusOut]:
    """Rename a campus; the code never changes."""
    campus = await service.update_campus(db, campus_id, name=body.name, version=body.version)
    return Envelope(data=campus_out(campus))
