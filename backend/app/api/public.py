"""Tenant Public Website API (``/api/v1/public/*``): anonymous visitors.

The tenant is resolved from a verified request host, never from the request
(ADR-0003, ADR-0004); routes arrive in Phase 14.
"""

from fastapi import APIRouter

from app.api.realms import Access, realm_router
from app.core.context import Realm

router = realm_router(Realm.PUBLIC, access=Access.ANONYMOUS)

ROUTERS: tuple[APIRouter, ...] = (router,)
