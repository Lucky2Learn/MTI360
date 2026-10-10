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
from typing import Any

from admissions_support import active_course
from courses_leads_support import add_member
from identity_support import Harness
from tenant_admin_support import data, send, sign_in

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
