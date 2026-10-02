"""The authorization decision (T01-05; ADR-0011 §4, ADR-0016).

``authorize(context, permission, resource=None)`` is the single place where a
permission is checked. It is synchronous and does no I/O: everything it needs
was resolved server-side with the session (T01-04) and put in the trusted
:class:`RequestContext` by the realm guard.

Order (the T01-05 contract):

1. principal — an authenticated principal (401 otherwise);
2. realm — the permission belongs to the request's realm;
3. tenant — tenant permissions need an active tenant (its status was
   validated when the session was resolved, T01-04);
4. permission — the code is among the effective permissions;
5. step-up (T01-06, D6-5) — a ``requires_step_up`` permission needs an MFA
   verification within :data:`STEP_UP_WINDOW` (10 minutes); otherwise
   ``403 STEP_UP_REQUIRED``. It is checked after the permission, so a caller
   without the permission is never asked to step up;
6. campus scope (D-B1) — tenant-wide permissions need all-campus access;
7. resource tenant — another tenant's resource is **not found** (404);
8. resource campus (D-B1) — a campus permission on a resource of a campus
   outside the member's campuses is **not found** (404).

Denials never say which permission, role, tenant or campus was involved.
The active campus is a view filter and plays no part here (D-B1).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Final, Protocol

from app.core.authz.registry import Permission, PermissionScope
from app.core.context import RequestContext
from app.core.errors import (
    AuthenticationRequiredError,
    NotFoundError,
    PermissionDeniedError,
    StepUpRequiredError,
)

STEP_UP_WINDOW: Final = timedelta(minutes=10)


class AuthzResource(Protocol):
    """What resource authorization needs to know about a loaded resource."""

    @property
    def tenant_id(self) -> uuid.UUID: ...

    @property
    def campus_id(self) -> uuid.UUID | None: ...


def require_fresh_mfa(context: RequestContext, *, now: datetime | None = None) -> None:
    """Raise ``StepUpRequiredError`` unless MFA was verified within the step-up window."""
    verified = context.mfa_verified_at
    moment = now or datetime.now(UTC)
    if verified is None or not (moment - STEP_UP_WINDOW <= verified <= moment):
        raise StepUpRequiredError()


def authorize(
    context: RequestContext, permission: Permission, resource: AuthzResource | None = None
) -> None:
    """Allow, or raise ``AuthenticationRequiredError``, ``PermissionDeniedError``,
    ``StepUpRequiredError`` or ``NotFoundError``."""
    if context.principal_id is None:
        raise AuthenticationRequiredError()
    if permission.realm is not context.realm:
        raise PermissionDeniedError()
    if permission.scope is not None and context.tenant_id is None:
        raise PermissionDeniedError()
    if permission.code not in context.permissions:
        raise PermissionDeniedError()
    if permission.requires_step_up:
        require_fresh_mfa(context)
    if permission.scope is PermissionScope.TENANT and not context.all_campuses:
        raise PermissionDeniedError()
    if resource is None:
        return
    if resource.tenant_id != context.tenant_id:
        raise NotFoundError()
    if (
        permission.scope is PermissionScope.CAMPUS
        and resource.campus_id is not None
        and not context.all_campuses
        and resource.campus_id not in context.campus_ids
    ):
        raise NotFoundError()
