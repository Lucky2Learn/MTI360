"""Platform Control Plane API (``/api/v1/platform/*``): platform administrators only.

Principal: ``platform_users`` (separate identity, ADR-0005). No tenant context
except through an audited support session (Phase 02).

* ``anonymous``: sign-in, sign-out and password reset (T01-06);
* ``mfa_pending``: MFA enrolment, verification and recovery codes for a
  session that passed the password step only (T01-06);
* ``session``: the session read, step-up and recovery-code regeneration — an
  MFA-verified session (T01-06);
* ``router``: every other platform route — an MFA-verified session and
  ``require_permission`` (platform administration in T01-07).
"""

from fastapi import APIRouter

from app.api.realms import Access, realm_router
from app.core.context import Realm
from app.modules.platform_identity.router import anonymous_routes, mfa_routes, session_routes

anonymous = realm_router(Realm.PLATFORM, access=Access.ANONYMOUS)
anonymous.include_router(anonymous_routes)

mfa_pending = realm_router(Realm.PLATFORM, access=Access.MFA_PENDING)
mfa_pending.include_router(mfa_routes)

session = realm_router(Realm.PLATFORM, access=Access.SESSION)
session.include_router(session_routes)

router = realm_router(Realm.PLATFORM, access=Access.AUTHENTICATED)

ROUTERS: tuple[APIRouter, ...] = (anonymous, mfa_pending, session, router)
