"""Trusted transactions for authentication (T01-04 decisions D01 and D02).

Authentication happens before the request has a user or a tenant, but every
identity table is protected by Row-Level Security. Two narrow transaction
kinds, both built on ``context_transaction`` (the same ``SET LOCAL``
mechanism as every request), give the authentication services exactly the
access they need:

**Lookup transaction** (:func:`lookup_transaction`) — anonymous tenant-realm
context plus exactly **one** pre-authentication lookup key, published with
``SET LOCAL`` and matched by equality in the policies of migration ``0004``:

=========================  ==================================================
``app.auth_email``          canonical email → that user and its credential
``app.auth_token_hash``     reset/invitation token HMAC → that token row (and,
                            for an invitation, its membership and tenant name)
``app.session_token_hash``  session token HMAC → that session row
=========================  ==================================================

A key reaches only the single row it names; it can never list users, read a
tenant's data or widen the tenant isolation of ADR-0014.

**Subject transaction** (:func:`subject_transaction`) — once the server has
resolved *who* an operation is about from a lookup (a verified session, a
verified password, a valid token), the work continues as that user (and
optionally a tenant), through the ordinary ``app.user_id`` /
``app.tenant_id`` policies.

Only this module publishes the lookup keys (a test enforces it). The values
come from the server: a canonical email, or an HMAC computed by the server
from the presented token — never a client-supplied hash, tenant or user ID.
Each transaction is short; password hashing runs outside both (D02).
"""

import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.context import Realm, RequestContext
from app.core.db.session import context_transaction
from app.modules.identity.domain import normalize_email
from app.modules.identity.tokens import TOKEN_HASH_PATTERN

AUTH_EMAIL: Final = "app.auth_email"
AUTH_TOKEN_HASH: Final = "app.auth_token_hash"  # noqa: S105 - a setting name
SESSION_TOKEN_HASH: Final = "app.session_token_hash"  # noqa: S105 - a setting name

_SET_LOCAL = text("SELECT set_config(:name, :value, true)")
_HASH = re.compile(TOKEN_HASH_PATTERN)


@dataclass(frozen=True, slots=True)
class LookupKey:
    """Exactly one pre-authentication key (constructed through the factories)."""

    setting: str
    value: str

    @classmethod
    def email(cls, email: str) -> LookupKey:
        canonical = normalize_email(email)
        if canonical != email:
            raise ValueError("the lookup email must already be canonical")
        return cls(AUTH_EMAIL, canonical)

    @classmethod
    def token_hash(cls, value: str) -> LookupKey:
        return cls(AUTH_TOKEN_HASH, _checked_hash(value))

    @classmethod
    def session_token_hash(cls, value: str) -> LookupKey:
        return cls(SESSION_TOKEN_HASH, _checked_hash(value))


def _checked_hash(value: str) -> str:
    if not _HASH.fullmatch(value):
        raise ValueError("not a server-computed token hash")
    return value


@asynccontextmanager
async def lookup_transaction(
    factory: async_sessionmaker[AsyncSession], *, request_id: uuid.UUID, key: LookupKey
) -> AsyncIterator[AsyncSession]:
    """An anonymous tenant-realm transaction with one lookup key published."""
    context = RequestContext(realm=Realm.TENANT, request_id=request_id)
    async with context_transaction(factory, context) as session:
        await session.execute(_SET_LOCAL, {"name": key.setting, "value": key.value})
        yield session


@asynccontextmanager
async def subject_transaction(
    factory: async_sessionmaker[AsyncSession],
    *,
    request_id: uuid.UUID,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
) -> AsyncIterator[AsyncSession]:
    """A tenant-realm transaction acting as a server-resolved user (and tenant)."""
    context = RequestContext(
        realm=Realm.TENANT, request_id=request_id, principal_id=user_id, tenant_id=tenant_id
    )
    async with context_transaction(factory, context) as session:
        yield session
