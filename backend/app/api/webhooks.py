"""Provider webhooks (``/api/v1/webhooks/*``).

Denied by default: a route is accepted only after its provider signature
verifier is attached, and the tenant is resolved from the verified channel
mapping (Phase 09).
"""

from fastapi import APIRouter

from app.api.realms import Access, realm_router
from app.core.context import Realm

router = realm_router(Realm.WEBHOOK, access=Access.AUTHENTICATED)

ROUTERS: tuple[APIRouter, ...] = (router,)
