"""Platform sign-in, MFA, session and step-up over HTTP (T01-06; D6-4, D6-5).

The real application, PostgreSQL and Redis; the service clock moves one TOTP
step per code (``StepClock``) so replay protection can be exercised without
sleeping.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from conftest import DatabaseUnderTest
from platform_support import PLATFORM_COOKIE, PlatformHarness, platform_harness

from app.api.realms import REALM_PREFIXES, Access, realm_router
from app.core.authz import require_permission
from app.core.context import Realm
from app.modules.platform_identity.permissions import PLATFORM_USER_READ, PLATFORM_USER_UPDATE

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

SUPER_ADMIN = sorted(
    {
        "audit.read",
        "platform_user.create",
        "platform_user.reactivate",
        "platform_user.read",
        "platform_user.suspend",
        "platform_user.update",
        "tenant.create",
        "tenant.reactivate",
        "tenant.read",
        "tenant.suspend",
    }
)
AUTH = "/api/v1/platform/auth"


def _probes() -> Any:
    probe = realm_router(Realm.PLATFORM, access=Access.AUTHENTICATED)

    @probe.get("/probe/users", dependencies=[require_permission(PLATFORM_USER_READ)])
    async def read_users() -> dict[str, str]:
        return {"ok": "read"}

    @probe.post("/probe/users/update", dependencies=[require_permission(PLATFORM_USER_UPDATE)])
    async def update_users() -> dict[str, str]:
        return {"ok": "update"}

    return probe


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[PlatformHarness]:
    async with platform_harness(migrated_database, redis_url) as harness:
        harness.app.include_router(_probes(), prefix=REALM_PREFIXES[Realm.PLATFORM])
        yield harness


def _data(response: Any) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()["data"]
    return data


async def _stale(h: PlatformHarness, name: str) -> None:
    await h.owner(
        "UPDATE platform_sessions SET mfa_verified_at = now() - interval '11 minutes' "
        "WHERE platform_user_id = :u AND revoked_at IS NULL AND mfa_verified_at IS NOT NULL",
        u=h.world.users[name],
    )


# --- Enrolment and the pending session --------------------------------------------------------


async def test_first_sign_in_requires_enrolment_then_rotates_to_a_full_session(
    h: PlatformHarness,
) -> None:
    login = await h.login("nora")
    pending = _data(login)
    assert pending["status"] == "mfa_enrolment_required"
    assert (pending["user"], pending["permissions"], pending["roles"]) == (None, [], [])
    pending_cookie = login.cookies[PLATFORM_COOKIE]
    csrf = pending["csrf_token"]

    enrolment = await h.post(f"{AUTH}/mfa/enrolment", csrf)
    assert enrolment.headers["Cache-Control"] == "no-store"
    secret = _data(enrolment)["secret"]
    assert _data(enrolment)["otpauth_uri"].startswith("otpauth://totp/MTI%20360:")
    h.secrets["nora"] = secret

    wrong = await h.post(f"{AUTH}/mfa/enrolment/confirm", csrf, {"code": "000000"})
    assert wrong.status_code == 422
    assert wrong.json()["error"]["details"][0]["code"] == "mfa_code_invalid"

    confirmed = await h.post(f"{AUTH}/mfa/enrolment/confirm", csrf, {"code": h.code("nora")})
    body = _data(confirmed)
    assert confirmed.headers["Cache-Control"] == "no-store"
    assert len(body["recovery_codes"]) == 10
    session = body["session"]
    assert session["status"] == "authenticated"
    assert session["permissions"] == SUPER_ADMIN
    assert session["roles"] == ["SUPER_ADMIN"]
    assert session["user"]["email"] == h.world.email("nora")
    assert session["mfa"]["enrolled"] is True
    assert session["mfa"]["recovery_codes_remaining"] == 10
    # Rotation: a new cookie; the pending one no longer works.
    assert confirmed.cookies[PLATFORM_COOKIE] != pending_cookie
    h.client.cookies.set(PLATFORM_COOKIE, pending_cookie)
    assert (await h.client.get("/api/v1/platform/session")).status_code == 401


async def test_a_pending_session_reaches_only_the_mfa_routes(h: PlatformHarness) -> None:
    csrf = _data(await h.login("nora"))["csrf_token"]
    for response in (
        await h.client.get("/api/v1/platform/session"),
        await h.client.get("/api/v1/platform/probe/users"),
        await h.post("/api/v1/platform/session/step-up", csrf, {"code": "123456"}),
    ):
        assert response.status_code == 401
    # Verification before enrolment fails like a wrong code.
    assert (await h.post(f"{AUTH}/mfa/verify", csrf, {"code": "123456"})).status_code == 422


async def test_a_full_session_cannot_use_the_mfa_routes(h: PlatformHarness) -> None:
    confirmed, _ = await h.enrol("nora")
    csrf = _data(confirmed)["session"]["csrf_token"]
    for path in ("enrolment", "verify"):
        response = await h.post(f"{AUTH}/mfa/{path}", csrf, {"code": "123456"})
        assert response.status_code == 401


async def test_mfa_routes_need_the_csrf_token(h: PlatformHarness) -> None:
    await h.login("nora")
    response = await h.client.post(f"{AUTH}/mfa/enrolment", json={})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SESSION_REFRESH_REQUIRED"


# --- Later sign-ins -----------------------------------------------------------------------------


async def test_an_enrolled_user_signs_in_with_totp_or_a_recovery_code(h: PlatformHarness) -> None:
    _, codes = await h.enrol("omar")
    login = _data(await h.login("omar"))
    assert login["status"] == "mfa_required"
    verified = await h.post(f"{AUTH}/mfa/verify", login["csrf_token"], {"code": h.code("omar")})
    assert _data(verified)["permissions"] == ["audit.read"]
    assert _data(verified)["roles"] == ["SECURITY_AUDIT_ADMIN"]

    csrf = _data(await h.login("omar"))["csrf_token"]
    recovered = await h.post(f"{AUTH}/mfa/recovery", csrf, {"recovery_code": codes[0]})
    assert _data(recovered)["mfa"]["recovery_codes_remaining"] == 9
    events = [row[0] for row in await h.audit(recovered)]
    assert "platform.mfa.recovery_code.used" in events
    assert "platform.auth.login.success" in events

    csrf = _data(await h.login("omar"))["csrf_token"]
    reused = await h.post(f"{AUTH}/mfa/recovery", csrf, {"recovery_code": codes[0]})
    assert reused.status_code == 422


async def test_enrolment_is_refused_once_enrolled(h: PlatformHarness) -> None:
    await h.enrol("pia")
    csrf = _data(await h.login("pia"))["csrf_token"]
    assert (await h.post(f"{AUTH}/mfa/enrolment", csrf)).status_code == 409


async def test_session_read_and_logout(h: PlatformHarness) -> None:
    await h.enrol("nora")
    session = _data(await h.client.get("/api/v1/platform/session"))
    assert session["status"] == "authenticated"
    assert session["mfa"]["step_up_expires_at"] is not None
    for key in ("id", "user_id", "session_id", "secret", "password_hash"):
        assert key not in session
    logout = await h.client.post(f"{AUTH}/logout")
    assert logout.status_code == 204
    assert (await h.client.get("/api/v1/platform/session")).status_code == 401


# --- Step-up (D6-5) -------------------------------------------------------------------------------


async def test_step_up_is_enforced_by_authorize(h: PlatformHarness) -> None:
    confirmed, _ = await h.enrol("nora")
    csrf = _data(confirmed)["session"]["csrf_token"]
    # Fresh MFA: allowed. Permissions without step-up ignore freshness.
    assert (await h.post("/api/v1/platform/probe/users/update", csrf)).status_code == 200
    await _stale(h, "nora")
    assert (await h.client.get("/api/v1/platform/probe/users")).status_code == 200
    stale = await h.post("/api/v1/platform/probe/users/update", csrf)
    assert stale.status_code == 403
    assert stale.json()["error"]["code"] == "STEP_UP_REQUIRED"
    assert [row[0] for row in await h.audit(stale)] == ["authz.step_up_required"]

    stepped = await h.post("/api/v1/platform/session/step-up", csrf, {"code": h.code("nora")})
    assert _data(stepped)["status"] == "authenticated"
    assert (await h.post("/api/v1/platform/probe/users/update", csrf)).status_code == 200


async def test_without_the_permission_step_up_is_never_offered(h: PlatformHarness) -> None:
    confirmed, _ = await h.enrol("omar")  # SECURITY_AUDIT_ADMIN
    csrf = _data(confirmed)["session"]["csrf_token"]
    await _stale(h, "omar")
    response = await h.post("/api/v1/platform/probe/users/update", csrf)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


async def test_recovery_codes_regenerate_only_with_a_fresh_step_up(h: PlatformHarness) -> None:
    confirmed, old_codes = await h.enrol("nora")
    csrf = _data(confirmed)["session"]["csrf_token"]
    await _stale(h, "nora")
    stale = await h.post("/api/v1/platform/session/mfa/recovery-codes", csrf)
    assert stale.status_code == 403
    assert stale.json()["error"]["code"] == "STEP_UP_REQUIRED"
    await h.post("/api/v1/platform/session/step-up", csrf, {"code": h.code("nora")})
    regenerated = await h.post("/api/v1/platform/session/mfa/recovery-codes", csrf)
    new_codes = _data(regenerated)["recovery_codes"]
    assert regenerated.headers["Cache-Control"] == "no-store"
    assert len(new_codes) == 10
    assert not set(new_codes) & set(old_codes)
    assert [row[0] for row in await h.audit(regenerated)] == [
        "platform.mfa.recovery_codes.regenerated"
    ]
    # The old codes no longer work.
    login_csrf = _data(await h.login("nora"))["csrf_token"]
    old = await h.post(f"{AUTH}/mfa/recovery", login_csrf, {"recovery_code": old_codes[1]})
    assert old.status_code == 422
