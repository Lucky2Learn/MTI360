"""Platform audit read over HTTP (T01-07, D7-9).

``audit.read`` (SUPER_ADMIN and SECURITY_AUDIT_ADMIN); filters by category,
event type, tenant (in it or about it), actor and target; newest first with
offset pagination; metadata as redacted at write time.
"""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from conftest import DatabaseUnderTest
from identity_support import build_world
from platform_support import PlatformHarness, platform_harness

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

AUDIT = "/api/v1/platform/audit-events"


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[PlatformHarness]:
    async with platform_harness(migrated_database, redis_url) as harness:
        yield harness


def _items(response: Any) -> list[dict[str, Any]]:
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["data"]
    return items


async def test_tenant_events_are_found_in_and_about_the_tenant(h: PlatformHarness) -> None:
    world = await build_world(h.factory)
    csrf = await h.admin()
    version = (await h.client.get(f"/api/v1/platform/tenants/{world.tenant_b}")).json()["data"][
        "version"
    ]
    suspended = await h.post(
        f"/api/v1/platform/tenants/{world.tenant_b}/suspend",
        csrf,
        {"reason": "Licence expired", "version": version},
    )
    assert suspended.status_code == 200
    items = _items(await h.client.get(AUDIT, params={"tenant_id": str(world.tenant_b)}))
    assert [item["event_type"] for item in items] == ["platform.tenant.suspended"]
    event = items[0]
    assert event["principal_id"] == str(h.world.users["nora"])
    assert event["target_type"] == "tenant"
    assert event["metadata"]["reason"] == "Licence expired"
    assert event["category"] == "admin"
    assert event["realm"] == "platform"


async def test_filters_order_and_pagination(h: PlatformHarness) -> None:
    await h.admin()
    nora = str(h.world.users["nora"])
    mine = _items(
        await h.client.get(
            AUDIT, params={"principal_id": nora, "category": "security", "limit": 50}
        )
    )
    types = [item["event_type"] for item in mine]
    # Newest first: the sign-in completes after the enrolment started.
    assert types.index("platform.auth.login.success") < types.index(
        "platform.mfa.enrolment.started"
    )
    assert all(item["category"] == "security" for item in mine)
    page = await h.client.get(
        AUDIT, params={"principal_id": nora, "event_type": "platform.mfa.verified", "limit": 1}
    )
    assert page.json()["meta"]["page"]["limit"] == 1
    assert len(_items(page)) == 1
    assert _items(await h.client.get(AUDIT, params={"target_id": str(uuid.uuid7())})) == []
    assert (await h.client.get(AUDIT, params={"category": "everything"})).status_code == 422


async def test_audit_read_needs_the_permission(h: PlatformHarness) -> None:
    await h.admin("omar")  # SECURITY_AUDIT_ADMIN: allowed
    assert (await h.client.get(AUDIT)).status_code == 200
    h.client.cookies.clear()
    await h.admin("pia")  # BILLING_ADMIN: nothing in T01
    denied = await h.client.get(AUDIT)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PERMISSION_DENIED"
