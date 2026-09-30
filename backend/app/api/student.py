"""Student Portal API (``/api/v1/student/*``): students only.

Students are a separate realm, not a staff role (T01-00 decision D7). Routes
arrive with the student records (Phase 04/13).
"""

from fastapi import APIRouter

from app.api.realms import Access, realm_router
from app.core.context import Realm

router = realm_router(Realm.STUDENT, access=Access.AUTHENTICATED)

ROUTERS: tuple[APIRouter, ...] = (router,)
