"""FastAPI integration: ``require_permission`` (T01-05; ADR-0011 §4).

Every route of an ``Access.AUTHENTICATED`` router declares exactly one::

    @router.get("/campuses", dependencies=[require_permission(CAMPUS_READ)])

The dependency runs after the realm guard (which resolved the session and
the effective permissions) and calls :func:`authorize` without a resource;
handlers that load a resource call ``authorize(context, permission, resource)``
again with it. The route-coverage test finds the dependency through
:data:`PERMISSION_ATTRIBUTE`.

A refusal records the security event ``authz.denied`` (permission code and
realm only; never the caller's permissions or roles); a stale MFA
verification on a step-up permission records ``authz.step_up_required``.
"""

from collections.abc import Callable
from typing import Any, Final

from fastapi import Depends

from app.core.audit import AuditCategory, AuditEventType, record_security_event
from app.core.authz.engine import authorize
from app.core.authz.registry import Permission
from app.core.context import current_context
from app.core.errors import PermissionDeniedError, StepUpRequiredError

PERMISSION_ATTRIBUTE: Final = "__mti360_permission__"
AUTHZ_DENIED = AuditEventType("authz.denied", AuditCategory.SECURITY)
AUTHZ_STEP_UP_REQUIRED = AuditEventType("authz.step_up_required", AuditCategory.SECURITY)


def require_permission(permission: Permission) -> Any:
    """A route dependency that authorizes ``permission`` for the current request."""

    async def check_permission() -> None:
        metadata = {"permission": permission.code, "realm": permission.realm.value}
        try:
            authorize(current_context(), permission)
        except PermissionDeniedError:
            record_security_event(AUTHZ_DENIED, metadata=metadata)
            raise
        except StepUpRequiredError:
            record_security_event(AUTHZ_STEP_UP_REQUIRED, metadata=metadata)
            raise

    check_permission.__name__ = f"require_{permission.code.replace('.', '_')}"
    setattr(check_permission, PERMISSION_ATTRIBUTE, permission)
    return Depends(check_permission)


def route_permissions(dependant: Any) -> list[Permission]:
    """The permissions required by a route's dependency tree (route-coverage test)."""
    found: list[Permission] = []
    for sub in getattr(dependant, "dependencies", ()):
        call: Callable[..., Any] | None = getattr(sub, "call", None)
        marker = getattr(call, PERMISSION_ATTRIBUTE, None)
        if isinstance(marker, Permission):
            found.append(marker)
        found.extend(route_permissions(sub))
    return found
