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
from app.modules.leads.domain import LeadStatus
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
            # Phase 02-1: leads reference members by their seed email.
            leads=tuple(
                dataclasses.replace(
                    lead,
                    owner=email(lead.owner) if lead.owner else None,
                    created_by=email(lead.created_by),
                )
                for lead in institute.leads
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


async def test_the_seed_creates_the_admissions_demo(h: Harness) -> None:
    """Phase 02-1: courses and leads load through the real schema, and a seeded
    campus counsellor sees exactly the institute pool and their campus."""
    institutes = _unique(load_seed())
    accounts = {a.email: a.password for a in await seed(h.factory, FAST_HASHER, institutes)}
    konkan = institutes[0]
    counsellor = next(m for m in konkan.members if m.role.value == "COUNSELLOR")
    assert counsellor.campuses == ("MUM",)

    h.client.cookies.clear()
    login = await h.client.post(
        "/api/v1/auth/login",
        json={"email": counsellor.email, "password": accounts[counsellor.email]},
    )
    assert login.status_code == 200, login.text
    courses = (await h.client.get("/api/v1/courses", params={"limit": 100})).json()
    assert {c["code"] for c in courses["data"]} == {c.code for c in konkan.courses}
    leads = await h.client.get(
        "/api/v1/leads", params={"status": [s.value for s in LeadStatus], "limit": 100}
    )
    visible = {lead["full_name"] for lead in leads.json()["data"]}
    expected = {lead.full_name for lead in konkan.leads if lead.campus in (None, "MUM")}
    assert visible == expected
    assert not visible & {lead.full_name for lead in konkan.leads if lead.campus == "RTN"}
    with_notes = next(lead for lead in leads.json()["data"] if lead["full_name"] == "Imran Shaikh")
    activity = await h.client.get(f"/api/v1/leads/{with_notes['id']}/activity")
    assert activity.status_code == 200
    assert activity.json()["data"]
