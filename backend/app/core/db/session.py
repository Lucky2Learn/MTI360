"""Transaction-per-request database session (T01-01; ARCHITECTURE.md §66).

Handlers and services receive the session through :data:`DbSession`:

* one ``AsyncSession`` and ONE transaction per request, opened before the
  handler runs;
* the trusted request context is published with ``SET LOCAL`` at the start of
  the transaction (Row-Level Security, ADR-0004);
* the transaction commits when the handler returns and rolls back when it
  raises. Repositories and services never commit or roll back themselves;
* the dependency uses FastAPI's ``scope="function"``, so the commit completes
  BEFORE the response is sent. A failed commit therefore becomes an error
  response instead of a success the client already received (FastAPI's
  default "request" scope would run the commit after sending).

Side effects outside the database (email, webhooks, provider calls) happen only
after a successful commit; see docs/architecture/backend-foundation.md §5.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.context import Realm, request_context
from app.core.db.settings import apply_transaction_settings

_USER_REALMS = frozenset({Realm.TENANT, Realm.STUDENT})


async def _transaction(request: Request) -> AsyncIterator[AsyncSession]:
    context = request_context(request)
    factory: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with factory() as session, session.begin():
        await apply_transaction_settings(
            session,
            realm=context.realm.value,
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            # app.user_id identifies a `users` row; platform principals are a
            # separate identity (ADR-0005) and never set it.
            user_id=context.principal_id if context.realm in _USER_REALMS else None,
        )
        yield session


DbSession = Annotated[AsyncSession, Depends(_transaction, scope="function")]
"""The request's transactional session. Use this alias; never create sessions ad hoc."""
