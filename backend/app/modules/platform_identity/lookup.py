"""Trusted transactions for platform authentication (T01-06; the T01-04 D01/D02 pattern).

Every platform table is protected by Row-Level Security (migration ``0006``).
Platform authentication reaches rows through three narrow transaction kinds,
all built on ``context_transaction`` with ``app.realm = 'platform'``:

**Lookup** (:func:`platform_lookup_transaction`) — no principal, plus exactly
**one** pre-authentication key, matched by equality in the policies:

==================================  ==============================================
``app.platform_auth_email``          canonical email → that identity and credential
``app.platform_auth_token_hash``     reset-token HMAC → that token row
``app.platform_session_token_hash``  session-token HMAC → that session row
==================================  ==============================================

**Subject** (:func:`platform_subject_transaction`) — acting as a
server-resolved platform user (``app.platform_user_id``).

**MFA reset** (:func:`mfa_reset_transaction`) — the current, already
authorized platform principal plus ``app.platform_mfa_reset_user_id``: opens
exactly the target's MFA factors, recovery codes and sessions (D6-3).

**Administration** (:func:`admin_target_transaction`, T01-07 D7-2) — the
current, already authorized platform principal plus
``app.platform_admin_target_user_id``: opens exactly that platform user's
row (update; insert while ``INVITED``), roles, sessions and invitations.

``app.platform_auth_token_hash`` also names a platform invitation (T01-07,
D7-3): the lookup opens that invitation, its user and the user's first
credential, so an invitee can set a password before having a session.

Only this module publishes the platform keys (a test enforces it). Values come
from the server: a canonical email, an HMAC computed by the server, or a
target the service has authorized — never client input as such.
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

PLATFORM_AUTH_EMAIL: Final = "app.platform_auth_email"
PLATFORM_AUTH_TOKEN_HASH: Final = "app.platform_auth_token_hash"  # noqa: S105 - a setting name
PLATFORM_SESSION_TOKEN_HASH: Final = "app.platform_session_token_hash"  # noqa: S105 - a name
PLATFORM_MFA_RESET_USER_ID: Final = "app.platform_mfa_reset_user_id"
PLATFORM_ADMIN_TARGET_USER_ID: Final = "app.platform_admin_target_user_id"

_SET_LOCAL = text("SELECT set_config(:name, :value, true)")
_HASH = re.compile(TOKEN_HASH_PATTERN)


@dataclass(frozen=True, slots=True)
class PlatformLookupKey:
    """Exactly one platform pre-authentication key (built through the factories)."""

    setting: str
    value: str

    @classmethod
    def email(cls, email: str) -> PlatformLookupKey:
        if normalize_email(email) != email:
            raise ValueError("the lookup email must already be canonical")
        return cls(PLATFORM_AUTH_EMAIL, email)

    @classmethod
    def token_hash(cls, value: str) -> PlatformLookupKey:
        return cls(PLATFORM_AUTH_TOKEN_HASH, _checked(value))

    @classmethod
    def session_token_hash(cls, value: str) -> PlatformLookupKey:
        return cls(PLATFORM_SESSION_TOKEN_HASH, _checked(value))


def _checked(value: str) -> str:
    if not _HASH.fullmatch(value):
        raise ValueError("not a server-computed token hash")
    return value


@asynccontextmanager
async def platform_lookup_transaction(
    factory: async_sessionmaker[AsyncSession], *, request_id: uuid.UUID, key: PlatformLookupKey
) -> AsyncIterator[AsyncSession]:
    """An anonymous platform-realm transaction with one lookup key published."""
    context = RequestContext(realm=Realm.PLATFORM, request_id=request_id)
    async with context_transaction(factory, context) as session:
        await session.execute(_SET_LOCAL, {"name": key.setting, "value": key.value})
        yield session


@asynccontextmanager
async def platform_subject_transaction(
    factory: async_sessionmaker[AsyncSession], *, request_id: uuid.UUID, user_id: uuid.UUID
) -> AsyncIterator[AsyncSession]:
    """A platform-realm transaction acting as a server-resolved platform user."""
    context = RequestContext(realm=Realm.PLATFORM, request_id=request_id, principal_id=user_id)
    async with context_transaction(factory, context) as session:
        yield session


@asynccontextmanager
async def mfa_reset_transaction(
    factory: async_sessionmaker[AsyncSession],
    *,
    context: RequestContext,
    target_user_id: uuid.UUID,
) -> AsyncIterator[AsyncSession]:
    """The authorized principal's transaction, opened to one MFA-reset target (D6-3)."""
    if context.realm is not Realm.PLATFORM or context.principal_id is None:
        raise ValueError("an MFA reset runs as an authenticated platform principal")
    async with context_transaction(factory, context) as session:
        await session.execute(
            _SET_LOCAL, {"name": PLATFORM_MFA_RESET_USER_ID, "value": str(target_user_id)}
        )
        yield session


@asynccontextmanager
async def admin_target_transaction(
    factory: async_sessionmaker[AsyncSession],
    *,
    context: RequestContext,
    target_user_id: uuid.UUID,
) -> AsyncIterator[AsyncSession]:
    """The authorized principal's transaction, opened to one platform user (D7-2).

    The caller must have run ``authorize()`` (permission and step-up) first.
    """
    if context.realm is not Realm.PLATFORM or context.principal_id is None:
        raise ValueError("platform administration runs as an authenticated platform principal")
    async with context_transaction(factory, context) as session:
        await session.execute(
            _SET_LOCAL, {"name": PLATFORM_ADMIN_TARGET_USER_ID, "value": str(target_user_id)}
        )
        yield session
