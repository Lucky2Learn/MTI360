"""Tenant Public Website API (``/api/v1/public/*``): anonymous visitors.

The tenant is resolved from a verified request host, never from the request
(ADR-0003, ADR-0004, ADR-0024). Phase 02-4 adds the hosted enquiry page's API;
the rest of the public website follows in Phase 14.
"""

from fastapi import APIRouter

from app.api.realms import Access, realm_router
from app.core.context import Realm
from app.modules.enquiries.router import enquiry_routes

router = realm_router(Realm.PUBLIC, access=Access.ANONYMOUS)
router.include_router(enquiry_routes)

ROUTERS: tuple[APIRouter, ...] = (router,)
