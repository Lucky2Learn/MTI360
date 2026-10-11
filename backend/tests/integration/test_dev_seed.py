"""Development seed against PostgreSQL (T01-08, decision D16).

The seed creates working institutes (owners sign in with the one-time
passwords it returns), refuses to run twice, and stores no password in
clear. Emails are made unique per run because the test database keeps rows.
"""

import dataclasses
import uuid
from collections import Counter
from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
from conftest import DatabaseUnderTest
from identity_support import FAST_HASHER, Harness, auth_harness

from app import seed as seed_module
from app.integrations.storage import InMemoryObjectStorage
from app.modules.access.templates import system_role_templates
from app.modules.leads.domain import LeadStatus
from app.seed import SeedError, SeedInstitute, load_seed, seed
from app.seed_finance import SeedFinance, SeedInvoice, seed_finance

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
            # Phase 02-5: fee structures, fee invoices and payments name members by email.
            finance=_finance_emails(institute.finance, email),
        )
        for institute in institutes
    )


def _finance_emails(finance: SeedFinance, email: Callable[[str], str]) -> SeedFinance:
    def optional(address: str | None) -> str | None:
        return email(address) if address else None

    return SeedFinance(
        fee_structures=tuple(
            dataclasses.replace(s, created_by=email(s.created_by)) for s in finance.fee_structures
        ),
        invoices=tuple(
            dataclasses.replace(
                invoice,
                issued_by=email(invoice.issued_by),
                cancelled_by=optional(invoice.cancelled_by),
                payments=tuple(
                    dataclasses.replace(
                        payment,
                        recorded_by=email(payment.recorded_by),
                        confirmed_by=optional(payment.confirmed_by),
                        closed_by=optional(payment.closed_by),
                    )
                    for payment in invoice.payments
                ),
            )
            for invoice in finance.invoices
        ),
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
    templates = len(system_role_templates())  # six since Phase 02-5
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
    students = (await h.client.get("/api/v1/students", params={"limit": 100})).json()["data"]
    admitted = {a.full_name for a in konkan.applications if a.status.value == "ADMITTED"}
    assert {s["full_name"] for s in students} == admitted  # Sandeep Patil + six (Phase 02-5)
    sandeep = next(s for s in students if s["full_name"] == "Sandeep Patil")
    timeline = (await h.client.get(f"/api/v1/students/{sandeep['id']}/activity")).json()
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


# --- Phase 02-5: Finance-lite ------------------------------------------------------------------

_INVOICE_VIOLATIONS = """
SELECT i.number FROM invoices i
JOIN admissions a ON a.tenant_id = i.tenant_id AND a.id = i.admission_id
JOIN applications ap ON ap.tenant_id = a.tenant_id AND ap.id = a.application_id
JOIN fee_structures f ON f.tenant_id = i.tenant_id AND f.id = i.fee_structure_id
WHERE i.tenant_id = :t AND NOT (
  ap.status = 'ADMITTED' AND ap.course_id = i.course_id AND ap.campus_id = i.campus_id
  AND a.student_id = i.student_id AND f.course_id = i.course_id
  AND (f.status = 'ACTIVE' OR (f.status = 'ARCHIVED' AND i.status = 'CANCELLED'))
  AND i.structure_total_minor = f.total_minor
  AND i.total_minor = (SELECT sum(l.amount_minor) FROM invoice_lines l WHERE l.invoice_id = i.id)
  AND i.paid_minor = coalesce((SELECT sum(p.amount_minor) FROM payments p
                               WHERE p.invoice_id = i.id AND p.status = 'CONFIRMED'), 0)
  AND 0 <= i.paid_minor AND i.paid_minor <= i.total_minor
  AND i.adjusted = EXISTS (SELECT 1 FROM invoice_lines l WHERE l.invoice_id = i.id
                           AND l.structure_amount_minor IS DISTINCT FROM l.amount_minor)
  AND (i.status <> 'CANCELLED' OR NOT EXISTS (SELECT 1 FROM payments p WHERE p.invoice_id = i.id
                                              AND p.status IN ('PENDING', 'CONFIRMED')))
)
"""
_PAYMENT_VIOLATIONS = """
SELECT p.id FROM payments p
JOIN invoices i ON i.tenant_id = p.tenant_id AND i.id = p.invoice_id
JOIN students s ON s.tenant_id = i.tenant_id AND s.id = i.student_id
LEFT JOIN receipts r ON r.tenant_id = p.tenant_id AND r.payment_id = p.id
WHERE p.tenant_id = :t AND NOT (
  p.student_id = i.student_id AND p.campus_id = i.campus_id
  AND (r.id IS NOT NULL) = (p.status IN ('CONFIRMED', 'REVERSED'))
  AND (r.id IS NULL OR (r.invoice_number = i.number AND r.student_number = s.student_number
                        AND r.amount_minor = p.amount_minor AND r.method = p.method))
  AND (p.status <> 'REVERSED' OR p.closed_by_membership_id <> p.recorded_by_membership_id)
  AND p.received_on <= (now() AT TIME ZONE 'Asia/Kolkata')::date
)
"""
_PROJECTION = """
SELECT i.number, i.status, i.total_minor, i.paid_minor, i.structure_total_minor, f.name,
       i.due_date - (now() AT TIME ZONE 'Asia/Kolkata')::date, i.adjusted, i.version,
       (SELECT array_agg(l.fee_head || ':' || l.amount_minor || ':'
                         || coalesce(l.structure_amount_minor::text, '-') ORDER BY l.position)
        FROM invoice_lines l WHERE l.invoice_id = i.id),
       (SELECT array_agg(p.method || ':' || p.amount_minor || ':' || p.status || ':'
                         || p.version || ':' || coalesce(r.number, '-') ORDER BY p.id)
        FROM payments p LEFT JOIN receipts r ON r.payment_id = p.id WHERE p.invoice_id = i.id),
       (SELECT array_agg(fa.kind ORDER BY fa.created_at, fa.id)
        FROM finance_activities fa WHERE fa.invoice_id = i.id)
FROM invoices i JOIN fee_structures f ON f.id = i.fee_structure_id
WHERE i.tenant_id = :t ORDER BY i.number
"""
_COUNTS = (
    "SELECT (SELECT count(*) FROM invoices), (SELECT count(*) FROM payments), "
    "(SELECT count(*) FROM receipts), (SELECT count(*) FROM fee_structures)"
)
_EVER_CONFIRMED = frozenset({"CONFIRMED", "REVERSED"})


async def _tenant(h: Harness, name: str) -> uuid.UUID:
    rows = await h.owner("SELECT id FROM tenants WHERE name = :n", n=name)
    return uuid.UUID(str(rows[0][0]))


async def _projection(h: Harness, tenant_id: uuid.UUID) -> list[tuple[object, ...]]:
    return [tuple(row) for row in await h.owner(_PROJECTION, t=tenant_id)]


def _expected_kinds(invoice: SeedInvoice) -> list[str]:
    """The activity timeline the API would have written for this seeded history."""
    kinds = ["ISSUED"]
    for payment in invoice.payments:
        kinds.append("PAYMENT_RECORDED")
        clearance = payment.method.value in {"CHEQUE", "DEMAND_DRAFT"}
        if clearance and payment.status.value in _EVER_CONFIRMED:
            kinds.append("PAYMENT_CONFIRMED")
        if payment.status.value == "FAILED":
            kinds.append("PAYMENT_FAILED")
        if payment.status.value == "REVERSED":
            kinds.append("PAYMENT_REVERSED")
    if invoice.cancel_reason:
        kinds.append("CANCELLED")
    return kinds


async def test_the_seed_creates_a_consistent_finance_demo(h: Harness) -> None:
    """Every seeded fee invoice, payment and receipt agrees with its admission, student,
    course, campus and fee structure, with the balance invariant and the API's history."""
    institutes = _unique(load_seed())
    await seed(h.factory, FAST_HASHER, institutes, storage=InMemoryObjectStorage())
    for institute in institutes:
        tenant_id = await _tenant(h, institute.name)
        assert await h.owner(_INVOICE_VIOLATIONS, t=tenant_id) == []
        assert await h.owner(_PAYMENT_VIOLATIONS, t=tenant_id) == []
        finance = institute.finance
        projection = await _projection(h, tenant_id)
        # Seed order is issue order: numbers are gap-free from 00001 in the FY sequence.
        for row, invoice in zip(projection, finance.invoices, strict=True):
            status, total, paid, due, adjusted, kinds = (*row[1:4], row[6], row[7], row[-1])
            assert (status, total, paid, due, adjusted) == (
                invoice.status.value,
                invoice.total_minor,
                invoice.paid_minor,
                invoice.due_in_days,
                invoice.adjustment_reason is not None,
            ), invoice.key
            assert kinds == _expected_kinds(invoice), invoice.key
        counters = [int(str(row[0]).rsplit("-", 1)[1]) for row in projection]
        assert counters == list(range(1, len(projection) + 1))
        receipts = await h.owner(
            "SELECT number FROM receipts WHERE tenant_id = :t ORDER BY number", t=tenant_id
        )
        ever_confirmed = sum(
            1
            for invoice in finance.invoices
            for payment in invoice.payments
            if payment.status.value in _EVER_CONFIRMED
        )
        assert [int(r[0].rsplit("-", 1)[1]) for r in receipts] == list(range(1, ever_confirmed + 1))
        sequences = dict(
            await h.owner(
                "SELECT name, last_value FROM tenant_sequences WHERE tenant_id = :t "
                "AND name IN ('INVOICE', 'RECEIPT')",
                t=tenant_id,
            )
        )
        assert sequences.get("INVOICE", 0) == len(finance.invoices)
        assert sequences.get("RECEIPT", 0) == ever_confirmed
        structures = await h.owner(
            "SELECT status, count(*) FROM fee_structures WHERE tenant_id = :t GROUP BY status",
            t=tenant_id,
        )
        assert dict(structures) == dict(Counter(s.status.value for s in finance.fee_structures))
        ((metadata,),) = await h.owner(
            "SELECT metadata FROM audit_events WHERE event_type = 'system.seed.applied' "
            "AND target_id = :t",
            t=tenant_id,
        )
        assert metadata["invoice_count"] == len(finance.invoices)
        assert metadata["fee_structure_count"] == len(finance.fee_structures)


async def test_the_finance_demo_respects_campus_and_tenant_boundaries(h: Harness) -> None:
    institutes = _unique(load_seed())
    accounts = {
        a.email: a.password
        for a in await seed(h.factory, FAST_HASHER, institutes, storage=InMemoryObjectStorage())
    }
    konkan, coromandel = institutes

    async def sign_in(email: str) -> None:
        h.client.cookies.clear()
        login = await h.client.post(
            "/api/v1/auth/login", json={"email": email, "password": accounts[email]}
        )
        assert login.status_code == 200, login.text

    async def invoices() -> list[dict[str, Any]]:
        response = await h.client.get(
            "/api/v1/invoices",
            params={"status": ["ISSUED", "PARTIALLY_PAID", "PAID", "CANCELLED"], "limit": 100},
        )
        assert response.status_code == 200, response.text
        return response.json()["data"]  # type: ignore[no-any-return]

    campus_of = {a.key: a.campus for a in konkan.applications}
    manager = next(m for m in konkan.members if m.role.value == "FINANCE_MANAGER")
    await sign_in(manager.email)
    listed = await invoices()
    assert sorted(i["status"] for i in listed) == sorted(
        i.status.value for i in konkan.finance.invoices
    )
    live = [i for i in konkan.finance.invoices if i.status.value != "CANCELLED"]
    summary = (await h.client.get("/api/v1/finance/summary")).json()["data"]
    assert summary["invoice_count"] == len(live)
    assert summary["invoiced_minor"] == sum(i.total_minor for i in live)
    assert summary["collected_minor"] == sum(i.paid_minor for i in live)
    assert summary["overdue_count"] == sum(
        1 for i in live if i.due_in_days < 0 and i.status.value != "PAID"
    )
    assert summary["overdue_count"] >= 2
    pending = [p for i in live for p in i.payments if p.status.value == "PENDING"]
    assert (summary["pending_count"], summary["pending_minor"]) == (
        len(pending),
        sum(p.amount_minor for p in pending),
    )

    # A campus-restricted finance officer sees only their campus's fee invoices and payments.
    officer = next(m for m in konkan.members if m.role.value == "FINANCE_OFFICER")
    await sign_in(officer.email)
    mine = await invoices()
    expected = [i for i in konkan.finance.invoices if campus_of[i.application] in officer.campuses]
    assert 0 < len(mine) == len(expected) < len(listed)
    assert {i["campus"]["code"] for i in mine} == set(officer.campuses)
    payments = (await h.client.get("/api/v1/payments", params={"limit": 100})).json()["data"]
    assert len(payments) == sum(len(i.payments) for i in expected)

    # Each institute sees only its own finance data, numbered from its own sequences.
    owner = next(m for m in coromandel.members if m.role.value == "INSTITUTE_OWNER")
    await sign_in(owner.email)
    theirs = await invoices()
    assert len(theirs) == len(coromandel.finance.invoices) == 1
    assert not {i["id"] for i in theirs} & {i["id"] for i in listed}
    assert theirs[0]["number"].endswith("-00001")
    payments = (await h.client.get("/api/v1/payments")).json()["data"]
    assert [p["status"] for p in payments] == ["CONFIRMED"]
    assert payments[0]["receipt"]["number"].endswith("-00001")


async def test_the_finance_seed_is_deterministic_and_refuses_a_rerun(h: Harness) -> None:
    template = load_seed()
    first, second = _unique(template), _unique(template)
    await seed(h.factory, FAST_HASHER, first, storage=InMemoryObjectStorage())
    await seed(h.factory, FAST_HASHER, second, storage=InMemoryObjectStorage())
    for one, other in zip(first, second, strict=True):
        projection = await _projection(h, await _tenant(h, one.name))
        assert projection  # numbers, amounts, statuses, due offsets, lines, payments, timeline
        assert projection == await _projection(h, await _tenant(h, other.name))

    before = await h.owner(_COUNTS)
    with pytest.raises(SeedError, match="already been applied"):
        await seed(h.factory, FAST_HASHER, first, storage=InMemoryObjectStorage())
    assert await h.owner(_COUNTS) == before


async def test_a_failure_while_seeding_finance_leaves_no_finance_data_or_numbers(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each institute is seeded in one transaction: a failure after its finance rows are
    written rolls back every one of them and their numbers. Users and the tenant row are
    committed earlier (the existing D16 structure), so the rerun is refused, not resumed."""
    institutes = _unique(load_seed())
    konkan, coromandel = institutes
    real = seed_finance

    async def failing(db: Any, tenant_id: uuid.UUID, **kwargs: Any) -> None:
        await real(db, tenant_id, **kwargs)  # the rows and numbers are written ...
        if kwargs["finance"] is coromandel.finance:
            raise RuntimeError("injected failure after the finance rows were written")

    monkeypatch.setattr(seed_module, "seed_finance", failing)
    with pytest.raises(RuntimeError, match="injected"):
        await seed(h.factory, FAST_HASHER, institutes, storage=InMemoryObjectStorage())

    # The institute seeded before the failure is complete and consistent.
    konkan_id = await _tenant(h, konkan.name)
    assert len(await _projection(h, konkan_id)) == len(konkan.finance.invoices)
    assert await h.owner(_INVOICE_VIOLATIONS, t=konkan_id) == []
    # The failing institute has no finance rows, no numbers and no campuses: all rolled back.
    coromandel_id = await _tenant(h, coromandel.name)
    rows = await h.owner(
        "SELECT (SELECT count(*) FROM fee_structures WHERE tenant_id = :t), "
        "(SELECT count(*) FROM invoices WHERE tenant_id = :t), "
        "(SELECT count(*) FROM payments WHERE tenant_id = :t), "
        "(SELECT count(*) FROM receipts WHERE tenant_id = :t), "
        "(SELECT count(*) FROM finance_activities WHERE tenant_id = :t), "
        "(SELECT count(*) FROM tenant_sequences WHERE tenant_id = :t), "
        "(SELECT count(*) FROM campuses WHERE tenant_id = :t)",
        t=coromandel_id,
    )
    assert tuple(rows[0]) == (0, 0, 0, 0, 0, 0, 0)

    monkeypatch.undo()
    before = await h.owner(_COUNTS)
    with pytest.raises(SeedError, match="already been applied"):
        await seed(h.factory, FAST_HASHER, institutes, storage=InMemoryObjectStorage())
    assert await h.owner(_COUNTS) == before
