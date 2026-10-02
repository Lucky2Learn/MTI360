"""The trusted tenant of a database session (T01-03; ADR-0014).

The tenant is always the one :func:`app.core.db.session.context_transaction`
published for the session's transaction (``SET LOCAL app.tenant_id``) and
recorded in ``session.info``. It is never taken from arguments or request
input, so the ORM filter, the repositories and Row-Level Security cannot
disagree about it.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.context import MissingContextError
from app.core.db.session import session_context


class MissingTenantContextError(MissingContextError):
    """Tenant-scoped data was accessed without a trusted tenant (fails closed → 500)."""


class TenantMismatchError(RuntimeError):
    """A tenant-scoped row claims another tenant than the trusted context (→ 500)."""


def trusted_tenant_id(session: AsyncSession | Session) -> uuid.UUID:
    """The trusted tenant of ``session``; raises when there is none."""
    context = session_context(session)
    if context is None or context.tenant_id is None:
        raise MissingTenantContextError("tenant-scoped data requires a trusted tenant context")
    return context.tenant_id
