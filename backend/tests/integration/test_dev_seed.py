"""Development seed against PostgreSQL (T01-08, decision D16).

The seed creates working institutes (owners sign in with the one-time
passwords it returns), refuses to run twice, and stores no password in
clear. Emails are made unique per run because the test database keeps rows.
"""

import dataclasses
import uuid
from collections.abc import AsyncIterator

import pytest
from conftest import DatabaseUnderTest
from identity_support import FAST_HASHER, Harness, auth_harness

from app.modules.access.templates import system_role_templates
from app.seed import SeedError, SeedInstitute, load_seed, seed

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        yield harness


def _unique(institutes: tuple[SeedInstitute, ...]) -> tuple[SeedInstitute, ...]:
    suffix = uuid.uuid7().hex[-8:]

    def email(address: str) -> str:
        local, domain = address.split("@")
        return f"{local}.{suffix}@{domain}"

    return tuple(
        dataclasses.replace(
            institute,
            name=f"{institute.name} {suffix}",
            members=tuple(
                dataclasses.replace(member, email=email(member.email))
                for member in institute.members
            ),
        )
        for institute in institutes
    )


async def test_the_seed_creates_working_institutes_once(h: Harness) -> None:
    institutes = _unique(load_seed())
    accounts = await seed(h.factory, FAST_HASHER, institutes)
    emails = sorted({m.email for i in institutes for m in i.members})
    assert [a.email for a in accounts] == emails
    assert len({a.password for a in accounts}) == len(accounts)

    first = institutes[0]
    tenant = await h.owner(
        "SELECT id, status, owner_membership_id IS NOT NULL FROM tenants WHERE name = :n",
        n=first.name,
    )
    tenant_id, status, has_owner = tenant[0]
    assert (status, has_owner) == (first.status.value, True)
    counts = await h.owner(
        "SELECT (SELECT count(*) FROM campuses WHERE tenant_id = :t), "
        "(SELECT count(*) FROM roles WHERE tenant_id = :t AND is_system), "
        "(SELECT count(*) FROM tenant_memberships WHERE tenant_id = :t AND status = 'ACTIVE')",
        t=tenant_id,
    )
    templates = len(system_role_templates())  # four since Phase 02-1
    assert tuple(counts[0]) == (len(first.campuses), templates, len(first.members))
    stored = await h.owner(
        "SELECT c.password_hash FROM user_credentials c JOIN users u ON u.id = c.user_id "
        "WHERE u.email = ANY(:e)",
        e=emails,
    )
    for account in accounts:
        assert account.password not in str(stored)

    owner = next(m for m in first.members if m.role.value == "INSTITUTE_OWNER")
    password = next(a.password for a in accounts if a.email == owner.email)
    login = await h.client.post(
        "/api/v1/auth/login", json={"email": owner.email, "password": password}
    )
    assert login.status_code == 200, login.text
    assert login.json()["data"]["status"] == "ready"
    assert (await h.client.get("/api/v1/members")).status_code == 200

    with pytest.raises(SeedError, match="already been applied"):
        await seed(h.factory, FAST_HASHER, institutes)
