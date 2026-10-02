"""Session, institute/campus selection, password reset and invitations through the API (T01-04).

Covers the D04 campus contract, tenant IDOR, stale sessions, the D19
invitation contract, post-commit email and the absence of tokens in logs and
audit rows.
"""

import logging
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
    add_invitation,
    add_reset_token,
    auth_harness,
)
from sqlalchemy import text

from app.core.tenancy import system_context
from app.integrations.email import FakeEmailSender

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

NEW_PASSWORD = "Steady as she goes, helmsman"


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        yield harness


async def _signed_in(h: Harness, user: str) -> str:
    """Sign in; return the CSRF token (the cookie stays in the client)."""
    response = await h.login(user)
    assert response.status_code == 200, response.text
    return str(response.json()["data"]["csrf_token"])


async def _put(h: Harness, path: str, body: dict[str, Any], csrf: str) -> Any:
    return await h.client.put(f"/api/v1/session/{path}", json=body, headers={"X-CSRF-Token": csrf})


async def _probe(h: Harness) -> Any:
    return await h.client.get("/api/v1/probe/context")


# --- Session read and access levels ------------------------------------------------------------


async def test_session_routes_need_a_session_and_tenant_routes_a_ready_one(h: Harness) -> None:
    assert (await h.client.get("/api/v1/session")).status_code == 401
    assert (await _probe(h)).status_code == 401

    await _signed_in(h, "bob")  # no institute yet
    assert (await h.client.get("/api/v1/session")).status_code == 200
    assert (await _probe(h)).status_code == 401  # Access.SESSION only (D12)


async def test_the_request_context_comes_from_the_session_only(h: Harness) -> None:
    await _signed_in(h, "alice")

    response = await h.client.get(
        "/api/v1/probe/context",
        params={"tenant_id": str(h.world.tenant_b)},
        headers={"X-Tenant-ID": str(h.world.tenant_b)},
    )

    assert response.json() == {"user": str(h.world.users["alice"]), "tenant": str(h.world.tenant_a)}


@pytest.mark.parametrize("change", ["revoked", "idle", "absolute", "disabled"])
async def test_stale_sessions_are_refused(h: Harness, change: str) -> None:
    await _signed_in(h, "alice")
    user = h.world.users["alice"]
    statements = {
        "revoked": "UPDATE user_sessions SET revoked_at = now(), revoke_reason = 'logout' "
        "WHERE user_id = :u",
        "idle": "UPDATE user_sessions SET idle_expires_at = now() - interval '1 second' "
        "WHERE user_id = :u",
        "absolute": "UPDATE user_sessions SET absolute_expires_at = now() - interval '1 second' "
        "WHERE user_id = :u",
        "disabled": "UPDATE users SET status = 'DISABLED' WHERE id = :u",
    }
    await h.owner(statements[change], u=user)

    assert (await h.client.get("/api/v1/session")).status_code == 401
    assert (await _probe(h)).status_code == 401


async def test_a_revoked_membership_drops_the_institute_from_the_session(h: Harness) -> None:
    await _signed_in(h, "alice")
    await h.owner(
        "UPDATE tenant_memberships SET status = 'REVOKED' WHERE id = :m",
        m=h.world.memberships["alice_a"],
    )

    session = await h.client.get("/api/v1/session")

    assert session.json()["data"]["active_institute"] is None
    assert session.json()["data"]["institutes"] == []
    assert (await _probe(h)).status_code == 401


# --- Institute selection ------------------------------------------------------------------------


async def test_choosing_an_institute_rotates_the_session(h: Harness) -> None:
    csrf = await _signed_in(h, "bob")
    old_token = h.client.cookies[COOKIE]

    switched = await _put(h, "tenant", {"tenant_id": str(h.world.tenant_b)}, csrf)
    new_token = switched.cookies[COOKIE]
    after = await h.client.get("/api/v1/session")

    assert switched.status_code == 200
    assert new_token != old_token
    assert switched.json()["data"]["active_institute"]["id"] == str(h.world.tenant_b)
    assert switched.json()["data"]["csrf_token"] != csrf  # bound to the new session
    assert after.json()["data"]["active_institute"]["id"] == str(h.world.tenant_b)
    assert (await _probe(h)).json()["tenant"] == str(h.world.tenant_b)  # the next request
    h.client.cookies.set(COOKIE, old_token)
    assert (await h.client.get("/api/v1/session")).status_code == 401
    assert {row.event_type for row in await h.audit(switched)} == {
        "auth.session.created",
        "auth.session.rotated",
        "auth.tenant.switched",
    }


@pytest.mark.parametrize("target", ["other_tenant", "unknown"])
async def test_an_institute_without_membership_is_not_found(h: Harness, target: str) -> None:
    csrf = await _signed_in(h, "carol")  # member of B only
    tenant = h.world.tenant_a if target == "other_tenant" else uuid.uuid7()

    response = await _put(h, "tenant", {"tenant_id": str(tenant)}, csrf)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert "set-cookie" not in response.headers


async def test_an_inaccessible_institute_cannot_be_chosen(h: Harness) -> None:
    csrf = await _signed_in(h, "bob")
    await h.owner("UPDATE tenants SET status = 'SUSPENDED' WHERE id = :t", t=h.world.tenant_b)

    assert (await _put(h, "tenant", {"tenant_id": str(h.world.tenant_b)}, csrf)).status_code == 404


async def test_selection_bodies_reject_extra_fields(h: Harness) -> None:
    csrf = await _signed_in(h, "bob")

    response = await _put(
        h, "tenant", {"tenant_id": str(h.world.tenant_b), "user_id": str(uuid.uuid7())}, csrf
    )

    assert response.status_code == 422


# --- Campus selection (D04) ----------------------------------------------------------------------


async def test_a_restricted_user_chooses_one_of_their_campuses(h: Harness) -> None:
    csrf = await _signed_in(h, "dave")
    token = h.client.cookies[COOKIE]
    assert (await _probe(h)).status_code == 401  # selection pending: session routes only

    chosen = await _put(h, "campus", {"campus_id": str(h.world.campus_a2)}, csrf)

    assert chosen.status_code == 200
    assert "set-cookie" not in chosen.headers  # no rotation (D04 rule 10)
    assert h.client.cookies[COOKIE] == token
    data = chosen.json()["data"]
    assert data["status"] == "ready"
    assert data["active_campus"]["id"] == str(h.world.campus_a2)
    assert (await _probe(h)).status_code == 200
    assert [row.event_type for row in await h.audit(chosen)] == ["auth.campus.switched"]


@pytest.mark.parametrize("campus", ["other_tenant", "unknown", "all"])
async def test_campuses_outside_the_options_are_not_found(h: Harness, campus: str) -> None:
    csrf = await _signed_in(h, "dave")
    value = {"other_tenant": str(h.world.campus_b1), "unknown": str(uuid.uuid7()), "all": None}[
        campus
    ]

    response = await _put(h, "campus", {"campus_id": value}, csrf)

    assert response.status_code == 404  # "all" is never allowed for a restricted scope


async def test_all_campus_scope_switches_between_one_campus_and_all(h: Harness) -> None:
    csrf = await _signed_in(h, "alice")

    one = await _put(h, "campus", {"campus_id": str(h.world.campus_a1)}, csrf)
    everything = await _put(h, "campus", {"campus_id": None}, csrf)
    missing_key = await _put(h, "campus", {}, csrf)

    assert one.json()["data"]["active_campus"]["id"] == str(h.world.campus_a1)
    assert everything.json()["data"]["active_campus"] is None
    assert everything.json()["data"]["all_campuses_allowed"] is True
    assert missing_key.status_code == 422


async def test_a_withdrawn_campus_sends_the_user_back_to_selection(h: Harness) -> None:
    csrf = await _signed_in(h, "dave")
    await _put(h, "campus", {"campus_id": str(h.world.campus_a1)}, csrf)
    async with system_context(h.factory, tenant_id=h.world.tenant_a) as db:
        campus_a3 = uuid.uuid7()
        await db.execute(
            text(
                "INSERT INTO campuses (id, tenant_id, name, code, version) "
                "VALUES (:id, :t, 'Kochi Campus', 'KOCHI', 1)"
            ),
            {"id": campus_a3, "t": h.world.tenant_a},
        )
        await db.execute(
            text(
                "INSERT INTO membership_campuses (id, tenant_id, membership_id, campus_id) "
                "VALUES (:id, :t, :m, :c)"
            ),
            {
                "id": uuid.uuid7(),
                "t": h.world.tenant_a,
                "m": h.world.memberships["dave_a"],
                "c": campus_a3,
            },
        )
    await h.owner(  # A1 withdrawn from dave's selection (owner: no DELETE grant at runtime)
        "DELETE FROM membership_campuses WHERE membership_id = :m AND campus_id = :c",
        m=h.world.memberships["dave_a"],
        c=h.world.campus_a1,
    )

    session = (await h.client.get("/api/v1/session")).json()["data"]

    assert session["campus_selection_required"] is True
    assert session["active_campus"] is None
    assert {c["id"] for c in session["campus_options"]} == {str(h.world.campus_a2), str(campus_a3)}
    assert (await _probe(h)).status_code == 401


# --- Password reset ------------------------------------------------------------------------------


async def test_reset_requests_look_the_same_for_known_and_unknown_emails(h: Harness) -> None:
    known = await h.client.post(
        "/api/v1/auth/password-reset", json={"email": h.world.email("alice")}
    )
    unknown = await h.client.post(
        "/api/v1/auth/password-reset", json={"email": f"nobody.{h.world.suffix}@x.example"}
    )

    assert (known.status_code, unknown.status_code) == (202, 202)
    assert known.content == unknown.content == b"null"
    (message,) = h.email.sent  # sent after the response, only for the real account
    assert message.to == h.world.email("alice")
    assert "/reset-password#token=" in message.body


async def test_a_reset_token_changes_the_password_once_and_ends_every_session(h: Harness) -> None:
    await _signed_in(h, "alice")
    session_token = h.client.cookies[COOKIE]
    await h.owner(
        "UPDATE user_credentials SET failed_login_count = 4 WHERE user_id = :u",
        u=h.world.users["alice"],
    )
    await h.client.post("/api/v1/auth/password-reset", json={"email": h.world.email("alice")})
    token = h.email.sent[-1].body.split("#token=")[1].split()[0]
    h.client.cookies.clear()

    confirmed = await h.client.post(
        "/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD}
    )
    reused = await h.client.post(
        "/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD}
    )

    assert confirmed.status_code == 204
    assert reused.status_code == 404
    h.client.cookies.set(COOKIE, session_token)
    assert (await h.client.get("/api/v1/session")).status_code == 401  # revoked
    h.client.cookies.clear()
    assert (await h.login("alice")).status_code == 401  # old password
    assert (await h.login("alice", NEW_PASSWORD)).status_code == 200
    (credential,) = await h.owner(
        "SELECT failed_login_count FROM user_credentials WHERE user_id = :u",
        u=h.world.users["alice"],
    )
    assert credential.failed_login_count == 0
    assert {row.event_type for row in await h.audit(confirmed)} == {
        "auth.password_reset.completed",
        "auth.session.revoked",
    }


async def test_a_new_reset_request_invalidates_the_previous_token(h: Harness) -> None:
    for _ in range(2):
        await h.client.post("/api/v1/auth/password-reset", json={"email": h.world.email("alice")})
    first, second = (m.body.split("#token=")[1].split()[0] for m in h.email.sent)

    stale = await h.client.post(
        "/api/v1/auth/password-reset/confirm", json={"token": first, "new_password": NEW_PASSWORD}
    )
    fresh = await h.client.post(
        "/api/v1/auth/password-reset/confirm", json={"token": second, "new_password": NEW_PASSWORD}
    )

    assert (stale.status_code, fresh.status_code) == (404, 204)


async def test_expired_and_unknown_reset_tokens_are_not_found(h: Harness) -> None:
    _, expired = await add_reset_token(
        h.factory, h.world, "alice", expires_in=-timedelta(seconds=1)
    )
    responses = [
        await h.client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": NEW_PASSWORD},
        )
        for token in (expired, "A" * 43)
    ]

    assert [r.status_code for r in responses] == [404, 404]
    assert responses[0].json()["error"]["message"] == responses[1].json()["error"]["message"]


@pytest.mark.parametrize(
    ("password", "code"),
    [("too short", "password_too_short"), ("unbelievable", "password_too_common")],
)
async def test_weak_new_passwords_are_rejected(h: Harness, password: str, code: str) -> None:
    _, token = await add_reset_token(h.factory, h.world, "alice")

    response = await h.client.post(
        "/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": password}
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["code"] == code
    assert password not in response.text


async def test_a_failed_email_does_not_undo_the_reset_request(h: Harness) -> None:
    h.service.email_sender = FakeEmailSender(fail=True)

    response = await h.client.post(
        "/api/v1/auth/password-reset", json={"email": h.world.email("alice")}
    )

    assert response.status_code == 202
    rows = await h.owner(
        "SELECT count(*) AS n FROM password_reset_tokens WHERE user_id = :u AND used_at IS NULL "
        "AND invalidated_at IS NULL",
        u=h.world.users["alice"],
    )
    assert rows[0].n == 1


async def test_the_reset_response_has_a_time_floor(h: Harness) -> None:
    from dataclasses import replace
    from time import monotonic

    h.service.config = replace(h.service.config, reset_response_floor_seconds=0.3)
    durations = []
    for email in (h.world.email("alice"), f"nobody.{h.world.suffix}@x.example"):
        started = monotonic()
        await h.client.post("/api/v1/auth/password-reset", json={"email": email})
        durations.append(monotonic() - started)

    assert min(durations) >= 0.3


# --- Invitations (D19) ---------------------------------------------------------------------------


async def test_preview_shows_only_institute_masked_email_and_account_kind(h: Harness) -> None:
    _, new_token = await add_invitation(
        h.factory, h.world, "frank", tenant_id=h.world.tenant_a, new_account=True
    )
    _, existing_token = await add_invitation(
        h.factory, h.world, "carol", tenant_id=h.world.tenant_a, new_account=False
    )

    new = await h.client.post("/api/v1/auth/invitations/preview", json={"token": new_token})
    existing = await h.client.post(
        "/api/v1/auth/invitations/preview", json={"token": existing_token}
    )

    assert new.status_code == 200
    data = new.json()["data"]
    assert set(data) == {"institute_name", "email_masked", "account"}
    assert data["account"] == "new"
    assert data["institute_name"].startswith("Western Maritime Academy")
    assert data["email_masked"] == f"f•••@{h.world.email('frank').split('@')[1]}"
    assert existing.json()["data"]["account"] == "existing"
    assert await h.audit(new) == []  # no audit event, no side effect


async def test_unusable_invitations_are_one_generic_not_found(h: Harness) -> None:
    _, expired = await add_invitation(
        h.factory,
        h.world,
        "gina",
        tenant_id=h.world.tenant_a,
        new_account=True,
        expires_in=-timedelta(seconds=1),
    )
    withdrawn_id, withdrawn = await add_invitation(
        h.factory, h.world, "hari", tenant_id=h.world.tenant_a, new_account=True
    )
    await h.owner("UPDATE user_invitations SET revoked_at = now() WHERE id = :i", i=withdrawn_id)
    _, accepted = await add_invitation(
        h.factory, h.world, "ivan", tenant_id=h.world.tenant_a, new_account=True
    )
    await h.client.post(
        "/api/v1/auth/invitations/accept",
        json={"token": accepted, "display_name": "Ivan", "password": NEW_PASSWORD},
    )

    responses = [
        await h.client.post("/api/v1/auth/invitations/preview", json={"token": token})
        for token in (expired, withdrawn, accepted, "B" * 43)
    ]

    assert [r.status_code for r in responses] == [404] * 4
    assert len({r.json()["error"]["message"] for r in responses}) == 1


async def test_a_new_account_accepts_with_name_and_password_without_signing_in(h: Harness) -> None:
    _, token = await add_invitation(
        h.factory, h.world, "frank", tenant_id=h.world.tenant_a, new_account=True
    )

    accepted = await h.client.post(
        "/api/v1/auth/invitations/accept",
        json={"token": token, "display_name": "Frank D'Souza", "password": NEW_PASSWORD},
    )

    assert accepted.status_code == 204
    assert "set-cookie" not in accepted.headers  # never signs in
    (user,) = await h.owner(
        "SELECT status, display_name, email_verified_at FROM users WHERE id = :u",
        u=h.world.users["frank"],
    )
    assert (user.status, user.display_name) == ("ACTIVE", "Frank D'Souza")
    assert user.email_verified_at is not None
    assert (await h.login("frank", NEW_PASSWORD)).json()["data"]["status"] == "ready"
    assert [row.event_type for row in await h.audit(accepted)] == ["auth.invitation.accepted"]


async def test_an_existing_account_never_gets_a_new_password(h: Harness) -> None:
    _, token = await add_invitation(
        h.factory, h.world, "carol", tenant_id=h.world.tenant_a, new_account=False
    )

    with_password = await h.client.post(
        "/api/v1/auth/invitations/accept", json={"token": token, "password": NEW_PASSWORD}
    )
    accepted = await h.client.post("/api/v1/auth/invitations/accept", json={"token": token})

    assert with_password.status_code == 422
    assert accepted.status_code == 204
    assert (await h.login("carol", NEW_PASSWORD)).status_code == 401
    data = (await h.login("carol")).json()["data"]  # the existing password still works
    assert {i["id"] for i in data["institutes"]} == {str(h.world.tenant_a), str(h.world.tenant_b)}


async def test_a_new_account_must_choose_a_name_and_a_strong_password(h: Harness) -> None:
    _, token = await add_invitation(
        h.factory, h.world, "frank", tenant_id=h.world.tenant_a, new_account=True
    )

    missing = await h.client.post("/api/v1/auth/invitations/accept", json={"token": token})
    weak = await h.client.post(
        "/api/v1/auth/invitations/accept",
        json={"token": token, "display_name": "Frank", "password": "unbelievable"},
    )

    assert missing.status_code == 422
    assert {d["field"] for d in missing.json()["error"]["details"]} == {"display_name", "password"}
    assert weak.json()["error"]["details"][0]["code"] == "password_too_common"


# --- Secrets never leak ---------------------------------------------------------------------------


async def test_tokens_and_passwords_never_reach_logs_or_audit(
    h: Harness, caplog: pytest.LogCaptureFixture
) -> None:
    _, invitation = await add_invitation(
        h.factory, h.world, "frank", tenant_id=h.world.tenant_a, new_account=True
    )
    with caplog.at_level(logging.DEBUG):
        login = await h.login("alice")
        session_token = login.cookies[COOKIE]
        await h.client.post("/api/v1/auth/password-reset", json={"email": h.world.email("alice")})
        reset_token = h.email.sent[-1].body.split("#token=")[1].split()[0]
        confirm = await h.client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": reset_token, "new_password": NEW_PASSWORD},
        )
        preview = await h.client.post(
            "/api/v1/auth/invitations/preview", json={"token": invitation}
        )
        accept = await h.client.post(
            "/api/v1/auth/invitations/accept",
            json={"token": invitation, "display_name": "Frank", "password": PASSWORD + "!"},
        )

    audit = [
        row for response in (login, confirm, preview, accept) for row in await h.audit(response)
    ]
    rendered = caplog.text + repr([r.__dict__ for r in caplog.records]) + repr(audit)
    for secret in (session_token, reset_token, invitation, PASSWORD, NEW_PASSWORD, PASSWORD + "!"):
        assert secret not in rendered
    paths = [
        getattr(r, "path", "") for r in caplog.records if r.getMessage() == "request.completed"
    ]
    assert "/api/v1/auth/invitations/preview" in paths
    assert all("token" not in path for path in paths)
