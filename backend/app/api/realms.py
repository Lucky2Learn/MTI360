"""Realm routers and guards (T01-01; ADR-0005, ADR-0006, tenancy.md §3-§4).

Every API route is mounted through a router created by :func:`realm_router`.
Its guard runs before the handler and before any other dependency, builds the
trusted :class:`RequestContext` and binds it to the request. Code that needs
the context (for example :data:`app.core.db.session.DbSession`) fails if a
route bypasses the realm routers.

Deny by default (T01-01): authentication does not exist yet, so the guard of
every authenticated router rejects every request with
``401 AUTHENTICATION_REQUIRED``. T01-04 (tenant/student) and T01-06 (platform)
replace the rejection with session resolution. Webhook routers stay denied
until a provider signature verifier is attached (Phase 09). Anonymous routers
(public website, sign-in endpoints) establish the realm without a principal.

``tests/security`` enumerates every registered route and fails if one is not
guarded (see :func:`route_realm`).
"""

from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Final

from fastapi import APIRouter, Depends, Request
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from app.core.context import Realm, RequestContext, bind_context
from app.core.errors import AuthenticationRequiredError, ErrorEnvelope
from app.core.ids import new_id

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
    ANONYMOUS = "anonymous"


_ANONYMOUS_REALMS: Final = frozenset({Realm.PUBLIC, Realm.TENANT, Realm.STUDENT, Realm.PLATFORM})

_ERROR_RESPONSES: Final[dict[int | str, dict[str, object]]] = {
    status: {"model": ErrorEnvelope} for status in (401, 403, 404, 422, 500)
}

type Guard = Callable[[Request], Awaitable[RequestContext]]

_GUARD_ATTRIBUTE: Final = "__mti360_realm__"


def _make_guard(realm: Realm, access: Access) -> Guard:
    async def guard(request: Request) -> RequestContext:
        request_id = getattr(request.state, "request_id", None) or new_id()
        context = RequestContext(realm=realm, request_id=request_id)
        bind_context(request, context)
        if access is Access.AUTHENTICATED:
            # No authentication mechanism exists yet (T01-04 / T01-06).
            raise AuthenticationRequiredError()
        return context

    guard.__name__ = f"{realm.value}_{access.value}_guard"
    setattr(guard, _GUARD_ATTRIBUTE, (realm, access))
    return guard


def realm_router(realm: Realm, *, access: Access = Access.AUTHENTICATED) -> APIRouter:
    """Router whose routes all belong to ``realm`` and pass its guard first."""
    if realm is Realm.SYSTEM:
        raise ValueError("the system realm has no HTTP routes")
    if access is Access.ANONYMOUS and realm not in _ANONYMOUS_REALMS:
        raise ValueError(f"the {realm.value} realm has no anonymous routes")
    return APIRouter(
        dependencies=[Depends(_make_guard(realm, access))],
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


def route_realm(route: APIRoute) -> tuple[Realm, Access] | None:
    """The realm guard of a route, or ``None`` when the route is unguarded.

    A route with more than one guard is a configuration error.
    """
    guards = _guards(route.dependant)
    if len(guards) > 1:
        raise ValueError(f"route {route.path} has more than one realm guard")
    return guards[0] if guards else None
