"""Optional tenant MFA over HTTP (T01-06; TASKS.md T01-06).

Users without MFA sign in exactly as in T01-04. A user who enrols gets an
MFA-pending session at the next sign-in: no institute, no permissions, only
the MFA routes; a TOTP or recovery code completes sign-in and rotates the
session.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from conftest import DatabaseUnderTest
from identity_support import COOKIE, Harness, auth_harness
from platform_support import StepClock

from app.core.security import totp

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        harness.service._clock = StepClock()
        yield harness


def _data(response: Any) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()["data"]
    return data


def _clock(h: Harness) -> StepClock:
    clock = h.service._clock
    assert isinstance(clock, StepClock)
    return clock


def _code(h: Harness, secret: str) -> str:
    return totp.code_at(secret, totp.time_step(_clock(h).tick()))


async def _post(h: Harness, path: str, csrf: str, body: dict[str, Any] | None = None) -> Any:
    return await h.client.post(path, json=body or {}, headers={"X-CSRF-Token": csrf})


async def _enrol(h: Harness, user: str) -> tuple[str, list[str]]:
    csrf = _data(await h.login(user))["csrf_token"]
    enrolment = await _post(h, "/api/v1/session/mfa/enrolment", csrf)
    assert enrolment.headers["Cache-Control"] == "no-store"
    secret = _data(enrolment)["secret"]
    confirmed = await _post(
        h, "/api/v1/session/mfa/enrolment/confirm", csrf, {"code": _code(h, secret)}
    )
    codes = _data(confirmed)["recovery_codes"]
    assert (await h.client.post("/api/v1/auth/logout")).status_code == 204
    return secret, codes


async def test_users_without_mfa_sign_in_as_before(h: Harness) -> None:
    session = _data(await h.login("alice"))
    assert session["status"] == "ready"
    assert session["mfa_enabled"] is False


async def test_enrolment_needs_a_valid_first_code(h: Harness) -> None:
    csrf = _data(await h.login("alice"))["csrf_token"]
    secret = _data(await _post(h, "/api/v1/session/mfa/enrolment", csrf))["secret"]
    wrong = await _post(h, "/api/v1/session/mfa/enrolment/confirm", csrf, {"code": "000000"})
    assert wrong.status_code == 422
    assert _data(await h.client.get("/api/v1/session"))["mfa_enabled"] is False
    confirmed = await _post(
        h, "/api/v1/session/mfa/enrolment/confirm", csrf, {"code": _code(h, secret)}
    )
    assert len(_data(confirmed)["recovery_codes"]) == 10
    assert _data(await h.client.get("/api/v1/session"))["mfa_enabled"] is True
    again = await _post(h, "/api/v1/session/mfa/enrolment", csrf)
    assert again.status_code == 409


async def test_an_enrolled_user_gets_a_restricted_pending_session(h: Harness) -> None:
    secret, _ = await _enrol(h, "alice")
    login = await h.login("alice")
    pending = _data(login)
    assert pending["status"] == "mfa_required"
    assert (pending["permissions"], pending["institutes"], pending["active_institute"]) == (
        [],
        [],
        None,
    )
    csrf = pending["csrf_token"]
    # Nothing but the MFA routes.
    assert (await h.client.get("/api/v1/session")).status_code == 401
    assert (await h.client.get("/api/v1/probe/context")).status_code == 401
    switch = await h.client.put(
        "/api/v1/session/tenant",
        json={"tenant_id": str(h.world.tenant_a)},
        headers={"X-CSRF-Token": csrf},
    )
    assert switch.status_code == 401

    verified = await _post(h, "/api/v1/auth/mfa/verify", csrf, {"code": _code(h, secret)})
    session = _data(verified)
    assert session["status"] == "ready"
    assert session["mfa_enabled"] is True
    assert "role.read" in session["permissions"]
    assert verified.cookies[COOKIE] != login.cookies[COOKIE]
    assert (await h.client.get("/api/v1/probe/context")).status_code == 200
    # The verified session no longer reaches the MFA step.
    again = await _post(h, "/api/v1/auth/mfa/verify", session["csrf_token"], {"code": "123456"})
    assert again.status_code == 401


async def test_mfa_happens_before_institute_selection(h: Harness) -> None:
    secret, _ = await _enrol(h, "bob")  # two institutes
    csrf = _data(await h.login("bob"))["csrf_token"]
    verified = await _post(h, "/api/v1/auth/mfa/verify", csrf, {"code": _code(h, secret)})
    assert _data(verified)["status"] == "institute_selection_required"


async def test_recovery_codes_are_single_use(h: Harness) -> None:
    _, codes = await _enrol(h, "carol")
    csrf = _data(await h.login("carol"))["csrf_token"]
    used = await _post(h, "/api/v1/auth/mfa/recovery", csrf, {"recovery_code": codes[0]})
    assert _data(used)["status"] == "ready"
    await h.client.post("/api/v1/auth/logout")
    csrf = _data(await h.login("carol"))["csrf_token"]
    reused = await _post(h, "/api/v1/auth/mfa/recovery", csrf, {"recovery_code": codes[0]})
    assert reused.status_code == 422


async def test_five_wrong_codes_end_the_pending_session(h: Harness) -> None:
    await _enrol(h, "dave")
    csrf = _data(await h.login("dave"))["csrf_token"]
    statuses = [
        (await _post(h, "/api/v1/auth/mfa/verify", csrf, {"code": "000000"})).status_code
        for _ in range(5)
    ]
    assert statuses == [422, 422, 422, 422, 401]
    assert (await _post(h, "/api/v1/auth/mfa/verify", csrf, {"code": "000000"})).status_code == 401


async def test_removing_mfa_needs_a_current_code(h: Harness) -> None:
    secret, _ = await _enrol(h, "alice")
    csrf = _data(await h.login("alice"))["csrf_token"]
    csrf = _data(await _post(h, "/api/v1/auth/mfa/verify", csrf, {"code": _code(h, secret)}))[
        "csrf_token"
    ]
    wrong = await _post(h, "/api/v1/session/mfa/remove", csrf, {"code": "000000"})
    assert wrong.status_code == 422
    removed = await _post(h, "/api/v1/session/mfa/remove", csrf, {"code": _code(h, secret)})
    assert removed.status_code == 204
    events = [row.event_type for row in await h.audit(removed)]
    assert events == ["auth.mfa.removed"]
    await h.client.post("/api/v1/auth/logout")
    assert _data(await h.login("alice"))["status"] == "ready"
