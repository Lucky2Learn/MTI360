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

from app.integrations.storage import InMemoryObjectStorage
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
            # Phase 02-2: applications reference members by their seed email too.
            applications=tuple(
                dataclasses.replace(
                    application,
                    created_by=email(application.created_by),
                    reviewed_by=email(application.reviewed_by) if application.reviewed_by else None,
                )
                for application in institute.applications
            ),
        )
        for institute in institutes
    )


async def test_the_seed_creates_working_institutes_once(h: Harness) -> None:
    institutes = _unique(load_seed())
    accounts = await seed(h.factory, FAST_HASHER, institutes, storage=InMemoryObjectStorage())
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
        await seed(h.factory, FAST_HASHER, institutes, storage=InMemoryObjectStorage())


async def test_the_seed_creates_the_admissions_demo(h: Harness) -> None:
    """Phase 02-1: courses and leads load through the real schema, and a seeded
    campus counsellor sees exactly the institute pool and their campus."""
    institutes = _unique(load_seed())
    accounts = {
        a.email: a.password
        for a in await seed(h.factory, FAST_HASHER, institutes, storage=InMemoryObjectStorage())
    }
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


async def test_the_seed_creates_the_applications_demo(h: Harness) -> None:
    """Phase 02-2: applications at every stage, documents in object storage, an admitted
    walk-in student, leads moved to APPLICATION/ADMITTED, all within each institute."""
    institutes = _unique(load_seed())
    storage = InMemoryObjectStorage()
    h.app.state.storage = storage  # the API reads what the seed stored
    accounts = {
        a.email: a.password for a in await seed(h.factory, FAST_HASHER, institutes, storage=storage)
    }
    konkan, coromandel = institutes[0], institutes[1]
    manager = next(m for m in konkan.members if m.role.value == "ADMISSIONS_MANAGER")

    async def sign_in(email: str) -> None:
        h.client.cookies.clear()
        login = await h.client.post(
            "/api/v1/auth/login", json={"email": email, "password": accounts[email]}
        )
        assert login.status_code == 200, login.text

    await sign_in(manager.email)
    listed = (await h.client.get("/api/v1/applications", params={"limit": 100})).json()["data"]
    assert {a["status"] for a in listed} == {a.status.value for a in konkan.applications}
    assert all(a["number"].startswith("APP-") for a in listed)
    queue = (await h.client.get("/api/v1/documents")).json()["data"]
    assert queue
    assert all(item["status"] == "UNDER_REVIEW" for item in queue)
    downloaded = await h.client.get(f"/api/v1/documents/{queue[0]['id']}/download")
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF-")
    assert all(f"/{key.split('/')[1]}/" in key for key in storage.objects)
    students = (await h.client.get("/api/v1/students")).json()["data"]
    assert [s["full_name"] for s in students] == ["Sandeep Patil"]
    timeline = (await h.client.get(f"/api/v1/students/{students[0]['id']}/activity")).json()
    assert {e["kind"] for e in timeline["data"]} >= {"ADMITTED", "SUBMITTED", "DOCUMENT_VERIFIED"}
    leads = (
        await h.client.get("/api/v1/leads", params={"status": ["APPLICATION"], "limit": 100})
    ).json()["data"]
    started = {a.lead for a in konkan.applications if a.lead}
    assert {lead["full_name"] for lead in leads} == {
        lead.full_name for lead in konkan.leads if lead.key in started
    }
    approved = next(a for a in listed if a["status"] == "APPROVED")
    detail = (await h.client.get(f"/api/v1/applications/{approved['id']}")).json()["data"]
    assert detail["documents"]["pending"] == 0  # ready for the admission demo

    # The other institute's student is invisible here, and its stored files are its own.
    coromandel_student = next(a for a in coromandel.applications if a.status.value == "ADMITTED")
    assert coromandel_student.full_name not in {s["full_name"] for s in students}
    tenants = {key.split("/")[1] for key in storage.objects}
    assert len(tenants) == 2
