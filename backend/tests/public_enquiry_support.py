"""Shared setup for the public enquiry tests (Phase 02-4, ADR-0024).

Builds on the identity harness (``tenant_a`` ACTIVE, ``tenant_b`` TRIAL): each
gets a platform-issued address, unique per test run, and courses. Every test
gets its own rate-limit namespace and outbox wake key, so runs never share
counters, and limits are generous unless a test lowers them.
"""

import dataclasses
import uuid
from dataclasses import dataclass
from typing import Any

from httpx import Response
from identity_support import Harness

from app.core.outbox import OutboxSignal
from app.core.ratelimit import Limit, RedisRateLimiter
from app.core.tenancy import system_context
from app.modules.courses.models import Course
from app.modules.enquiries.domain import CONSENT_VERSION
from app.modules.enquiries.service import PublicEnquiries
from app.modules.tenants.domains import issue_platform_subdomain

SITE_DOMAIN = "mti360.in"
FORM = "/api/v1/public/enquiry-form"
ENQUIRIES = "/api/v1/public/enquiries"
GENEROUS = Limit(10_000, 600)


@dataclass(frozen=True, slots=True)
class Sites:
    host_a: str
    host_b: str
    course_a: uuid.UUID
    draft_a: uuid.UUID
    course_b: uuid.UUID


async def issue(h: Harness, tenant_id: uuid.UUID, slug: str) -> str:
    async with system_context(h.factory) as db:
        return await issue_platform_subdomain(db, tenant_id, slug, site_domain=SITE_DOMAIN)


async def course(
    h: Harness, tenant_id: uuid.UUID, code: str, *, status: str = "ACTIVE"
) -> uuid.UUID:
    async with system_context(h.factory, tenant_id=tenant_id) as db:
        row = Course(
            tenant_id=tenant_id,
            code=code,
            name=f"{code} programme",
            category="PRE_SEA",
            status=status,
        )
        db.add(row)
        await db.flush()
        return row.id


async def sites(h: Harness) -> Sites:
    suffix = uuid.uuid7().hex[-10:]
    return Sites(
        host_a=await issue(h, h.world.tenant_a, f"a{suffix}"),
        host_b=await issue(h, h.world.tenant_b, f"b{suffix}"),
        course_a=await course(h, h.world.tenant_a, "GPR"),
        draft_a=await course(h, h.world.tenant_a, "AFF", status="DRAFT"),
        course_b=await course(h, h.world.tenant_b, "DNS"),
    )


async def isolate(h: Harness, **config: Any) -> PublicEnquiries:
    """Fresh rate-limit namespace and wake key for this test; config overrides."""
    service: PublicEnquiries = h.app.state.enquiries
    await service.limiter.close()
    if service.signal is not None:
        await service.signal.close()
    redis_url = h.app.state.settings.redis_url.get_secret_value()
    run = uuid.uuid7().hex
    service.limiter = RedisRateLimiter.from_url(redis_url, namespace=f"test:{run}:public")
    service.signal = OutboxSignal.from_url(redis_url, key=f"test:{run}:outbox:wake")
    defaults: dict[str, Any] = {"ip_limit": GENEROUS, "tenant_limit": GENEROUS}
    service.config = dataclasses.replace(service.config, **(defaults | config))
    return service


def enquiry(**fields: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "full_name": "Ananya Iyer",
        "email": f"ananya.{uuid.uuid7().hex[-8:]}@example.com",
        "consent_accepted": True,
        "consent_version": CONSENT_VERSION,
        **fields,
    }
    return body


async def submit(h: Harness, host: str, body: dict[str, Any], **headers: str) -> Response:
    sent = {"host": host, "origin": f"https://{host}", **headers}
    return await h.client.post(ENQUIRIES, json=body, headers=sent)


async def form(h: Harness, host: str, **headers: str) -> Response:
    return await h.client.get(FORM, headers={"host": host, **headers})


async def leads_by_email(h: Harness, email: str) -> list[Any]:
    rows = await h.owner(
        "SELECT id, tenant_id, source, status, campus_id, owner_membership_id, "
        "created_by_membership_id, consent_version, consented_at, interested_course_id "
        "FROM leads WHERE email = :e ORDER BY created_at",
        e=email,
    )
    return list(rows)
