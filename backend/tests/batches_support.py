"""Shared Phase 02-6 test helpers: batches, paid admissions and allocation.

Builds on the admissions team (``maya`` all campuses, ``kiran`` A1 admissions
managers; ``ravi`` A1, ``sita`` A2 counsellors) and the finance team
(``fiona`` finance manager, ``farah`` A1 finance officer). Fake people only.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any

from finance_support import ITEMS_TOTAL, issue, pay, today_ist
from httpx import ASGITransport, AsyncClient
from identity_support import PASSWORD, Harness
from tenant_admin_support import data, send, sign_in

BATCHES = "/api/v1/batches"
ALLOCATIONS = "/api/v1/batch-allocations"


def start(days: int = 30) -> str:
    return (today_ist() + timedelta(days=days)).isoformat()


async def new_batch(
    h: Harness,
    csrf: str,
    course_id: str,
    campus: uuid.UUID,
    *,
    code: str | None = None,
    capacity: int = 24,
    **fields: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "course_id": course_id,
        "campus_id": str(campus),
        "code": code or f"B-{uuid.uuid4().hex[:8].upper()}",
        "name": "DNS Batch 2026-B",
        "intake_label": "July 2026",
        "start_date": start(30),
        "end_date": start(395),
        "capacity": capacity,
        **fields,
    }
    return data(await send(h, "POST", BATCHES, csrf, body), 201)  # type: ignore[no-any-return]


async def batch(h: Harness, batch_id: str) -> dict[str, Any]:
    return data(await h.client.get(f"{BATCHES}/{batch_id}"))  # type: ignore[no-any-return]


async def allocate(
    h: Harness, csrf: str, batch_id: str, admission_id: str, override: str | None = None
) -> Any:
    body: dict[str, Any] = {"admission_id": admission_id}
    if override is not None:
        body["override_reason"] = override
    return await send(h, "POST", f"{BATCHES}/{batch_id}/allocations", csrf, body)


async def pay_in_full(h: Harness, admission_id: str, *, user: str = "fiona") -> dict[str, Any]:
    """Issue the admission's fee invoice and record one cash payment of the total."""
    csrf = await sign_in(h, user)
    invoice = data(await issue(h, csrf, admission_id), 201)
    data(await pay(h, csrf, invoice["id"], ITEMS_TOTAL), 201)
    return invoice  # type: ignore[no-any-return]


async def admission_status(h: Harness, admission_id: str) -> str:
    rows = await h.owner("SELECT status FROM admissions WHERE id = :id", id=admission_id)
    return str(rows[0][0])


@asynccontextmanager
async def client_for(h: Harness, user: str) -> AsyncIterator[tuple[AsyncClient, str]]:
    """A second, independently signed-in client (concurrent requests by another user)."""
    transport = ASGITransport(app=h.app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url=str(h.client.base_url), headers=dict(h.client.headers)
    ) as client:
        login = await client.post(
            "/api/v1/auth/login", json={"email": h.world.email(user), "password": PASSWORD}
        )
        assert login.status_code == 200, login.text
        payload = login.json()["data"]
        assert payload["status"] == "ready", payload["status"]
        yield client, payload["csrf_token"]
