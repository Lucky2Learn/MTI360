"""Shared Phase 02-1 test helpers: the admissions team, courses and leads.

Extends the T01 two-institute world (``identity_support.build_world``):

* ``maya`` — Institute A, all campuses, Admissions manager;
* ``kiran`` — Institute A, campus A1 only, Admissions manager (restricted:
  ``course.manage`` is tenant-wide, so not effective);
* ``ravi`` — Institute A, campus A1 only, Counsellor;
* ``sita`` — Institute A, campus A2 only, Counsellor;
* ``carol`` (T01) — Institute B owner.

Fake contact data only: ``.example`` emails and numbers from the fictitious
``90000 10xxx`` range.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from identity_support import Harness, add_membership, add_user, assign_role
from tenant_admin_support import data, send, sign_in

from app.core.tenancy import system_context

COURSES = "/api/v1/courses"
LEADS = "/api/v1/leads"
FOLLOW_UPS = "/api/v1/lead-follow-ups"


@dataclass
class Team:
    h: Harness

    def membership(self, key: str) -> uuid.UUID:
        return self.h.world.memberships[key]


async def system_role(h: Harness, tenant_id: uuid.UUID, template: str) -> uuid.UUID:
    rows = await h.owner(
        "SELECT id FROM roles WHERE tenant_id = :t AND template_code = :c", t=tenant_id, c=template
    )
    return uuid.UUID(str(rows[0][0]))


async def add_member(
    h: Harness,
    name: str,
    *,
    tenant_id: uuid.UUID,
    template: str,
    campuses: tuple[uuid.UUID, ...] = (),
) -> uuid.UUID:
    async with system_context(h.factory) as db:
        await add_user(db, h.world, name)
    membership = await add_membership(
        h.factory,
        h.world,
        f"{name}_m",
        user=name,
        tenant_id=tenant_id,
        scope="SELECTED" if campuses else "ALL",
        campuses=campuses,
    )
    role_key = f"{template.lower()}_{tenant_id.hex[-6:]}"
    if role_key not in h.world.roles:
        h.world.roles[role_key] = await system_role(h, tenant_id, template)
    await assign_role(h.factory, h.world, f"{name}_m", role_key)
    return membership


async def admissions_team(h: Harness) -> Team:
    w = h.world
    await add_member(h, "maya", tenant_id=w.tenant_a, template="ADMISSIONS_MANAGER")
    await add_member(
        h, "kiran", tenant_id=w.tenant_a, template="ADMISSIONS_MANAGER", campuses=(w.campus_a1,)
    )
    await add_member(
        h, "ravi", tenant_id=w.tenant_a, template="COUNSELLOR", campuses=(w.campus_a1,)
    )
    await add_member(
        h, "sita", tenant_id=w.tenant_a, template="COUNSELLOR", campuses=(w.campus_a2,)
    )
    return Team(h)


async def as_user(h: Harness, user: str) -> str:
    """Sign in (choosing the user's only institute) and return the CSRF token."""
    return await sign_in(h, user)


async def new_course(
    h: Harness, csrf: str, code: str, *, activate: bool = True, **fields: Any
) -> dict[str, Any]:
    body = {"code": code, "name": f"{code} programme", "category": "PRE_SEA", **fields}
    course = data(await send(h, "POST", COURSES, csrf, body), 201)
    if activate:
        course = data(
            await send(
                h,
                "POST",
                f"{COURSES}/{course['id']}/status",
                csrf,
                {"status": "ACTIVE", "version": course["version"]},
            )
        )
    return course  # type: ignore[no-any-return]


_SEQUENCE = iter(range(100, 1000))


def fake_mobile() -> str:
    return f"+91 90000 10{next(_SEQUENCE):03d}"


async def new_lead(h: Harness, csrf: str, **fields: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "full_name": "Arjun Nair",
        "mobile": fake_mobile(),
        "source": "WALK_IN",
        **fields,
    }
    return data(await send(h, "POST", LEADS, csrf, body), 201)  # type: ignore[no-any-return]
