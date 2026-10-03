"""Tenant audit read over HTTP (T01-08, D8-2).

``GET /api/v1/audit-events`` returns only events written in the tenant realm
for the active institute: platform-written events carrying the tenant's ID
(T01-07 provisioning) and other institutes' events are never shown.
"""

import json
import uuid
from collections.abc import AsyncIterator

import pytest
from conftest import DatabaseUnderTest
from identity_support import Harness, auth_harness
from tenant_admin_support import MEMBERS, send, sign_in, version

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

AUDIT = "/api/v1/audit-events"


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        yield harness


async def _platform_event(h: Harness, tenant_id: uuid.UUID) -> uuid.UUID:
    """A platform-written event carrying the tenant's ID, as T01-07 provisioning writes."""
    event_id = uuid.uuid7()
    await h.owner(
        "INSERT INTO audit_events (id, request_id, realm, tenant_id, principal_id, category, "
        "event_type, target_type, target_id, metadata) VALUES (:id, :r, 'platform', :t, :p, "
        "'admin', 'platform.tenant.created', 'tenant', :t, CAST(:m AS jsonb))",
        id=event_id,
        r=uuid.uuid7(),
        t=tenant_id,
        p=uuid.uuid7(),
        m=json.dumps({"campus_code": "MUM"}),
    )
    return event_id


async def test_tenant_admins_see_their_tenant_realm_events_only(h: Harness) -> None:
    platform_event = await _platform_event(h, h.world.tenant_a)
    csrf = await sign_in(h, "alice")
    dave = h.world.memberships["dave_a"]
    await send(h, "POST", f"{MEMBERS}/{dave}/suspend", csrf, {"version": await version(h, dave)})
    page = (await h.client.get(AUDIT, params={"limit": 100})).json()
    items = page["data"]
    assert items, page
    assert all(item["realm"] == "tenant" for item in items)
    assert all(item["tenant_id"] == str(h.world.tenant_a) for item in items)
    assert str(platform_event) not in json.dumps(page)
    suspended = [i for i in items if i["event_type"] == "member.suspended"]
    assert [i["target_id"] for i in suspended] == [str(dave)]
    assert suspended[0]["principal_id"] == str(h.world.users["alice"])
    # Filters: the event type and the target.
    filtered = (await h.client.get(AUDIT, params={"target_id": str(dave)})).json()["data"]
    assert [i["event_type"] for i in filtered] == ["member.suspended"]
    # A tenant_id query parameter is not a filter and never widens the scope.
    widened = await h.client.get(AUDIT, params={"tenant_id": str(h.world.tenant_b)})
    assert all(i["tenant_id"] == str(h.world.tenant_a) for i in widened.json()["data"])


async def test_another_institute_never_sees_these_events(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    dave = h.world.memberships["dave_a"]
    await send(h, "POST", f"{MEMBERS}/{dave}/suspend", csrf, {"version": await version(h, dave)})
    await sign_in(h, "carol")
    items = (await h.client.get(AUDIT, params={"limit": 100})).json()["data"]
    assert all(item["tenant_id"] == str(h.world.tenant_b) for item in items)
    assert str(dave) not in json.dumps(items)


async def test_audit_read_needs_the_tenant_wide_permission(h: Harness) -> None:
    await sign_in(h, "dave", campus_id=h.world.campus_a1)  # no audit.read
    assert (await h.client.get(AUDIT)).status_code == 403
    await sign_in(h, "bob", h.world.tenant_a)  # Administrator, campus-restricted (D-B1)
    assert (await h.client.get(AUDIT)).status_code == 403
    await sign_in(h, "bob", h.world.tenant_b)  # Administrator of B, all campuses
    assert (await h.client.get(AUDIT)).status_code == 200
