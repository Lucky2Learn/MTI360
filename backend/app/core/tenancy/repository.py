"""Tenant-scoped repository (T01-03; ADR-0004 layer 2, ADR-0014).

The base class of every repository of a tenant-owned model::

    class CampusRepository(TenantScopedRepository[Campus]):
        model = Campus

* Every query is filtered by the trusted tenant of the session (in addition
  to the automatic ORM filter and Row-Level Security).
* :meth:`get` matches ``id AND tenant_id``: another tenant's row is reported
  exactly like a missing one (``NotFoundError`` → 404), never as forbidden.
* :meth:`add` stamps ``tenant_id`` from the trusted context and rejects an
  entity that already claims a different tenant.
* There is deliberately no delete method: tenant-owned rows are not
  hard-deleted in T01-03.

The repository never commits; the request (or ``system_context``) owns the
transaction.
"""

import uuid
from collections.abc import Sequence
from typing import ClassVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.tenancy.context import TenantMismatchError, trusted_tenant_id
from app.core.tenancy.mixins import TenantScopedMixin


class TenantScopedRepository[ModelT: TenantScopedMixin]:
    model: ClassVar[type[TenantScopedMixin]]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def tenant_id(self) -> uuid.UUID:
        """The trusted tenant; raises ``MissingTenantContextError`` when there is none."""
        return trusted_tenant_id(self._session)

    def _model(self) -> type[ModelT]:
        return self.model  # type: ignore[return-value]

    def select(self) -> Select[tuple[ModelT]]:
        """``SELECT`` of the model restricted to the trusted tenant."""
        model = self._model()
        return select(model).where(model.tenant_id == self.tenant_id)

    async def find(self, entity_id: uuid.UUID) -> ModelT | None:
        """The entity of the trusted tenant with this ID, or ``None``."""
        model = self._model()
        result = await self._session.execute(self.select().where(model.id == entity_id))
        return result.scalar_one_or_none()

    async def get(self, entity_id: uuid.UUID) -> ModelT:
        """Like :meth:`find`, but a miss (including another tenant's row) is a 404."""
        entity = await self.find(entity_id)
        if entity is None:
            raise NotFoundError()
        return entity

    async def list(self, *, limit: int, offset: int) -> Sequence[ModelT]:
        """A page of the trusted tenant's entities in ID (creation) order."""
        model = self._model()
        statement = self.select().order_by(model.id).limit(limit).offset(offset)
        return (await self._session.execute(statement)).scalars().all()

    async def count(self) -> int:
        model = self._model()
        statement = select(func.count()).select_from(model).where(model.tenant_id == self.tenant_id)
        return (await self._session.execute(statement)).scalar_one()

    async def add(self, entity: ModelT) -> ModelT:
        """Stamp the trusted tenant on ``entity``, insert it and flush."""
        tenant_id = self.tenant_id
        if entity.tenant_id is not None and entity.tenant_id != tenant_id:
            raise TenantMismatchError("entity belongs to another tenant than the trusted context")
        entity.tenant_id = tenant_id
        self._session.add(entity)
        await self._session.flush()
        return entity
