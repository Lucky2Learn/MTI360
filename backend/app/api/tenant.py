"""Tenant Application API (``/api/v1/*``): institute staff.

Tenant context comes only from the server-side session → validated membership
(ADR-0004); a ``tenant_id`` in a request is never used as authority.

* ``anonymous``: sign-in, sign-out, password reset and invitations (T01-04);
* ``mfa_pending``: the MFA step of sign-in for users with MFA (T01-06);
* ``session``: the session read, institute/campus selection and MFA opt-in —
  a valid session, institute optional (T01-04, ``Access.SESSION``);
* ``router``: every other tenant route — a session with an institute
  (tenant administration in T01-08, business modules from Phase 04).
"""

from fastapi import APIRouter

from app.api.realms import Access, realm_router
from app.core.context import Realm
from app.modules.access.router import role_routes
from app.modules.audit.router import tenant_audit_routes
from app.modules.identity.members_router import member_routes
from app.modules.identity.router import anonymous_routes, mfa_routes, session_routes
from app.modules.institute.router import institute_routes

anonymous = realm_router(Realm.TENANT, access=Access.ANONYMOUS)
anonymous.include_router(anonymous_routes)

mfa_pending = realm_router(Realm.TENANT, access=Access.MFA_PENDING)
mfa_pending.include_router(mfa_routes)

session = realm_router(Realm.TENANT, access=Access.SESSION)
session.include_router(session_routes)

router = realm_router(Realm.TENANT, access=Access.AUTHENTICATED)
router.include_router(institute_routes)
router.include_router(member_routes)
router.include_router(role_routes)
router.include_router(tenant_audit_routes)

ROUTERS: tuple[APIRouter, ...] = (anonymous, mfa_pending, session, router)
