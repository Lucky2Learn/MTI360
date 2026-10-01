"""Tenant Application API (``/api/v1/*``): institute staff.

Tenant context comes only from the server-side session → validated membership
(ADR-0004); a ``tenant_id`` in a request is never used. Sign-in (anonymous) and
session routes arrive in T01-04, tenant administration in T01-08, business
modules from Phase 04.
"""

from fastapi import APIRouter

from app.api.realms import Access, realm_router
from app.core.context import Realm

router = realm_router(Realm.TENANT, access=Access.AUTHENTICATED)

ROUTERS: tuple[APIRouter, ...] = (router,)
