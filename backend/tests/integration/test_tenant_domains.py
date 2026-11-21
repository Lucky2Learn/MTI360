"""Institute site addresses and their Row-Level Security (Phase 02-4, ADR-0024)."""

import uuid
from collections.abc import AsyncIterator

import pytest
from conftest import DatabaseUnderTest
from identity_support import Harness, auth_harness
from public_enquiry_support import SITE_DOMAIN, issue
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.context import Realm, RequestContext
from app.core.db.session import context_transaction
from app.core.tenancy import system_context
from app.modules.tenants.domains import (
    DOMAINS,
    DomainLimitError,
    DomainTakenError,
    issue_platform_subdomain,
    resolve_public_host,
    set_domain_status,
)
from app.modules.tenants.sites import DomainStatus, InvalidSlugError

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        yield harness


def _slug() -> str:
    return f"t{uuid.uuid7().hex[-12:]}"


def _context(realm: Realm, tenant_id: uuid.UUID | None = None) -> RequestContext:
    return RequestContext(realm=realm, request_id=uuid.uuid7(), tenant_id=tenant_id)


async def test_an_address_is_issued_verified_and_unique(h: Harness) -> None:
    slug = _slug()
    hostname = await issue(h, h.world.tenant_a, slug)
    assert hostname == f"{slug}.{SITE_DOMAIN}"
    row = (
        await h.owner(
            "SELECT tenant_id, kind, status, verified_at FROM tenant_domains WHERE hostname = :h",
            h=hostname,
        )
    )[0]
    assert (row.tenant_id, row.kind, row.status) == (
        h.world.tenant_a,
        "PLATFORM_SUBDOMAIN",
        "ACTIVE",
    )
    assert row.verified_at is not None
    # Nobody else can take it, active or not, and its owner cannot take it twice.
    with pytest.raises(DomainTakenError):
        await issue(h, h.world.tenant_b, slug)
    async with system_context(h.factory) as db:
        await set_domain_status(db, h.world.tenant_a, hostname, DomainStatus.INACTIVE)
    with pytest.raises(DomainTakenError):
        await issue(h, h.world.tenant_b, slug)
    with pytest.raises(DomainTakenError):
        await issue(h, h.world.tenant_b, slug.upper())


async def test_an_institute_has_one_active_platform_address(h: Harness) -> None:
    first = await issue(h, h.world.tenant_a, _slug())
    with pytest.raises(DomainLimitError):
        await issue(h, h.world.tenant_a, _slug())
    async with system_context(h.factory) as db:
        await set_domain_status(db, h.world.tenant_a, first, DomainStatus.INACTIVE)
    await issue(h, h.world.tenant_a, _slug())  # after deactivating the old one


@pytest.mark.parametrize(
    "slug", ["ab", "www", "-konkan", "konkan-", "kon--kan", "konkan.in", "k@n"]
)
async def test_invalid_and_reserved_slugs_are_refused(h: Harness, slug: str) -> None:
    async with system_context(h.factory) as db:
        with pytest.raises(InvalidSlugError):
            await issue_platform_subdomain(db, h.world.tenant_a, slug, site_domain=SITE_DOMAIN)


async def test_a_refused_issue_leaves_the_transaction_usable(h: Harness) -> None:
    slug = _slug()
    await issue(h, h.world.tenant_a, slug)
    async with system_context(h.factory) as db:
        with pytest.raises(DomainTakenError):
            await issue_platform_subdomain(db, h.world.tenant_b, slug, site_domain=SITE_DOMAIN)
        assert await db.scalar(text("SELECT 1")) == 1


async def test_the_public_realm_reads_only_active_verified_addresses(h: Harness) -> None:
    active = await issue(h, h.world.tenant_a, _slug())
    inactive = await issue(h, h.world.tenant_b, _slug())
    async with system_context(h.factory) as db:
        await set_domain_status(db, h.world.tenant_b, inactive, DomainStatus.INACTIVE)
    async with context_transaction(h.factory, _context(Realm.PUBLIC)) as db:
        visible = set(
            (
                await db.execute(
                    select(DOMAINS.c.hostname).where(DOMAINS.c.hostname.in_([active, inactive]))
                )
            ).scalars()
        )
        assert visible == {active}
        assert await resolve_public_host(db, active) == h.world.tenant_a
        assert await resolve_public_host(db, inactive) is None


async def test_a_tenant_reads_only_its_own_addresses(h: Harness) -> None:
    mine = await issue(h, h.world.tenant_a, _slug())
    theirs = await issue(h, h.world.tenant_b, _slug())
    context = _context(Realm.TENANT, h.world.tenant_a)
    async with context_transaction(h.factory, context) as db:
        visible = set(
            (
                await db.execute(
                    select(DOMAINS.c.hostname).where(DOMAINS.c.hostname.in_([mine, theirs]))
                )
            ).scalars()
        )
    assert visible == {mine}


@pytest.mark.parametrize("realm", [Realm.PUBLIC, Realm.TENANT])
async def test_only_platform_and_system_can_issue(h: Harness, realm: Realm) -> None:
    tenant = h.world.tenant_a if realm is Realm.TENANT else None
    with pytest.raises(DBAPIError, match="row-level security"):
        async with context_transaction(h.factory, _context(realm, tenant)) as db:
            await issue_platform_subdomain(db, h.world.tenant_a, _slug(), site_domain=SITE_DOMAIN)
