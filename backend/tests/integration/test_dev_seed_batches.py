"""The batch demo of the development seed against PostgreSQL (Phase 02-6; ADR-0025).

A tagged copy per test (the test database keeps rows). The seeded batches and
allocations agree with their admissions, students, courses, campuses and the
seat counts; the history is the API's; the seeded data works through the API
(roles, campus scope, the full batch, a live allocation with an override); a
second run is refused and an earlier copy is untouched.
"""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from conftest import DatabaseUnderTest
from identity_support import FAST_HASHER, Harness, auth_harness

from app.integrations.storage import InMemoryObjectStorage
from app.seed import SeedError, SeedInstitute, load_seed, seed, tag_seed

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        yield harness


def _unique(institutes: tuple[SeedInstitute, ...]) -> tuple[SeedInstitute, ...]:
    return tag_seed(institutes, uuid.uuid7().hex[-12:])


async def _tenant(h: Harness, name: str) -> uuid.UUID:
    rows = await h.owner("SELECT id FROM tenants WHERE name = :n", n=name)
    return uuid.UUID(str(rows[0][0]))


# Rows that break the demo's invariants (each query must return nothing).
_SEAT_VIOLATIONS = (
    "SELECT b.code FROM batches b WHERE b.tenant_id = :t AND b.allocated_count <> "
    "(SELECT count(*) FROM batch_allocations a WHERE a.batch_id = b.id AND a.status = 'ACTIVE')"
)
_ADMISSION_VIOLATIONS = (
    "SELECT ad.admission_number FROM admissions ad WHERE ad.tenant_id = :t AND "
    "(ad.status = 'ENROLLED') <> EXISTS (SELECT 1 FROM batch_allocations a "
    "WHERE a.admission_id = ad.id AND a.status = 'ACTIVE')"
)


async def test_the_seed_creates_a_consistent_batch_demo(h: Harness) -> None:
    institutes = _unique(load_seed())
    await seed(h.factory, FAST_HASHER, institutes, storage=InMemoryObjectStorage())
    for institute in institutes:
        tenant_id = await _tenant(h, institute.name)
        assert await h.owner(_SEAT_VIOLATIONS, t=tenant_id) == []
        assert await h.owner(_ADMISSION_VIOLATIONS, t=tenant_id) == []
        rows = await h.owner(
            "SELECT code, status, capacity, allocated_count FROM batches WHERE tenant_id = :t",
            t=tenant_id,
        )
        stored = {row[0]: tuple(row[1:]) for row in rows}
        assert set(stored) == {b.code for b in institute.batches.batches}
        for batch in institute.batches.batches:
            assert stored[batch.code][:2] == (batch.status.value, batch.capacity)
        ((metadata,),) = await h.owner(
            "SELECT metadata FROM audit_events WHERE event_type = 'system.seed.applied' "
            "AND target_id = :t",
            t=tenant_id,
        )
        assert metadata["batch_count"] == len(institute.batches.batches)
        assert metadata["allocation_count"] == len(institute.batches.allocations)

    konkan = institutes[0]
    tenant_id = await _tenant(h, konkan.name)
    stored = {
        row[0]: (row[1], row[2], row[3])
        for row in await h.owner(
            "SELECT code, status, capacity, allocated_count FROM batches WHERE tenant_id = :t",
            t=tenant_id,
        )
    }
    assert stored["DNS-MUM-2026-A"] == ("OPEN", 2, 2)  # full
    assert stored["STCW-BST-MUM-2612"] == ("OPEN", 20, 1)  # seats free
    assert stored["GPR-RTN-2026-B"] == ("CLOSED", 30, 1)  # closed with a student
    assert stored["GPR-MUM-2027-A"][2] == 0  # transferred out
    assert stored["GPR-MUM-2027-B"][2] == 1  # transferred in
    overrides = await h.owner(
        "SELECT payment_basis, override_invoice_state, override_outstanding_minor, "
        "override_reason IS NOT NULL FROM batch_allocations WHERE tenant_id = :t "
        "ORDER BY allocated_at, id",
        t=tenant_id,
    )
    bases = sorted(row[0] for row in overrides)
    assert bases.count("PAID") == 1
    assert bases.count("TRANSFER") == 1
    assert bases.count("OVERRIDE") == 4  # KA6, KA11, KA8, KA9
    assert all(row[3] for row in overrides if row[0] == "OVERRIDE")
    transfer = await h.owner(
        "SELECT o.status, o.end_reason, n.status, n.payment_basis FROM batch_allocations n "
        "JOIN batch_allocations o ON o.id = n.transferred_from_id WHERE n.tenant_id = :t",
        t=tenant_id,
    )
    assert [tuple(row) for row in transfer] == [("ENDED", "TRANSFERRED", "ACTIVE", "TRANSFER")]
    kinds = await h.owner(
        "SELECT kind, count(*) FROM batch_activities WHERE tenant_id = :t GROUP BY kind",
        t=tenant_id,
    )
    assert dict(kinds) == {
        "CREATED": 5,
        "ALLOCATED": 5,
        "TRANSFERRED_OUT": 1,
        "TRANSFERRED_IN": 1,
        "STATUS_CHANGED": 1,
    }


async def test_the_batch_demo_works_through_the_api(h: Harness) -> None:
    institutes = _unique(load_seed())
    accounts = {
        a.email: a.password
        for a in await seed(h.factory, FAST_HASHER, institutes, storage=InMemoryObjectStorage())
    }
    konkan, coromandel = institutes

    async def sign_in(email: str) -> str:
        h.client.cookies.clear()
        login = await h.client.post(
            "/api/v1/auth/login", json={"email": email, "password": accounts[email]}
        )
        assert login.status_code == 200, login.text
        return str(login.json()["data"]["csrf_token"])

    def member(role: str, campuses: tuple[str, ...] = ()) -> str:
        return next(
            m.email for m in konkan.members if m.role.value == role and m.campuses == campuses
        )

    async def batches() -> dict[str, dict[str, Any]]:
        response = await h.client.get("/api/v1/batches", params={"limit": 100})
        assert response.status_code == 200, response.text
        return {b["code"]: b for b in response.json()["data"]}

    # The admissions manager sees every Konkan batch and nothing of Coromandel's.
    csrf = await sign_in(member("ADMISSIONS_MANAGER"))
    listed = await batches()
    assert set(listed) == {b.code for b in konkan.batches.batches}
    full = listed["DNS-MUM-2026-A"]
    assert (full["available_seats"], full["status"]) == (0, "OPEN")

    # The full batch refuses another student; an unallocated admission needs an override.
    tenant_id = await _tenant(h, konkan.name)
    waiting = {
        row[0]: str(row[1])
        for row in await h.owner(
            "SELECT ap.number, ad.id FROM admissions ad JOIN applications ap "
            "ON ap.id = ad.application_id WHERE ad.tenant_id = :t AND ad.status = 'ADMITTED'",
            t=tenant_id,
        )
    }
    assert len(waiting) == 2  # KA7 (DNS, Ratnagiri) and KA10 (STCW-BST, Ratnagiri)
    response = await h.client.post(
        f"/api/v1/batches/{full['id']}/allocations",
        json={"admission_id": next(iter(waiting.values())), "override_reason": "x"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 422
    # Student 360 shows the seeded batch history.
    allocations = (
        await h.client.get(f"/api/v1/batches/{listed['GPR-MUM-2027-B']['id']}/allocations")
    ).json()["data"]
    (moved,) = allocations
    assert moved["transferred_from_batch_code"] == "GPR-MUM-2027-A"
    timeline = (await h.client.get(f"/api/v1/students/{moved['student']['id']}/activity")).json()[
        "data"
    ]
    assert [e["kind"] for e in timeline if e["source"] == "batch"] == [
        "TRANSFERRED_IN",
        "ALLOCATED",
    ]

    # The Mumbai counsellor reads Mumbai batches only, and cannot allocate.
    csrf = await sign_in(member("COUNSELLOR", ("MUM",)))
    mumbai = await batches()
    assert mumbai
    assert all(b["campus"]["code"] == "MUM" for b in mumbai.values())
    assert (
        await h.client.get(f"/api/v1/batches/{listed['GPR-RTN-2026-B']['id']}")
    ).status_code == 404
    response = await h.client.post(
        f"/api/v1/batches/{listed['STCW-BST-MUM-2612']['id']}/allocations",
        json={"admission_id": next(iter(waiting.values()))},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403

    # Coromandel's director sees only Coromandel's batch.
    director = next(m.email for m in coromandel.members if m.role.value == "INSTITUTE_OWNER")
    await sign_in(director)
    assert set(await batches()) == {b.code for b in coromandel.batches.batches}
    assert (await h.client.get(f"/api/v1/batches/{full['id']}")).status_code == 404


async def test_a_rerun_is_refused_and_an_earlier_copy_is_untouched(h: Harness) -> None:
    template = load_seed()
    earlier = _unique(template)
    await seed(h.factory, FAST_HASHER, earlier, storage=InMemoryObjectStorage())
    earlier_konkan = await _tenant(h, earlier[0].name)
    snapshot = (
        "SELECT (SELECT array_agg(version || status || allocated_count ORDER BY id) FROM batches "
        "WHERE tenant_id = :t), (SELECT count(*) FROM batch_allocations WHERE tenant_id = :t), "
        "(SELECT count(*) FROM batch_activities WHERE tenant_id = :t)"
    )
    before = await h.owner(snapshot, t=earlier_konkan)
    with pytest.raises(SeedError, match="already been applied"):
        await seed(h.factory, FAST_HASHER, earlier, storage=InMemoryObjectStorage())
    later = _unique(template)
    await seed(h.factory, FAST_HASHER, later, storage=InMemoryObjectStorage())
    assert await h.owner(snapshot, t=earlier_konkan) == before
    assert await _tenant(h, later[0].name) != earlier_konkan
