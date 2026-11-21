"""Public enquiry API against PostgreSQL and Redis (Phase 02-4, ADR-0024).

The institute comes only from a verified, active request host; everything else
is 404. An enquiry becomes a tenant-scoped website lead with consent evidence,
its activity, the ``lead.created`` audit event and an acknowledgement outbox
message, in one transaction. Also the cross-tenant suite of the public routes
(``tests/cross_tenant_registry.py``, ``PUBLIC_ROUTES``).
"""

import asyncio
import dataclasses
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from conftest import DatabaseUnderTest
from httpx import ASGITransport, AsyncClient
from identity_support import Harness, auth_harness, auth_settings
from public_enquiry_support import (
    ENQUIRIES,
    FORM,
    Sites,
    enquiry,
    form,
    isolate,
    leads_by_email,
    sites,
    submit,
)
from tenant_admin_support import sign_in

from app.core.ratelimit import Limit, RedisRateLimiter
from app.core.tenancy import system_context
from app.main import create_app
from app.modules.enquiries import service as enquiry_service
from app.modules.enquiries.domain import ACKNOWLEDGEMENT_KIND, CONSENT_VERSION, MAX_BODY_BYTES
from app.modules.enquiries.service import PublicEnquiries
from app.modules.tenants.domains import set_domain_status
from app.modules.tenants.sites import DomainStatus

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        await isolate(harness)
        yield harness  # the harness closes the enquiry limiter and signal


@pytest.fixture
async def s(h: Harness) -> Sites:
    return await sites(h)


def _codes(response: Any) -> dict[str | None, str]:
    return {d["field"]: d["code"] for d in response.json()["error"]["details"]}


async def _outbox(h: Harness, lead_id: uuid.UUID) -> list[Any]:
    return list(
        await h.owner(
            "SELECT tenant_id, kind, payload, status, idempotency_key FROM outbox_messages "
            "WHERE payload->>'lead_id' = :l",
            l=str(lead_id),
        )
    )


# --- Host resolution ------------------------------------------------------------------


async def test_the_form_belongs_to_the_verified_host_only(h: Harness, s: Sites) -> None:
    response = await form(h, s.host_a)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["institute_name"].startswith("Western Maritime Academy")
    # Only this institute's open courses: no draft, nothing of the other institute.
    assert [c["id"] for c in data["courses"]] == [str(s.course_a)]
    assert data["consent"]["version"] == CONSENT_VERSION
    assert data["consent"]["retention_months"] == 12
    assert "12 months" in data["consent"]["text"]
    assert "12 months" in data["privacy_notice"]
    other = (await form(h, s.host_b)).json()["data"]
    assert [c["id"] for c in other["courses"]] == [str(s.course_b)]


@pytest.mark.parametrize(
    "host",
    [
        "unknown-institute.mti360.in",
        "127.0.0.1",
        "[::1]",
        "mti360.in",
        "evil.example",
        "",
    ],
)
async def test_unknown_and_malformed_hosts_are_not_found(h: Harness, s: Sites, host: str) -> None:
    assert (await form(h, host)).status_code == 404
    # 404 before the body is looked at: an invalid body is still 404, not 422.
    response = await submit(h, host, {"tenant_id": str(h.world.tenant_a)})
    assert response.status_code == 404


async def test_host_matching_ignores_case_port_and_trailing_dot(h: Harness, s: Sites) -> None:
    for variant in (s.host_a.upper(), f"{s.host_a}:443", f"{s.host_a}."):
        assert (await form(h, variant)).status_code == 200, variant


async def test_inactive_addresses_and_closed_institutes_are_not_found(h: Harness, s: Sites) -> None:
    async with system_context(h.factory) as db:
        assert await set_domain_status(db, h.world.tenant_b, s.host_b, DomainStatus.INACTIVE)
    assert (await form(h, s.host_b)).status_code == 404
    assert (await submit(h, s.host_b, enquiry())).status_code == 404
    await h.owner("UPDATE tenants SET status = 'SUSPENDED' WHERE id = :t", t=h.world.tenant_a)
    try:
        assert (await form(h, s.host_a)).status_code == 404
        assert (await submit(h, s.host_a, enquiry())).status_code == 404
    finally:
        await h.owner("UPDATE tenants SET status = 'ACTIVE' WHERE id = :t", t=h.world.tenant_a)


async def test_a_forwarded_host_is_ignored_without_a_trusted_proxy(h: Harness, s: Sites) -> None:
    """Spoofing: TRUSTED_PROXY_HOPS=0, so X-Forwarded-Host never chooses the institute."""
    response = await form(h, "unknown.mti360.in", **{"x-forwarded-host": s.host_a})
    assert response.status_code == 404
    response = await form(h, s.host_b, **{"x-forwarded-host": s.host_a})
    assert response.status_code == 200
    assert response.json()["data"]["courses"][0]["id"] == str(s.course_b)


@pytest.fixture
async def proxied(
    h: Harness, migrated_database: DatabaseUnderTest, redis_url: str
) -> AsyncIterator[tuple[AsyncClient, PublicEnquiries]]:
    """The API behind one trusted proxy (the Next.js server): TRUSTED_PROXY_HOPS=1."""
    settings = auth_settings(migrated_database, redis_url)
    app = create_app(settings.model_copy(update={"trusted_proxy_hops": 1}))
    service: PublicEnquiries = app.state.enquiries
    await service.limiter.close()
    service.limiter = RedisRateLimiter.from_url(
        redis_url, namespace=f"test:{uuid.uuid7().hex}:public"
    )
    if service.signal is not None:
        await service.signal.close()
    service.signal = None
    service.config = dataclasses.replace(
        service.config, ip_limit=Limit(10_000, 600), tenant_limit=Limit(10_000, 600)
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with AsyncClient(transport=transport, base_url="https://api.internal") as client:
            yield client, service
    finally:
        await service.limiter.close()
        await app.state.engine.dispose()


async def test_behind_a_trusted_proxy_only_its_forwarded_host_counts(
    s: Sites, proxied: tuple[AsyncClient, PublicEnquiries]
) -> None:
    client, _ = proxied
    # The API's own Host (internal) is not an institute; the proxy's header is.
    response = await client.get(FORM, headers={"x-forwarded-host": s.host_a})
    assert response.status_code == 200
    assert response.json()["data"]["courses"][0]["id"] == str(s.course_a)
    # Without the header nothing resolves, whatever Host says.
    assert (await client.get(FORM, headers={"host": s.host_a})).status_code == 404
    # A chain: only the right-most entry (written by the trusted proxy) counts.
    chained = await client.get(FORM, headers={"x-forwarded-host": f"{s.host_a}, {s.host_b}"})
    assert chained.json()["data"]["courses"][0]["id"] == str(s.course_b)


# --- Creating the lead ------------------------------------------------------------------


async def test_an_enquiry_becomes_a_website_lead_of_the_host_institute_only(
    h: Harness, s: Sites
) -> None:
    body = enquiry(mobile="+91 90000 10401", course_id=str(s.course_a), message="Batch dates?")
    response = await submit(h, s.host_a, body)
    assert response.status_code == 202, response.text
    assert response.json() == {"data": {"status": "received"}, "meta": {}}

    (lead,) = await leads_by_email(h, body["email"])
    assert lead.tenant_id == h.world.tenant_a
    assert (lead.source, lead.status) == ("WEBSITE", "NEW")
    assert lead.campus_id is None
    assert lead.owner_membership_id is None
    assert lead.created_by_membership_id is None
    assert lead.consent_version == CONSENT_VERSION
    assert lead.consented_at is not None
    assert lead.interested_course_id == s.course_a

    activities = await h.owner(
        "SELECT kind, actor_membership_id, body, details FROM lead_activities "
        "WHERE lead_id = :l ORDER BY created_at, kind",
        l=lead.id,
    )
    kinds = {row.kind: row for row in activities}
    assert set(kinds) == {"CREATED", "NOTE"}
    assert kinds["NOTE"].body == "Batch dates?"
    assert kinds["CREATED"].details["channel"] == "public_enquiry"
    assert kinds["CREATED"].details["consent_version"] == CONSENT_VERSION
    assert kinds["CREATED"].details["retention_months"] == 12
    assert all(row.actor_membership_id is None for row in activities)

    (message,) = await _outbox(h, lead.id)
    assert (message.tenant_id, message.kind, message.status) == (
        h.world.tenant_a,
        ACKNOWLEDGEMENT_KIND,
        "PENDING",
    )
    assert message.payload == {"lead_id": str(lead.id)}  # identifiers only, no contact
    assert message.idempotency_key == f"{ACKNOWLEDGEMENT_KIND}:{lead.id}"

    audit = await h.audit(response)
    created = [row for row in audit if row.event_type == "lead.created"]
    assert len(created) == 1
    assert (created[0].tenant_id, created[0].realm) == (h.world.tenant_a, "public")
    assert created[0].metadata["channel"] == "public_enquiry"
    assert body["email"] not in str(created[0].metadata)

    # Nothing in the other institute.
    other = await h.owner(
        "SELECT count(*) FROM leads WHERE tenant_id = :t AND email = :e",
        t=h.world.tenant_b,
        e=body["email"],
    )
    assert other[0][0] == 0


async def test_staff_see_the_enquiry_and_the_other_institute_does_not(h: Harness, s: Sites) -> None:
    body = enquiry()
    assert (await submit(h, s.host_a, body)).status_code == 202
    (lead,) = await leads_by_email(h, body["email"])

    await sign_in(h, "alice", tenant_id=h.world.tenant_a)  # owner of A
    detail = await h.client.get(f"/api/v1/leads/{lead.id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["created_by"] is None
    assert detail.json()["data"]["source"] == "WEBSITE"
    activity = await h.client.get(f"/api/v1/leads/{lead.id}/activity")
    assert activity.status_code == 200

    await sign_in(h, "carol", tenant_id=h.world.tenant_b)  # owner of B
    assert (await h.client.get(f"/api/v1/leads/{lead.id}")).status_code == 404


async def test_a_tenant_id_in_the_body_is_refused(h: Harness, s: Sites) -> None:
    body = enquiry(tenant_id=str(h.world.tenant_b))
    response = await submit(h, s.host_a, body)
    assert response.status_code == 422
    assert await leads_by_email(h, body["email"]) == []


async def test_only_an_open_course_of_this_institute_is_accepted(h: Harness, s: Sites) -> None:
    for course_id in (s.course_b, s.draft_a, uuid.uuid7()):
        body = enquiry(course_id=str(course_id))
        response = await submit(h, s.host_a, body)
        assert response.status_code == 422, course_id
        assert _codes(response) == {"course_id": "course_not_available"}
        assert await leads_by_email(h, body["email"]) == []


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"consent_accepted": False}, {"consent_accepted": "consent_required"}),
        ({"consent_version": "enquiry-2020-01"}, {"consent_version": "consent_outdated"}),
        ({"email": None}, {"email": "contact_required"}),
        ({"email": "not-an-email"}, {"email": "invalid"}),
        ({"mobile": "call me"}, {"mobile": "invalid"}),
        ({"full_name": "   "}, {"full_name": "string_too_short"}),
        ({"tenant_id": "x"}, {"tenant_id": "extra_forbidden"}),
    ],
)
async def test_invalid_enquiries_are_refused_and_store_nothing(
    h: Harness, s: Sites, fields: dict[str, Any], expected: dict[str, str]
) -> None:
    body = enquiry(**fields)
    response = await submit(h, s.host_a, body)
    assert response.status_code == 422, response.text
    assert _codes(response) == expected
    if body.get("email"):
        assert await leads_by_email(h, body["email"]) == []


async def test_missing_consent_fields_are_refused(h: Harness, s: Sites) -> None:
    body = enquiry()
    del body["consent_accepted"]
    assert (await submit(h, s.host_a, body)).status_code == 422


async def test_a_mobile_only_enquiry_queues_no_email(h: Harness, s: Sites) -> None:
    # The test database keeps rows: find this lead by a unique name, not its mobile.
    name = f"Mobile Only {uuid.uuid7().hex[-10:]}"
    mobile = f"+91 9{uuid.uuid7().int % 1_000_000_000:09d}"
    response = await submit(h, s.host_a, enquiry(full_name=name, email=None, mobile=mobile))
    assert response.status_code == 202
    rows = await h.owner(
        "SELECT id FROM leads WHERE tenant_id = :t AND full_name = :n",
        t=h.world.tenant_a,
        n=name,
    )
    assert len(rows) == 1
    assert await _outbox(h, rows[0].id) == []


# --- Abuse protection --------------------------------------------------------------------


async def test_the_spam_trap_answers_like_success_and_stores_nothing(h: Harness, s: Sites) -> None:
    body = enquiry(website="https://cheap-seo.example")
    response = await submit(h, s.host_a, body)
    assert response.status_code == 202
    assert response.json() == {"data": {"status": "received"}, "meta": {}}
    assert await leads_by_email(h, body["email"]) == []
    events = [row.event_type for row in await h.audit(response)]
    assert events == ["enquiry.discarded"]


async def test_the_client_ip_is_rate_limited(h: Harness, s: Sites) -> None:
    await isolate(h, ip_limit=Limit(2, 600))
    for _ in range(2):
        assert (await submit(h, s.host_a, enquiry())).status_code == 202
    limited = await submit(h, s.host_a, enquiry())
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0
    # The limit is per address, not per institute: the same client is limited everywhere.
    assert (await submit(h, s.host_b, enquiry())).status_code == 429


async def test_each_institute_is_rate_limited(
    s: Sites, proxied: tuple[AsyncClient, PublicEnquiries]
) -> None:
    client, service = proxied
    service.config = dataclasses.replace(service.config, tenant_limit=Limit(2, 600))

    async def from_ip(number: int, host: str) -> int:
        response = await client.post(
            ENQUIRIES,
            json=enquiry(),
            headers={"x-forwarded-host": host, "x-forwarded-for": f"203.0.113.{number}"},
        )
        return response.status_code

    assert [await from_ip(n, s.host_a) for n in (1, 2, 3)] == [202, 202, 429]
    assert await from_ip(4, s.host_b) == 202  # another institute has its own budget


async def test_without_the_rate_limit_store_enquiries_are_refused(h: Harness, s: Sites) -> None:
    service: PublicEnquiries = h.app.state.enquiries
    await service.limiter.close()
    service.limiter = RedisRateLimiter.from_url("redis://127.0.0.1:1/0", namespace="down")
    body = enquiry()
    assert (await submit(h, s.host_a, body)).status_code == 503
    assert await leads_by_email(h, body["email"]) == []


async def test_repeats_within_the_window_are_acknowledged_but_not_stored(
    h: Harness, s: Sites
) -> None:
    body = enquiry(course_id=str(s.course_a))
    first = await submit(h, s.host_a, body)
    again = await submit(h, s.host_a, body | {"full_name": "Ananya R. Iyer"})
    assert (first.status_code, again.status_code) == (202, 202)
    assert again.json() == first.json()
    assert len(await leads_by_email(h, body["email"])) == 1
    # Another course is a new enquiry.
    assert (await submit(h, s.host_a, body | {"course_id": None})).status_code == 202
    assert len(await leads_by_email(h, body["email"])) == 2


async def test_concurrent_repeats_store_one_lead(h: Harness, s: Sites) -> None:
    body = enquiry(course_id=str(s.course_a))
    responses = await asyncio.gather(*(submit(h, s.host_a, body) for _ in range(5)))
    assert [r.status_code for r in responses] == [202] * 5
    assert len(await leads_by_email(h, body["email"])) == 1


async def test_a_post_from_another_site_is_refused(h: Harness, s: Sites) -> None:
    body = enquiry()
    response = await submit(h, s.host_a, body, origin="https://evil.example")
    assert response.status_code == 403
    response = await submit(h, s.host_a, body, origin=f"https://{s.host_b}")
    assert response.status_code == 403
    assert await leads_by_email(h, body["email"]) == []


async def test_a_post_without_origin_is_accepted(h: Harness, s: Sites) -> None:
    origin = h.client.headers.pop("origin")
    try:
        body = enquiry()
        response = await h.client.post(ENQUIRIES, json=body, headers={"host": s.host_a})
        assert response.status_code == 202
    finally:
        h.client.headers["origin"] = origin


async def test_an_oversized_body_is_refused_unread(h: Harness, s: Sites) -> None:
    padding = "x" * (MAX_BODY_BYTES + 1)
    response = await h.client.post(
        ENQUIRIES,
        content=b'{"full_name": "' + padding.encode() + b'"}',
        headers={
            "host": s.host_a,
            "origin": f"https://{s.host_a}",
            "content-type": "application/json",
        },
    )
    assert response.status_code == 413


# --- Atomicity ---------------------------------------------------------------------------


async def test_the_lead_and_its_acknowledgement_commit_together(
    h: Harness, s: Sites, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing(*_: Any, **__: Any) -> bool:
        raise RuntimeError("outbox unavailable")

    monkeypatch.setattr(enquiry_service, "enqueue", failing)
    body = enquiry()
    response = await submit(h, s.host_a, body)
    assert response.status_code == 500
    assert await leads_by_email(h, body["email"]) == []
