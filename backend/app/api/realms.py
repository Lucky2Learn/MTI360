"""Realm routers and guards (T01-01; ADR-0005, ADR-0006, tenancy.md §3-§4).

Every API route is mounted through a router created by :func:`realm_router`.
Its guard runs before the handler and before any other dependency, builds the
trusted :class:`RequestContext` and binds it to the request. Code that needs
the context (for example :data:`app.core.db.session.DbSession`) fails if a
route bypasses the realm routers.

Deny by default. Tenant-realm routers resolve the server-side session
(T01-04): the session cookie is re-validated on every request (token, expiry,
revocation, user, membership, tenant status, campus — ``IdentityService.
resolve``) and becomes the context's principal and tenant. Access levels:

* ``AUTHENTICATED`` — a session with an institute and, where required, a
  chosen campus; anything less is ``401``;
* ``SESSION`` — any valid session, institute optional (session routes only,
  D12 and D04 §2.2);
* ``ANONYMOUS`` — no principal (public website, sign-in endpoints).

Unsafe methods need a valid ``X-CSRF-Token`` on session-backed tenant routes
and a same-origin request (``Origin`` in the allow-list, or
``Sec-Fetch-Site: same-origin``) on anonymous tenant routes (ADR-0010 §5,
D14). Platform and student routers still deny every request (T01-06, Phase
04/13); webhook routers stay denied until a provider signature verifier is
attached (Phase 09).

``tests/security`` enumerates every registered route and fails if one is not
guarded (see :func:`route_realm`).

The guard also opens the request's security-event scope (T01-02; ADR-0013
§5). It is a function-scoped dependency resolved before every other one, so
it exits last: after ``DbSession`` has committed or rolled back and released
its connection, and before the response is sent. On exit it flushes the
buffered security events in a fresh transaction — also when the guard itself
denies the request.
"""

import uuid
from collections.abc import AsyncIterator, Callable
from enum import StrEnum
from typing import Final

from fastapi import APIRouter, Depends, Request
from fastapi.dependencies.models import Dependant

from app.core.audit import record_security_event
from app.core.audit.security import security_event_scope
from app.core.context import Realm, RequestContext, bind_context
from app.core.errors import (
    AuthenticationRequiredError,
    ErrorEnvelope,
    SessionRefreshRequiredError,
)
from app.core.ids import new_id
from app.core.net import client_ip
from app.modules.identity.events import CSRF_REJECTED
from app.modules.identity.router import SESSION_COOKIE
from app.modules.identity.service import IdentityService, RequestInfo, ResolvedSession
from app.modules.identity.tokens import csrf_valid

API_PREFIX: Final = "/api/v1"

REALM_PREFIXES: Final[dict[Realm, str]] = {
    Realm.PLATFORM: f"{API_PREFIX}/platform",
    Realm.STUDENT: f"{API_PREFIX}/student",
    Realm.PUBLIC: f"{API_PREFIX}/public",
    Realm.WEBHOOK: f"{API_PREFIX}/webhooks",
    Realm.TENANT: API_PREFIX,
}
"""ADR-0006. The tenant realm owns the remaining ``/api/v1/*`` paths."""


class Access(StrEnum):
    AUTHENTICATED = "authenticated"
    SESSION = "session"
    """A valid session without the institute/campus requirement (tenant realm only)."""
    ANONYMOUS = "anonymous"


_ANONYMOUS_REALMS: Final = frozenset({Realm.PUBLIC, Realm.TENANT, Realm.STUDENT, Realm.PLATFORM})

_ERROR_RESPONSES: Final[dict[int | str, dict[str, object]]] = {
    status: {"model": ErrorEnvelope} for status in (401, 403, 404, 422, 429, 500, 503)
}

CSRF_HEADER: Final = "x-csrf-token"
SAFE_METHODS: Final = frozenset({"GET", "HEAD", "OPTIONS"})

type Guard = Callable[[Request], AsyncIterator[RequestContext]]

_GUARD_ATTRIBUTE: Final = "__mti360_realm__"


def _same_origin(request: Request, service: IdentityService) -> bool:
    """D14: the browser says the request comes from our own origin."""
    origin = request.headers.get("origin")
    if origin is not None:
        return origin in service.config.allowed_origins
    return request.headers.get("sec-fetch-site") == "same-origin"


async def _resolve_tenant_session(request: Request, request_id: uuid.UUID) -> ResolvedSession:
    service: IdentityService = request.app.state.identity
    info = RequestInfo(
        request_id=request_id,
        ip=client_ip(request, request.app.state.settings.trusted_proxy_hops),
        user_agent=request.headers.get("user-agent"),
    )
    return await service.resolve(request.cookies.get(SESSION_COOKIE), info)


def _make_guard(realm: Realm, access: Access) -> Guard:
    async def guard(request: Request) -> AsyncIterator[RequestContext]:
        request_id = getattr(request.state, "request_id", None) or new_id()
        context = RequestContext(realm=realm, request_id=request_id)
        resolved: ResolvedSession | None = None
        session_backed = realm is Realm.TENANT and access is not Access.ANONYMOUS
        if session_backed:
            # Its own short transactions, before the request transaction (D02).
            resolved = await _resolve_tenant_session(request, request_id)
            if access is Access.AUTHENTICATED and not resolved.ready:
                raise AuthenticationRequiredError()
            context = RequestContext(
                realm=realm,
                request_id=request_id,
                principal_id=resolved.user_id,
                tenant_id=resolved.tenant_id,
                permissions=resolved.permissions,
                all_campuses=resolved.all_campuses,
                campus_ids=resolved.campus_ids,
            )
            request.state.auth_session = resolved
        bind_context(request, context)
        async with security_event_scope(request.app.state.sessionmaker, context):
            if access is not Access.ANONYMOUS and not session_backed:
                # Platform / student / webhook authentication: T01-06, Phase 04/13, 09.
                raise AuthenticationRequiredError()
            if request.method not in SAFE_METHODS and realm is Realm.TENANT:
                service: IdentityService = request.app.state.identity
                if resolved is not None:
                    trusted = csrf_valid(
                        service.config.csrf_secret,
                        resolved.session_id,
                        request.headers.get(CSRF_HEADER),
                    )
                else:
                    trusted = _same_origin(request, service)
                if not trusted:
                    record_security_event(CSRF_REJECTED, metadata={"session": resolved is not None})
                    raise SessionRefreshRequiredError()
            yield context

    guard.__name__ = f"{realm.value}_{access.value}_guard"
    setattr(guard, _GUARD_ATTRIBUTE, (realm, access))
    return guard


def realm_router(realm: Realm, *, access: Access = Access.AUTHENTICATED) -> APIRouter:
    """Router whose routes all belong to ``realm`` and pass its guard first."""
    if realm is Realm.SYSTEM:
        raise ValueError("the system realm has no HTTP routes")
    if access is Access.SESSION and realm is not Realm.TENANT:
        raise ValueError("session access exists only in the tenant realm")
    if access is Access.ANONYMOUS and realm not in _ANONYMOUS_REALMS:
        raise ValueError(f"the {realm.value} realm has no anonymous routes")
    return APIRouter(
        # scope="function": the guard exits before the response is sent.
        dependencies=[Depends(_make_guard(realm, access), scope="function")],
        responses=_ERROR_RESPONSES,
    )


def _guards(dependant: Dependant) -> list[tuple[Realm, Access]]:
    found: list[tuple[Realm, Access]] = []
    for sub in dependant.dependencies:
        marker = getattr(sub.call, _GUARD_ATTRIBUTE, None)
        if marker is not None:
            found.append(marker)
        found.extend(_guards(sub))
    return found


def realm_for_path(path: str) -> Realm | None:
    """The realm that owns an API path by prefix (ADR-0006), or ``None`` outside ``/api``."""
    for realm, prefix in REALM_PREFIXES.items():
        if realm is not Realm.TENANT and (path == prefix or path.startswith(f"{prefix}/")):
            return realm
    if path == API_PREFIX or path.startswith(f"{API_PREFIX}/"):
        return Realm.TENANT
    return None


def route_realm(route: object) -> tuple[Realm, Access] | None:
    """The realm guard of a route, or ``None`` when the route is unguarded.

    Accepts an ``APIRoute`` or a ``fastapi.routing.RouteContext`` (the effective
    route of an included router, from ``iter_route_contexts(app.routes)``). A
    route with more than one guard is a configuration error.
    """
    dependant: Dependant | None = getattr(route, "dependant", None)
    if dependant is None:
        return None
    guards = _guards(dependant)
    if len(guards) > 1:
        raise ValueError(f"route {getattr(route, 'path', '?')} has more than one realm guard")
    return guards[0] if guards else None
