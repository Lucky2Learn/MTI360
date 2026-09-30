"""API realms (ADR-0006): one package-level entry point that mounts every realm.

Modules contribute routes by including their routers into the realm routers
defined here (``app/api/<realm>.py``); nothing is mounted on the application
directly, so every route passes a realm guard (see ``realms.py``).
"""

from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.api import platform, public, student, tenant, webhooks
from app.api.realms import REALM_PREFIXES, realm_for_path
from app.core.context import Realm

# The tenant realm owns the remaining /api/v1/* paths, so it is mounted last.
_REALMS = (
    (Realm.PLATFORM, platform.ROUTERS),
    (Realm.STUDENT, student.ROUTERS),
    (Realm.PUBLIC, public.ROUTERS),
    (Realm.WEBHOOK, webhooks.ROUTERS),
    (Realm.TENANT, tenant.ROUTERS),
)


def mount_api(app: FastAPI) -> None:
    for realm, routers in _REALMS:
        for router in routers:
            app.include_router(router, prefix=REALM_PREFIXES[realm])


def operation_id(route: APIRoute) -> str:
    """OpenAPI operationId ``<realm>_<tag>_<function>``, e.g. ``tenant_campuses_list_campuses``.

    The realm prefix keeps IDs unique when two realms expose the same operation
    name (for example tenant and platform ``get_session``), so generated API
    clients stay unambiguous. Routes outside the realms (``/health``) have none.
    """
    tag = str(route.tags[0]).replace(" ", "_").lower() if route.tags else "api"
    realm = realm_for_path(route.path)
    prefix = f"{realm.value}_" if realm else ""
    return f"{prefix}{tag}_{route.name}"
