"""Platform Control Plane API (``/api/v1/platform/*``): platform administrators only.

Principal: ``platform_users`` (separate identity, ADR-0005). No tenant context
except through an audited support session (Phase 02). Sign-in routes (anonymous)
and platform administration routes are added in T01-06 and T01-07.
"""

from fastapi import APIRouter

from app.api.realms import Access, realm_router
from app.core.context import Realm

router = realm_router(Realm.PLATFORM, access=Access.AUTHENTICATED)

ROUTERS: tuple[APIRouter, ...] = (router,)
