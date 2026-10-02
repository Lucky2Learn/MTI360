"""Sign-in, sign-out, origin/CSRF and rate limits through the real API (T01-04).

The application runs against the PostgreSQL test database and a real Redis
(namespaced per test), with a fake email sender. Every assertion goes through
HTTP, the realm guard, the services and Row-Level Security together.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import pytest
from conftest import DatabaseUnderTest
from identity_support import (
    COOKIE,
    PASSWORD,
    Harness,
    add_membership,
    auth_harness,
)
from sqlalchemy import text

from app.core.ratelimit import RedisRateLimiter
from app.core.tenancy import system_context

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

GENERIC_FAILURE = {
    "code": "AUTHENTICATION_REQUIRED",
    "message": "Sign in to continue.",
    "details": [],
}


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        yield harness


def _error(response: Any) -> dict[str, Any]:
    body = dict(response.json()["error"])
    body.pop("request_id")
    return body


def _cookie(response: Any) -> str:
    return str(response.headers["set-cookie"])


# --- Successful sign-in ---------------------------------------------------------------------


async def test_one_institute_signs_in_ready_with_all_campuses(h: Harness) -> None:
    response = await h.login("alice")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "ready"
    assert data["user"] == {"display_name": "Alice", "email": h.world.email("alice")}
    assert data["active_institute"]["id"] == str(h.world.tenant_a)
    assert data["institutes"] == [data["active_institute"]]
    assert data["active_campus"] is None  # "All campuses" (D04 rule 1)
    assert data["all_campuses_allowed"] is True
    assert data["campus_selection_required"] is False
    assert {c["code"] for c in data["campus_options"]} == {"MUM", "PUNE"}
    assert len(data["csrf_token"]) == 64


async def test_the_session_cookie_is_host_bound_http_only_and_secure(h: Harness) -> None:
    response = await h.login("alice")
    cookie = _cookie(response)
    token = response.cookies[COOKIE]

    assert cookie.startswith(f"{COOKIE}=")
    for attribute in ("HttpOnly", "Secure", "Path=/", "SameSite=lax"):
        assert attribute.lower() in cookie.lower(), attribute
    assert "domain=" not in cookie.lower()
    assert token not in response.text  # never in the body
    stored = await h.owner(
        "SELECT token_hash FROM user_sessions WHERE user_id = :u", u=h.world.users["alice"]
    )
    assert stored
    assert all(row.token_hash != token and len(row.token_hash) == 64 for row in stored)


async def test_several_institutes_require_a_choice(h: Harness) -> None:
    data = (await h.login("bob")).json()["data"]

    assert data["status"] == "institute_selection_required"
    assert data["active_institute"] is None
    names = [i["name"] for i in data["institutes"]]
    assert names == sorted(names)  # by name
    assert {i["id"] for i in data["institutes"]} == {str(h.world.tenant_a), str(h.world.tenant_b)}
    trial = {i["id"]: i["is_trial"] for i in data["institutes"]}
    assert trial == {str(h.world.tenant_a): False, str(h.world.tenant_b): True}
    assert data["campus_options"] == []


async def test_restricted_campus_scope_requires_a_campus_choice(h: Harness) -> None:
    data = (await h.login("dave")).json()["data"]

    assert data["status"] == "campus_selection_required"
    assert data["campus_selection_required"] is True
    assert data["all_campuses_allowed"] is False  # D04 rule 4: never "all"
    assert data["active_campus"] is None
    assert {c["id"] for c in data["campus_options"]} == {
        str(h.world.campus_a1),
        str(h.world.campus_a2),
    }


async def test_a_single_permitted_campus_is_selected_automatically(h: Harness) -> None:
    # bob is restricted to A1 in institute A; choosing A selects A1 (D04 rule 2).
    login = await h.login("bob")
    switched = await h.client.put(
        "/api/v1/session/tenant",
        json={"tenant_id": str(h.world.tenant_a)},
        headers={"X-CSRF-Token": login.json()["data"]["csrf_token"]},
    )

    data = switched.json()["data"]
    assert data["status"] == "ready"
    assert data["active_campus"]["id"] == str(h.world.campus_a1)


# --- Failed sign-in: one generic answer -----------------------------------------------------


async def test_every_sign_in_failure_looks_the_same(h: Harness) -> None:
    world = h.world
    async with system_context(h.factory) as db:
        await db.execute(
            text("UPDATE users SET status = 'DISABLED' WHERE id = :id"),
            {"id": world.users["carol"]},
        )
    await h.owner("UPDATE tenants SET status = 'SUSPENDED' WHERE id = :t", t=world.tenant_a)
    failures = [
        await h.login("alice", "a wrong password entirely"),  # wrong password
        await h.client.post(
            "/api/v1/auth/login",
            json={"email": f"nobody.{world.suffix}@x.example", "password": PASSWORD},
        ),  # unknown account
        await h.login("erin"),  # no membership
        await h.login("carol"),  # disabled user
        await h.login("dave"),  # only institute suspended
        await h.client.post(
            "/api/v1/auth/login", json={"email": "not-an-email", "password": PASSWORD}
        ),  # implausible email
    ]

    assert {response.status_code for response in failures} == {401}
    assert all(_error(response) == GENERIC_FAILURE for response in failures)
    assert all("set-cookie" not in response.headers for response in failures)


async def test_a_suspended_membership_cannot_sign_in(h: Harness) -> None:
    await h.owner(
        "UPDATE tenant_memberships SET status = 'SUSPENDED' WHERE id = :m",
        m=h.world.memberships["alice_a"],
    )

    assert (await h.login("alice")).status_code == 401


async def test_unknown_fields_are_rejected(h: Harness) -> None:
    response = await h.client.post(
        "/api/v1/auth/login",
        json={
            "email": h.world.email("alice"),
            "password": PASSWORD,
            "tenant_id": str(h.world.tenant_b),
        },
    )

    assert response.status_code == 422
    assert PASSWORD not in response.text


async def test_failures_lock_the_account_progressively(h: Harness) -> None:
    for _ in range(5):
        assert (await h.login("alice", "not the right password")).status_code == 401
    (credential,) = await h.owner(
        "SELECT failed_login_count, locked_until, locked_until - now() AS remaining "
        "FROM user_credentials WHERE user_id = :u",
        u=h.world.users["alice"],
    )

    assert credential.failed_login_count == 5
    assert timedelta(seconds=30) < credential.remaining <= timedelta(minutes=1)
    # Locked: even the right password fails, generically, and nothing is counted.
    locked = await h.login("alice")
    assert locked.status_code == 401
    assert _error(locked) == GENERIC_FAILURE
    (after,) = await h.owner(
        "SELECT failed_login_count FROM user_credentials WHERE user_id = :u",
        u=h.world.users["alice"],
    )
    assert after.failed_login_count == 5

    # After the lock expires, the next failure locks for 5 minutes.
    await h.owner(
        "UPDATE user_credentials SET locked_until = now() - interval '1 second' WHERE user_id = :u",
        u=h.world.users["alice"],
    )
    await h.login("alice", "still not the right password")
    (second,) = await h.owner(
        "SELECT failed_login_count, locked_until - now() AS remaining FROM user_credentials "
        "WHERE user_id = :u",
        u=h.world.users["alice"],
    )
    assert second.failed_login_count == 6
    assert timedelta(minutes=4) < second.remaining <= timedelta(minutes=5)


async def test_success_resets_the_failure_counter(h: Harness) -> None:
    for _ in range(3):
        await h.login("alice", "not the right password")
    assert (await h.login("alice")).status_code == 200

    (credential,) = await h.owner(
        "SELECT failed_login_count, locked_until FROM user_credentials WHERE user_id = :u",
        u=h.world.users["alice"],
    )
    assert (credential.failed_login_count, credential.locked_until) == (0, None)


# --- Security events --------------------------------------------------------------------


async def test_sign_in_events_name_the_user_and_contain_no_secrets(h: Harness) -> None:
    success = await h.login("alice")
    failure = await h.login("alice", "not the right password")
    token = success.cookies[COOKIE]

    ok_events = {row.event_type: row for row in await h.audit(success)}
    failed_events = {row.event_type: row for row in await h.audit(failure)}

    assert set(ok_events) == {"auth.login.success", "auth.session.created"}
    login = ok_events["auth.login.success"]
    assert (login.category, login.realm, login.tenant_id, login.principal_id) == (
        "security",
        "tenant",
        None,
        None,
    )  # anonymous request context; the user is the target (D13)
    assert (login.target_type, login.target_id) == ("user", h.world.users["alice"])
    assert failed_events["auth.login.failed"]._mapping["metadata"] == {"reason": "bad_password"}
    rendered = repr([*ok_events.values(), *failed_events.values()])
    for secret in (PASSWORD, "not the right password", token, h.world.email("alice")):
        assert secret not in rendered


# --- Sign-in rotation and sign-out -------------------------------------------------------------


async def test_signing_in_again_rotates_the_presented_session(h: Harness) -> None:
    first = await h.login("alice")
    first_token = first.cookies[COOKIE]
    second = await h.login("alice")

    assert second.cookies[COOKIE] != first_token
    h.client.cookies.set(COOKIE, first_token)
    assert (await h.client.get("/api/v1/session")).status_code == 401
    rows = await h.owner(
        "SELECT revoke_reason FROM user_sessions WHERE user_id = :u ORDER BY created_at",
        u=h.world.users["alice"],
    )
    assert [row.revoke_reason for row in rows] == ["rotated", None]


async def test_logout_revokes_the_session_and_is_idempotent(h: Harness) -> None:
    login = await h.login("alice")
    token = login.cookies[COOKIE]

    first = await h.client.post("/api/v1/auth/logout")
    h.client.cookies.set(COOKIE, token)  # a stolen copy of the cookie
    after = await h.client.get("/api/v1/session")
    again = await h.client.post("/api/v1/auth/logout")
    h.client.cookies.clear()
    anonymous = await h.client.post("/api/v1/auth/logout")

    assert [first.status_code, again.status_code, anonymous.status_code] == [204, 204, 204]
    assert "max-age=0" in _cookie(first).lower()
    assert after.status_code == 401
    assert {row.event_type for row in await h.audit(first)} == {"auth.logout"}
    assert await h.audit(again) == []


# --- Origin and CSRF (D14) ------------------------------------------------------------------


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://attacker.example"},
        {"Origin": "null"},
        {"Origin": "", "Sec-Fetch-Site": "cross-site"},
    ],
)
async def test_cross_site_anonymous_requests_are_refused(
    h: Harness, headers: dict[str, str]
) -> None:
    response = await h.client.post(
        "/api/v1/auth/login",
        json={"email": h.world.email("alice"), "password": PASSWORD},
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SESSION_REFRESH_REQUIRED"
    assert "set-cookie" not in response.headers
    assert [row.event_type for row in await h.audit(response)] == ["auth.csrf.rejected"]


async def test_a_same_origin_fetch_without_origin_is_accepted(h: Harness) -> None:
    del h.client.headers["Origin"]

    refused = await h.login("alice")
    accepted = await h.client.post(
        "/api/v1/auth/login",
        json={"email": h.world.email("alice"), "password": PASSWORD},
        headers={"Sec-Fetch-Site": "same-origin"},
    )

    assert refused.status_code == 403  # neither signal
    assert accepted.status_code == 200


async def test_session_requests_need_the_csrf_token_on_unsafe_methods(h: Harness) -> None:
    login = await h.login("bob")
    csrf = login.json()["data"]["csrf_token"]
    body = {"tenant_id": str(h.world.tenant_b)}

    missing = await h.client.put("/api/v1/session/tenant", json=body)
    wrong = await h.client.put(
        "/api/v1/session/tenant", json=body, headers={"X-CSRF-Token": "0" * 64}
    )
    safe = await h.client.get("/api/v1/session")
    right = await h.client.put("/api/v1/session/tenant", json=body, headers={"X-CSRF-Token": csrf})

    assert [missing.status_code, wrong.status_code] == [403, 403]
    assert missing.json()["error"]["code"] == "SESSION_REFRESH_REQUIRED"
    assert safe.status_code == 200
    assert right.status_code == 200


# --- Rate limiting (D17) ------------------------------------------------------------------


async def test_the_ip_limit_is_twenty_attempts_with_retry_after(h: Harness) -> None:
    for index in range(20):
        response = await h.client.post(
            "/api/v1/auth/login",
            json={"email": f"probe{index}.{h.world.suffix}@x.example", "password": PASSWORD},
        )
        assert response.status_code == 401
    limited = await h.login("alice")

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert 0 < int(limited.headers["Retry-After"]) <= 300
    assert [row.event_type for row in await h.audit(limited)] == ["auth.rate_limited"]


async def test_the_account_limit_is_ten_attempts(h: Harness) -> None:
    # erin has no membership: every attempt fails before the database lockout matters.
    for _ in range(10):
        await h.client.post(
            "/api/v1/auth/login",
            json={"email": h.world.email("erin"), "password": "nope nope nope"},
        )
    limited = await h.login("erin")

    assert limited.status_code == 429
    assert 0 < int(limited.headers["Retry-After"]) <= 900


async def test_forged_forwarded_headers_do_not_change_the_ip_bucket(h: Harness) -> None:
    for index in range(20):
        await h.client.post(
            "/api/v1/auth/login",
            json={"email": f"forge{index}.{h.world.suffix}@x.example", "password": PASSWORD},
            headers={"X-Forwarded-For": f"198.51.100.{index}"},
        )
    limited = await h.client.post(
        "/api/v1/auth/login",
        json={"email": h.world.email("alice"), "password": PASSWORD},
        headers={"X-Forwarded-For": "203.0.113.99"},
    )

    assert limited.status_code == 429  # TRUSTED_PROXY_HOPS=0: the header is ignored


async def test_sign_in_fails_closed_without_redis(h: Harness) -> None:
    await h.service.rate_limiter.close()
    h.service.rate_limiter = RedisRateLimiter.from_url("redis://127.0.0.1:9/0")

    response = await h.login("alice")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert "redis" not in response.text.lower()


async def test_an_extra_membership_appears_as_an_institute_choice(h: Harness) -> None:
    await add_membership(h.factory, h.world, "alice_b", user="alice", tenant_id=h.world.tenant_b)

    data = (await h.login("alice")).json()["data"]

    assert data["status"] == "institute_selection_required"
    assert {i["id"] for i in data["institutes"]} == {str(h.world.tenant_a), str(h.world.tenant_b)}
    assert uuid.UUID(data["institutes"][0]["id"])
