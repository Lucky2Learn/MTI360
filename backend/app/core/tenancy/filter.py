"""Automatic tenant filter for ORM statements (T01-03; ADR-0004 layer 3, ADR-0014).

A ``do_orm_execute`` listener on every SQLAlchemy ``Session`` adds
``with_loader_criteria(TenantScopedMixin, tenant_id = <trusted tenant>,
include_aliases=True)`` to every ORM SELECT, UPDATE and DELETE. The criterion
also applies to joined, aliased and relationship-loaded tenant-scoped
entities, and to ORM bulk UPDATE and DELETE.

* The tenant comes from ``session.info`` (the context ``context_transaction``
  published with ``SET LOCAL``), never from the statement.
* Fails closed: a statement whose entities include a tenant-scoped model
  raises :class:`MissingTenantContextError` without a trusted tenant. Any other
  ORM statement without a tenant gets an always-false criterion, so a
  tenant-scoped entity reached through a join or subquery yields no rows.
* Core statements (``text()``, ``insert(Table)``) are not ORM statements and
  are not rewritten; PostgreSQL Row-Level Security still applies to them.

There is no unscoped escape hatch in T01-03 (ADR-0014, D19).

The listener is installed when this package is imported, which happens
whenever a tenant-scoped model is defined.
"""

from typing import Any

from sqlalchemy import event, false
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from app.core.db.session import session_context
from app.core.tenancy.context import MissingTenantContextError
from app.core.tenancy.mixins import TenantScopedMixin


def _involves_tenant_scoped_entity(state: ORMExecuteState) -> bool:
    return any(issubclass(mapper.class_, TenantScopedMixin) for mapper in state.all_mappers)


def _tenant_criteria(state: ORMExecuteState) -> Any:
    context = session_context(state.session)
    tenant_id = context.tenant_id if context is not None else None
    if tenant_id is None:
        if _involves_tenant_scoped_entity(state):
            raise MissingTenantContextError("tenant-scoped query without a trusted tenant context")
        return with_loader_criteria(TenantScopedMixin, lambda cls: false(), include_aliases=True)
    return with_loader_criteria(
        TenantScopedMixin, lambda cls: cls.tenant_id == tenant_id, include_aliases=True
    )


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_filter(state: ORMExecuteState) -> None:
    # Also refreshes and relationship loads: a criterion they already inherit
    # is merely repeated, and none of them can run unfiltered.
    if state.is_orm_statement and (state.is_select or state.is_update or state.is_delete):
        state.statement = state.statement.options(_tenant_criteria(state))
