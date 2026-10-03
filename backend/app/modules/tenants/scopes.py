"""Narrow platform scopes into tenant-owned rows (T01-07; D7-1, D7-6, D7-8; INC-39).

A platform request has no trusted tenant, so the realm-agnostic tenant RLS of
ADR-0014 gives it nothing. Platform administration reaches tenant-owned rows
only through three named scopes, all built on ``context_transaction`` and
all used **after** ``authorize()``:

**Provisioning** (:func:`provisioning_transaction`, D7-1) — one transaction
whose trusted tenant is the **new tenant's server-generated ID**, published
as ``app.tenant_id`` and again as ``app.provisioning_tenant_id``. The
ordinary tenant policies admit that tenant's rows (campus, membership, role
assignment, invitation); migration ``0007`` adds only the terms the
provisioning key needs (the tenant's system roles and their permissions, and
an ``INVITED`` owner identity). The context is bound for the block, so the
audit events written inside it carry the new tenant.

**Suspension target** (:func:`publish_suspension_target`, D7-6) —
``app.platform_target_tenant_id``: the sessions whose active institute is the
tenant being suspended, nothing else.

**Owner** (:func:`publish_owner`, D7-8) — ``app.platform_owner_membership_id``:
one owner membership, its invitations and its user.

Only this module publishes these keys or builds a platform context with a
tenant (``tests/security/test_platform_administration_boundaries.py``).
``system_context`` is not used: it refuses to run inside an HTTP request.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.context import Realm, RequestContext, context_scope
from app.core.db.session import context_transaction

PROVISIONING_TENANT_ID: Final = "app.provisioning_tenant_id"
TARGET_TENANT_ID: Final = "app.platform_target_tenant_id"
OWNER_MEMBERSHIP_ID: Final = "app.platform_owner_membership_id"

_SET_LOCAL = text("SELECT set_config(:name, :value, true)")


def _authorized_platform(context: RequestContext) -> None:
    if context.realm is not Realm.PLATFORM or context.principal_id is None:
        raise ValueError("platform scopes run as an authenticated platform principal")
    if context.tenant_id is not None:
        raise ValueError("a platform request never has a tenant of its own")


@asynccontextmanager
async def provisioning_transaction(
    factory: async_sessionmaker[AsyncSession], *, context: RequestContext, tenant_id: uuid.UUID
) -> AsyncIterator[AsyncSession]:
    """The single transaction that creates ``tenant_id`` and its first rows."""
    _authorized_platform(context)
    scoped = replace(context, tenant_id=tenant_id)
    with context_scope(scoped):
        async with context_transaction(factory, scoped) as session:
            await session.execute(
                _SET_LOCAL, {"name": PROVISIONING_TENANT_ID, "value": str(tenant_id)}
            )
            yield session


async def publish_suspension_target(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Open the sessions of ``tenant_id`` (and only them) to revocation."""
    await session.execute(_SET_LOCAL, {"name": TARGET_TENANT_ID, "value": str(tenant_id)})


async def publish_owner(session: AsyncSession, membership_id: uuid.UUID) -> None:
    """Open one owner membership, its invitations and its user."""
    await session.execute(_SET_LOCAL, {"name": OWNER_MEMBERSHIP_ID, "value": str(membership_id)})
