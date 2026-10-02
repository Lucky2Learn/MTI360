"""``system_context``: trusted server-side work outside HTTP (T01-03; ADR-0014).

For command-line tools, the development seed and background jobs::

    async with system_context(sessionmaker, tenant_id=tenant_id) as session:
        ...

* Builds ``RequestContext(realm=SYSTEM, request_id=<new UUIDv7>,
  principal_id=None, tenant_id=<trusted caller's value or None>)``.
* Binds it for the block (contextvar token, restored on exit, also on error)
  and opens :func:`context_transaction`: one transaction, the same
  ``SET LOCAL`` context as a request, recorded in ``session.info`` for the
  tenant ORM filter. Commits when the block completes, rolls back when it
  raises.
* Refuses to run while an HTTP request context is bound: a request can never
  switch to the system realm, override its tenant or hold a second
  connection. The system realm has no HTTP routes (``realm_router``).

The tenant is a trusted caller's decision (for example a re-validated job
envelope), never request data.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.context import Realm, RequestContext, context_scope, optional_context
from app.core.db.session import context_transaction
from app.core.ids import new_id


class SystemContextError(RuntimeError):
    """``system_context`` was used inside an HTTP request (a programming error)."""


@asynccontextmanager
async def system_context(
    factory: async_sessionmaker[AsyncSession], *, tenant_id: uuid.UUID | None = None
) -> AsyncIterator[AsyncSession]:
    """A system-realm transaction, optionally scoped to one tenant."""
    current = optional_context()
    if current is not None and current.realm is not Realm.SYSTEM:
        raise SystemContextError("system_context cannot be used inside an HTTP request")
    if tenant_id is not None and not isinstance(tenant_id, uuid.UUID):
        raise TypeError("tenant_id must be a UUID")
    context = RequestContext(realm=Realm.SYSTEM, request_id=new_id(), tenant_id=tenant_id)
    with context_scope(context):
        async with context_transaction(factory, context) as session:
            yield session
