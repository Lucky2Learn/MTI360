"""Route authorization coverage (T01-05; ADR-0011 §4).

Every API route either requires exactly one permission
(``dependencies=[require_permission(...)]``) or appears in
:data:`REVIEWED_EXEMPTIONS` with a kind and a reason. The exemption list is
code-reviewed: adding a route to it is a deliberate security decision.

* ``public_route`` — reachable without a session (``Access.ANONYMOUS``):
  sign-in, password reset, invitations, the public website.
* ``authenticated_only`` — any valid session, no permission: the caller acts
  only on their own data, such as their session (``Access.SESSION`` or
  ``Access.AUTHENTICATED``).
* ``mfa_pending`` (T01-06) — a session that passed the password step only;
  the route completes the caller's own MFA step (``Access.MFA_PENDING``).

:func:`coverage_violations` runs on the real application in
``tests/security/test_route_coverage.py``; it also rejects stale exemptions,
exemptions that do not match the route's access level, and permissions of
another realm than the route's.
"""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from fastapi import FastAPI
from fastapi.routing import iter_route_contexts

from app.api.realms import API_PREFIX, Access, route_realm
from app.core.authz import route_permissions


class Exemption(StrEnum):
    PUBLIC_ROUTE = "public_route"
    AUTHENTICATED_ONLY = "authenticated_only"
    MFA_PENDING = "mfa_pending"


@dataclass(frozen=True, slots=True)
class ReviewedExemption:
    kind: Exemption
    reason: str


_PUBLIC = Exemption.PUBLIC_ROUTE
_OWN_SESSION = Exemption.AUTHENTICATED_ONLY
_MFA_PENDING = Exemption.MFA_PENDING
_PLATFORM = f"{API_PREFIX}/platform"

REVIEWED_EXEMPTIONS: Final = MappingProxyType(
    {
        ("POST", f"{API_PREFIX}/auth/login"): ReviewedExemption(
            _PUBLIC, "Sign-in: establishes the session (T01-04)."
        ),
        ("POST", f"{API_PREFIX}/auth/logout"): ReviewedExemption(
            _PUBLIC, "Sign-out of the presented session; idempotent (T01-04)."
        ),
        ("POST", f"{API_PREFIX}/auth/password-reset"): ReviewedExemption(
            _PUBLIC, "Password reset request; no account enumeration (T01-04)."
        ),
        ("POST", f"{API_PREFIX}/auth/password-reset/confirm"): ReviewedExemption(
            _PUBLIC, "Password reset with a single-use token (T01-04)."
        ),
        ("POST", f"{API_PREFIX}/auth/invitations/preview"): ReviewedExemption(
            _PUBLIC, "Invitation preview with a single-use token (T01-04)."
        ),
        ("POST", f"{API_PREFIX}/auth/invitations/accept"): ReviewedExemption(
            _PUBLIC, "Invitation acceptance with a single-use token (T01-04)."
        ),
        ("GET", f"{API_PREFIX}/session"): ReviewedExemption(
            _OWN_SESSION, "The caller's own session, permissions included (T01-04/05)."
        ),
        ("PUT", f"{API_PREFIX}/session/tenant"): ReviewedExemption(
            _OWN_SESSION, "Selects one of the caller's own memberships (T01-04)."
        ),
        ("PUT", f"{API_PREFIX}/session/campus"): ReviewedExemption(
            _OWN_SESSION, "Selects one of the caller's permitted campuses (T01-04)."
        ),
        # --- Optional tenant MFA (T01-06) ------------------------------------------------
        ("POST", f"{API_PREFIX}/auth/mfa/verify"): ReviewedExemption(
            _MFA_PENDING, "Completes the caller's own sign-in with a TOTP code."
        ),
        ("POST", f"{API_PREFIX}/auth/mfa/recovery"): ReviewedExemption(
            _MFA_PENDING, "Completes the caller's own sign-in with a recovery code."
        ),
        ("POST", f"{API_PREFIX}/session/mfa/enrolment"): ReviewedExemption(
            _OWN_SESSION, "Starts the caller's own optional MFA enrolment."
        ),
        ("POST", f"{API_PREFIX}/session/mfa/enrolment/confirm"): ReviewedExemption(
            _OWN_SESSION, "Confirms the caller's own MFA enrolment."
        ),
        ("POST", f"{API_PREFIX}/session/mfa/remove"): ReviewedExemption(
            _OWN_SESSION, "Turns off the caller's own MFA with a current code."
        ),
        # --- Platform realm (T01-06) ------------------------------------------------------
        ("POST", f"{_PLATFORM}/auth/login"): ReviewedExemption(
            _PUBLIC, "Platform sign-in: password step, opens an MFA-pending session."
        ),
        ("POST", f"{_PLATFORM}/auth/logout"): ReviewedExemption(
            _PUBLIC, "Platform sign-out of the presented session; idempotent."
        ),
        ("POST", f"{_PLATFORM}/auth/password-reset"): ReviewedExemption(
            _PUBLIC, "Platform password reset request; no account enumeration (D6-2)."
        ),
        ("POST", f"{_PLATFORM}/auth/password-reset/confirm"): ReviewedExemption(
            _PUBLIC, "Platform password reset with a single-use token (D6-2)."
        ),
        ("POST", f"{_PLATFORM}/auth/mfa/enrolment"): ReviewedExemption(
            _MFA_PENDING, "Starts TOTP enrolment for the caller's own pending session."
        ),
        ("POST", f"{_PLATFORM}/auth/mfa/enrolment/confirm"): ReviewedExemption(
            _MFA_PENDING, "Confirms the caller's own TOTP enrolment and completes sign-in."
        ),
        ("POST", f"{_PLATFORM}/auth/mfa/verify"): ReviewedExemption(
            _MFA_PENDING, "Completes the caller's own sign-in with a TOTP code."
        ),
        ("POST", f"{_PLATFORM}/auth/mfa/recovery"): ReviewedExemption(
            _MFA_PENDING, "Completes the caller's own sign-in with a recovery code."
        ),
        ("GET", f"{_PLATFORM}/session"): ReviewedExemption(
            _OWN_SESSION, "The caller's own platform session, permissions and MFA state."
        ),
        ("POST", f"{_PLATFORM}/session/step-up"): ReviewedExemption(
            _OWN_SESSION, "Re-verifies the caller's own MFA for step-up (D6-5)."
        ),
        ("POST", f"{_PLATFORM}/session/mfa/recovery-codes"): ReviewedExemption(
            _OWN_SESSION, "Regenerates the caller's own recovery codes; needs step-up."
        ),
    }
)

_ALLOWED_ACCESS: Final = {
    Exemption.PUBLIC_ROUTE: frozenset({Access.ANONYMOUS}),
    Exemption.AUTHENTICATED_ONLY: frozenset({Access.SESSION, Access.AUTHENTICATED}),
    Exemption.MFA_PENDING: frozenset({Access.MFA_PENDING}),
}


def coverage_violations(
    app: FastAPI,
    exemptions: MappingProxyType[tuple[str, str], ReviewedExemption] = REVIEWED_EXEMPTIONS,
) -> list[str]:
    """API routes without exactly one permission or one matching reviewed exemption."""
    problems: list[str] = []
    seen: set[tuple[str, str]] = set()
    for route in iter_route_contexts(app.routes):
        path = route.path or ""
        if not path.startswith(API_PREFIX):
            continue
        guard = route_realm(route)
        permissions = route_permissions(getattr(route, "dependant", None))
        for method in sorted(getattr(route, "methods", None) or ()):
            key = (method, path)
            seen.add(key)
            label = f"{method} {path}"
            exemption = exemptions.get(key)
            if guard is None:
                problems.append(f"{label}: no realm guard")
                continue
            realm, access = guard
            if len(permissions) > 1:
                problems.append(f"{label}: more than one require_permission")
            if permissions and exemption is not None:
                problems.append(f"{label}: both a permission and an exemption")
            if not permissions and exemption is None:
                problems.append(f"{label}: no require_permission and no reviewed exemption")
            if permissions and access is Access.ANONYMOUS:
                problems.append(f"{label}: a permission on an anonymous route")
            if any(p.realm is not realm for p in permissions):
                problems.append(f"{label}: permission of another realm")
            if exemption is not None and access not in _ALLOWED_ACCESS[exemption.kind]:
                problems.append(f"{label}: {exemption.kind.value} on a {access.value} route")
    problems.extend(
        f"{method} {path}: stale exemption" for method, path in sorted(set(exemptions) - seen)
    )
    return problems
