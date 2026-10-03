"""Shared T01-08 test helpers: signing in as a tenant member and calling admin routes."""

import uuid
from typing import Any

from identity_support import Harness, add_membership, add_user, assign_role

from app.core.tenancy import system_context

MEMBERS = "/api/v1/members"


async def sign_in(
    h: Harness,
    user: str,
    tenant_id: uuid.UUID | None = None,
    campus_id: uuid.UUID | None = None,
) -> str:
    """Sign ``user`` in (choosing ``tenant_id`` / ``campus_id`` when asked); returns the CSRF."""
    h.client.cookies.clear()
    login = await h.login(user)
    assert login.status_code == 200, login.text
    data = login.json()["data"]
    csrf: str = data["csrf_token"]
    if data["status"] == "institute_selection_required":
        assert tenant_id is not None
        chosen = await h.client.put(
            "/api/v1/session/tenant",
            json={"tenant_id": str(tenant_id)},
            headers={"X-CSRF-Token": csrf},
        )
        assert chosen.status_code == 200, chosen.text
        data = chosen.json()["data"]
        csrf = data["csrf_token"]
    if data["status"] == "campus_selection_required":
        assert campus_id is not None
        chosen = await h.client.put(
            "/api/v1/session/campus",
            json={"campus_id": str(campus_id)},
            headers={"X-CSRF-Token": csrf},
        )
        assert chosen.status_code == 200, chosen.text
        csrf = chosen.json()["data"]["csrf_token"]
    return csrf


async def send(
    h: Harness, method: str, path: str, csrf: str, body: dict[str, Any] | None = None
) -> Any:
    return await h.client.request(method, path, json=body, headers={"X-CSRF-Token": csrf})


def data(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()["data"]


async def add_owner(h: Harness, name: str, tenant_id: uuid.UUID, owner_role: str) -> uuid.UUID:
    """Another ACTIVE all-campus member of ``tenant_id`` holding the owner role ``owner_role``."""
    async with system_context(h.factory) as db:
        await add_user(db, h.world, name)
    membership = await add_membership(
        h.factory, h.world, f"{name}_m", user=name, tenant_id=tenant_id
    )
    await assign_role(h.factory, h.world, f"{name}_m", owner_role)
    return membership


async def version(h: Harness, membership_id: uuid.UUID) -> int:
    rows = await h.owner("SELECT version FROM tenant_memberships WHERE id = :m", m=membership_id)
    return int(rows[0][0])
