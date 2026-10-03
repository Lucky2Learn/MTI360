"""Request context (T01-01; tenancy.md §3, ADR-0004).

A :class:`RequestContext` is built once per request by the realm guard of the
router that matched (``app/api``) and is the ONLY trusted source of realm,
principal and tenant for services, repositories, the database session
(``SET LOCAL``) and logs. It is never built from request input.

Fields are added by the tasks that establish them: the principal and active
tenant in T01-04, campus scope and permissions in T01-05, and the support
session in Phase 02.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from starlette.requests import HTTPConnection


class Realm(StrEnum):
    """Security realms (ADR-0005, ADR-0006)."""

    PLATFORM = "platform"
    TENANT = "tenant"
    STUDENT = "student"
    PUBLIC = "public"
    WEBHOOK = "webhook"
    SYSTEM = "system"
    """Background jobs, command-line tools and migrations — never an HTTP request."""


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestContext:
    """Trusted, server-derived context of one request or job."""

    realm: Realm
    request_id: uuid.UUID
    principal_id: uuid.UUID | None = None
    tenant_id: uuid.UUID | None = None
    # Authorization (T01-05), resolved server-side with the session. Effective
    # permission codes in the active tenant (tenant-wide ones only with
    # all-campus access, D-B1) and the member's permitted campuses.
    permissions: frozenset[str] = frozenset()
    all_campuses: bool = False
    campus_ids: frozenset[uuid.UUID] = frozenset()
    # When the session last completed MFA (T01-06): sign-in or step-up. Read by
    # authorize() for permissions that require a fresh MFA verification.
    mfa_verified_at: datetime | None = None


class MissingContextError(RuntimeError):
    """Raised when code that needs a context runs outside a realm router.

    This is a programming error (a route mounted outside ``app/api`` or a
    service called without context) and results in a 500 response.
    """


_request_id: ContextVar[uuid.UUID | None] = ContextVar("mti360_request_id", default=None)
_context: ContextVar[RequestContext | None] = ContextVar("mti360_request_context", default=None)


def current_request_id() -> uuid.UUID | None:
    """Correlation ID of the current request (set by the request middleware)."""
    return _request_id.get()


def bind_request_id(request_id: uuid.UUID) -> Token[uuid.UUID | None]:
    return _request_id.set(request_id)


def reset_request_id(token: Token[uuid.UUID | None]) -> None:
    _request_id.reset(token)


def bind_context(connection: HTTPConnection, context: RequestContext) -> None:
    """Attach the context to the request and the current execution context."""
    connection.state.context = context
    _context.set(context)


@contextmanager
def context_scope(context: RequestContext) -> Iterator[RequestContext]:
    """Bind ``context`` outside an HTTP request; restore the previous one on exit.

    For trusted server-side code only (``app.core.tenancy.system_context``,
    T01-03). The previous context is restored even when the block raises.
    """
    token = _context.set(context)
    try:
        yield context
    finally:
        _context.reset(token)


def clear_context() -> None:
    """Forget the request's context when the request ends (request middleware).

    Production serves every request in its own task, but an in-process caller
    (tests, ASGI transports) runs the application in its own task: without
    this, the context would outlive the request.
    """
    _context.set(None)


def current_context() -> RequestContext:
    """The context of the current request; raises if there is none."""
    context = _context.get()
    if context is None:
        raise MissingContextError("no request context is bound")
    return context


def optional_context() -> RequestContext | None:
    """The context if one is bound (used by logging)."""
    return _context.get()


def request_context(connection: HTTPConnection) -> RequestContext:
    """The context attached to this request by its realm guard."""
    context: RequestContext | None = getattr(connection.state, "context", None)
    if context is None:
        raise MissingContextError("route is not mounted under a realm router")
    return context
