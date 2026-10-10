"""Shared Phase 02-5 test helpers: the finance team, fee structures and fee invoices.

Extends the two-institute world (``identity_support.build_world``) and the
admissions team (``courses_leads_support.admissions_team``):

* ``fiona`` — Institute A, all campuses, Finance manager;
* ``faisal`` — Institute A, all campuses, Finance manager (a second reverser);
* ``farah`` — Institute A, campus A1 only, Finance officer;
* ``feroz`` — Institute A, campus A2 only, Finance officer;
* ``fatima`` — Institute A, campus A1 only, Finance manager (restricted:
  ``fee_structure.manage`` is tenant-wide, so not effective);
* ``carol`` (T01) — Institute B owner.

Amounts are integer paise. Fake people only.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from admissions_support import active_course, admit, approved
from courses_leads_support import add_member, fake_mobile
from identity_support import Harness
from tenant_admin_support import data, send, sign_in

from app.core.sequences.numbering import IST

FEE_STRUCTURES = "/api/v1/fee-structures"
INVOICES = "/api/v1/invoices"
PAYMENTS = "/api/v1/payments"
SUMMARY = "/api/v1/finance/summary"
ITEMS: list[dict[str, Any]] = [
    {"fee_head": "Tuition", "amount_minor": 25_000_000},
    {"fee_head": "Hostel", "amount_minor": 6_000_000},
    {"fee_head": "Uniform and kit", "amount_minor": 850_000},
]
ITEMS_TOTAL = 31_850_000


async def finance_team(h: Harness) -> None:
    w = h.world
    await add_member(h, "fiona", tenant_id=w.tenant_a, template="FINANCE_MANAGER")
    await add_member(h, "faisal", tenant_id=w.tenant_a, template="FINANCE_MANAGER")
    await add_member(
        h, "farah", tenant_id=w.tenant_a, template="FINANCE_OFFICER", campuses=(w.campus_a1,)
    )
    await add_member(
        h, "feroz", tenant_id=w.tenant_a, template="FINANCE_OFFICER", campuses=(w.campus_a2,)
    )
    await add_member(
        h, "fatima", tenant_id=w.tenant_a, template="FINANCE_MANAGER", campuses=(w.campus_a1,)
    )


async def finance_course(h: Harness, prefix: str, *, user: str = "maya") -> dict[str, Any]:
    """An ACTIVE course created by an admissions manager (finance roles only read courses).

    Signs ``user`` in: the caller signs its own user in again afterwards.
    """
    return await active_course(h, await sign_in(h, user), prefix)


async def new_structure(
    h: Harness,
    csrf: str,
    course_id: str,
    *,
    activate: bool = True,
    items: list[dict[str, Any]] | None = None,
    name: str = "Fees 2026-27",
) -> dict[str, Any]:
    body = {"course_id": course_id, "name": name, "items": items if items is not None else ITEMS}
    structure = data(await send(h, "POST", FEE_STRUCTURES, csrf, body), 201)
    if activate:
        structure = data(
            await send(
                h,
                "POST",
                f"{FEE_STRUCTURES}/{structure['id']}/status",
                csrf,
                {"status": "ACTIVE", "version": structure["version"]},
            )
        )
    return structure  # type: ignore[no-any-return]


def key() -> str:
    return str(uuid.uuid4())


def errors(response: Any) -> set[tuple[str | None, str]]:
    return {(d.get("field"), d["code"]) for d in response.json()["error"]["details"]}


def today_ist() -> date:
    return datetime.now(IST).date()


def due_in(days: int = 30) -> str:
    return (today_ist() + timedelta(days=days)).isoformat()


@dataclass
class Billable:
    """An admitted student whose course has an active fee structure."""

    course: dict[str, Any]
    structure: dict[str, Any]
    admission: dict[str, Any]
    """The application's admission link: ``id``, ``student_id``, numbers."""

    @property
    def admission_id(self) -> str:
        return str(self.admission["id"])

    @property
    def student_id(self) -> str:
        return str(self.admission["student_id"])


async def admitted(
    h: Harness,
    *,
    course: dict[str, Any],
    campus: uuid.UUID,
    user: str = "maya",
    full_name: str = "Kavya Menon",
) -> dict[str, Any]:
    """A new student admitted to ``course`` at ``campus`` (signs ``user`` in)."""
    csrf = await sign_in(h, user)
    application = await approved(
        h, csrf, course=course, campus=campus, full_name=full_name, mobile=fake_mobile()
    )
    return data(await admit(h, csrf, application))["admission"]  # type: ignore[no-any-return]


async def billable(
    h: Harness,
    campus: uuid.UUID,
    *,
    prefix: str = "DNS",
    admissions: str = "maya",
    finance: str = "fiona",
    items: list[dict[str, Any]] | None = None,
) -> Billable:
    """Course (by ``admissions``), active fee structure (by ``finance``), admitted student.

    Leaves ``admissions`` signed in: callers sign their own user in afterwards.
    """
    course = await active_course(h, await sign_in(h, admissions), prefix)
    structure = await new_structure(h, await sign_in(h, finance), course["id"], items=items)
    admission = await admitted(h, course=course, campus=campus, user=admissions)
    return Billable(course, structure, admission)


async def issue(
    h: Harness,
    csrf: str,
    admission_id: str,
    *,
    lines: list[dict[str, Any]] | None = None,
    due_date: str | None = None,
    reason: str | None = None,
    idempotency_key: str | None = None,
) -> Any:
    body: dict[str, Any] = {
        "admission_id": admission_id,
        "due_date": due_date or due_in(),
        "lines": lines if lines is not None else ITEMS,
        "idempotency_key": idempotency_key or key(),
    }
    if reason is not None:
        body["adjustment_reason"] = reason
    return await send(h, "POST", INVOICES, csrf, body)


async def pay(
    h: Harness,
    csrf: str,
    invoice_id: str,
    amount_minor: int,
    *,
    method: str = "CASH",
    reference: str | None = None,
    received_on: str | None = None,
    idempotency_key: str | None = None,
) -> Any:
    body: dict[str, Any] = {
        "amount_minor": amount_minor,
        "method": method,
        "received_on": received_on or today_ist().isoformat(),
        "idempotency_key": idempotency_key or key(),
    }
    if reference is not None:
        body["reference"] = reference
    return await send(h, "POST", f"{INVOICES}/{invoice_id}/payments", csrf, body)


async def paid_matches_confirmed(h: Harness, invoice_id: str) -> None:
    """The invariant: ``paid_minor`` is the sum of the invoice's ``CONFIRMED`` payments."""
    rows = await h.owner(
        "SELECT i.paid_minor, COALESCE((SELECT sum(p.amount_minor) FROM payments p "
        "WHERE p.invoice_id = i.id AND p.status = 'CONFIRMED'), 0) FROM invoices i "
        "WHERE i.id = :id",
        id=invoice_id,
    )
    assert rows[0][0] == rows[0][1]
