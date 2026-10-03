"""Campuses and the institute summary for tenant administrators (T01-08).

Campuses are tenant-owned rows read and written through
:class:`CampusRepository` (T01-03: trusted tenant, ORM filter, RLS) in the
request transaction. Authorization follows D-B1: ``campus.read`` and
``campus.update`` are campus-scoped (a campus outside the member's campuses
is not found), ``campus.create`` is tenant-wide. The code is immutable after
creation (INC-41); campus status and archival are not defined yet (INC-40).
The institute summary is read-only (``tenant.profile.read``); its name and
status belong to the platform (T01-07).
"""

import re
import uuid
from dataclasses import dataclass
from typing import Final, cast

from sqlalchemy import Table, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditTarget, write_audit_event
from app.core.authz import Permission, authorize
from app.core.context import RequestContext, current_context
from app.core.errors import ConflictError, ErrorDetail, NotFoundError, ValidationFailedError
from app.core.tenancy import TenantScopedRepository
from app.modules.institute import events
from app.modules.institute.models import CAMPUS_CODE_MAX_LENGTH, CAMPUS_CODE_PATTERN, Campus
from app.modules.institute.permissions import CAMPUS_CREATE, CAMPUS_READ, CAMPUS_UPDATE
from app.modules.tenants.domain import TenantStatus
from app.modules.tenants.models import Tenant
from app.modules.tenants.permissions import TENANT_PROFILE_READ

NAME_MAX_LENGTH: Final = 200
_CODE = re.compile(CAMPUS_CODE_PATTERN)
TENANTS = cast(Table, Tenant.__table__)


class CampusRepository(TenantScopedRepository[Campus]):
    model = Campus

    async def code_taken(self, code: str) -> bool:
        found = await self._session.scalar(self.select().where(Campus.code == code))
        return found is not None


@dataclass(frozen=True, slots=True)
class CampusResource:
    """A campus as an authorization resource: its campus is itself."""

    tenant_id: uuid.UUID
    campus_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class InstituteSummary:
    name: str
    status: TenantStatus


def _invalid(field: str, code: str, message: str) -> ValidationFailedError:
    return ValidationFailedError(details=[ErrorDetail(field=field, code=code, message=message)])


def _name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned or len(cleaned) > NAME_MAX_LENGTH:
        raise _invalid("name", "invalid", "Enter a name of up to 200 characters.")
    return cleaned


def _resource(campus: Campus) -> CampusResource:
    return CampusResource(campus.tenant_id, campus.id)


async def _campus(
    db: AsyncSession, context: RequestContext, campus_id: uuid.UUID, permission: Permission
) -> Campus:
    found = await CampusRepository(db).find(campus_id)
    if found is None:
        raise NotFoundError()
    authorize(context, permission, _resource(found))
    return found


async def institute(db: AsyncSession) -> InstituteSummary:
    context = current_context()
    authorize(context, TENANT_PROFILE_READ)
    row = (
        await db.execute(
            select(TENANTS.c.name, TENANTS.c.status).where(TENANTS.c.id == context.tenant_id)
        )
    ).one_or_none()
    if row is None:
        raise NotFoundError()
    return InstituteSummary(row.name, TenantStatus(row.status))


async def list_campuses(db: AsyncSession) -> list[Campus]:
    """The member's campuses: all of them with all-campus access, else the permitted ones."""
    context = current_context()
    authorize(context, CAMPUS_READ)
    statement = CampusRepository(db).select().order_by(Campus.name, Campus.id)
    if not context.all_campuses:
        statement = statement.where(Campus.id.in_(context.campus_ids))
    return list((await db.scalars(statement)).all())


async def get_campus(db: AsyncSession, campus_id: uuid.UUID) -> Campus:
    context = current_context()
    authorize(context, CAMPUS_READ)
    return await _campus(db, context, campus_id, CAMPUS_READ)


async def create_campus(db: AsyncSession, *, name: str, code: str) -> Campus:
    context = current_context()
    authorize(context, CAMPUS_CREATE)
    clean_code = code.strip().upper()
    if len(clean_code) > CAMPUS_CODE_MAX_LENGTH or not _CODE.fullmatch(clean_code):
        raise _invalid(
            "code",
            "invalid",
            "Use up to 32 letters, digits or hyphens, starting with a letter or digit.",
        )
    repository = CampusRepository(db)
    if await repository.code_taken(clean_code):
        raise ConflictError("A campus with this code already exists.")
    campus = await repository.add(Campus(name=_name(name), code=clean_code))
    try:
        await db.flush()
    except IntegrityError:  # created concurrently
        raise ConflictError("A campus with this code already exists.") from None
    await db.refresh(campus)  # server-side timestamps for the response
    await write_audit_event(
        db,
        events.CAMPUS_CREATED,
        target=AuditTarget("campus", campus.id),
        metadata={"code": clean_code},
    )
    return campus


async def update_campus(
    db: AsyncSession, campus_id: uuid.UUID, *, name: str, version: int
) -> Campus:
    """Rename a campus (optimistic ``version``); the code never changes."""
    context = current_context()
    authorize(context, CAMPUS_UPDATE)
    campus = await _campus(db, context, campus_id, CAMPUS_UPDATE)
    if campus.version != version:
        raise ConflictError("This campus was changed by someone else. Reload and try again.")
    previous, campus.name = campus.name, _name(name)
    await db.flush()
    await db.refresh(campus)
    await write_audit_event(
        db,
        events.CAMPUS_UPDATED,
        target=AuditTarget("campus", campus.id),
        metadata={"name_changed": previous != campus.name},
    )
    return campus
