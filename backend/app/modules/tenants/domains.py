"""Institute site addresses: issue, change status, resolve (Phase 02-4, ADR-0024).

* :func:`issue_platform_subdomain` gives an institute ``<slug>.<site domain>``
  (platform or system realm: the command line, the development seed; a
  platform screen comes later). The hostname is unique across the platform,
  so an address already held by any institute is refused (``DomainTakenError``),
  active or not. An institute holds at most one active platform address.
* :func:`set_domain_status` deactivates or reactivates an address; it stays
  with its institute either way.
* :func:`resolve_public_host` is the public realm's only tenant source: an
  exact hostname match on one ``ACTIVE``, verified row. Anything else (unknown,
  inactive, unverified, malformed) is ``None``, which callers answer with 404.
"""

import uuid
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import Table, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_id
from app.modules.tenants.models import TenantDomain
from app.modules.tenants.sites import (
    DomainKind,
    DomainStatus,
    clean_slug,
    normalize_host,
    site_hostname,
)

DOMAINS = cast(Table, TenantDomain.__table__)


class DomainTakenError(Exception):
    """The hostname belongs to an institute already (this one or another)."""


class DomainLimitError(Exception):
    """The institute already has an active platform address."""


async def issue_platform_subdomain(
    db: AsyncSession, tenant_id: uuid.UUID, slug: str, *, site_domain: str
) -> str:
    """Record ``<slug>.<site_domain>`` for ``tenant_id``, active and verified; return it.

    Runs in a savepoint, so a refusal leaves the caller's transaction usable.
    Raises :class:`~app.modules.tenants.sites.InvalidSlugError`,
    :class:`DomainTakenError` or :class:`DomainLimitError`.
    """
    hostname = site_hostname(clean_slug(slug), site_domain)
    taken = await db.scalar(select(DOMAINS.c.id).where(DOMAINS.c.hostname == hostname))
    if taken is not None:
        raise DomainTakenError()
    try:
        async with db.begin_nested():
            await db.execute(
                insert(DOMAINS).values(
                    id=new_id(),
                    tenant_id=tenant_id,
                    hostname=hostname,
                    kind=DomainKind.PLATFORM_SUBDOMAIN.value,
                    status=DomainStatus.ACTIVE.value,
                    verified_at=datetime.now(UTC),
                    version=1,
                )
            )
    except IntegrityError as error:
        # A concurrent issue of the same hostname, or a second active address.
        if "one_active_platform" in str(error.orig):
            raise DomainLimitError() from None
        raise DomainTakenError() from None
    return hostname


async def set_domain_status(
    db: AsyncSession, tenant_id: uuid.UUID, hostname: str, status: DomainStatus
) -> bool:
    """Activate or deactivate one of ``tenant_id``'s addresses; ``False`` if it has none."""
    changed = await db.execute(
        update(DOMAINS)
        .where(DOMAINS.c.tenant_id == tenant_id, DOMAINS.c.hostname == hostname)
        .values(status=status.value, version=DOMAINS.c.version + 1, updated_at=datetime.now(UTC))
        .returning(DOMAINS.c.id)
    )
    return changed.first() is not None


async def resolve_public_host(db: AsyncSession, raw_host: str | None) -> uuid.UUID | None:
    """The institute of a request host, or ``None`` (unknown, inactive, unverified, invalid)."""
    hostname = normalize_host(raw_host)
    if hostname is None:
        return None
    rows = (
        await db.execute(
            select(DOMAINS.c.tenant_id).where(
                DOMAINS.c.hostname == hostname,
                DOMAINS.c.status == DomainStatus.ACTIVE.value,
                DOMAINS.c.verified_at.is_not(None),
            )
        )
    ).all()
    # The hostname is unique; more than one row would be ambiguous: resolve nothing.
    return rows[0].tenant_id if len(rows) == 1 else None
