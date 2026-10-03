"""Platform user administration over HTTP (T01-07; D7-2 … D7-5, D6-3).

Invitations (D7-3), step-up for every change (D6-5, D7-4), optimistic
versions, self-protection and the last active guardian (D7-5), session
revocation on suspension, and the MFA-reset route.
"""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import anyio
import pytest
from conftest import DatabaseUnderTest
from platform_support import PLATFORM_COOKIE, PlatformHarness, platform_harness
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.context import Realm, RequestContext
from app.core.db.session import context_transaction
from app.modules.platform_identity import admin_repository
from app.modules.platform_identity.lookup import admin_target_transaction

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

USERS = "/api/v1/platform/platform-users"
INVITATIONS = "/api/v1/platform/auth/invitations"


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[PlatformHarness]:
    async with platform_harness(migrated_database, redis_url) as harness:
        yield harness


def _data(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()["data"]


def _email(h: PlatformHarness) -> str:
    return f"ops.{uuid.uuid7().hex[-8:]}.{h.world.suffix}@mti360-platform.example"


def _token(h: PlatformHarness) -> str:
    return str(h.email.sent[-1].body.split("#token=")[1].split()[0])


async def _create(h: PlatformHarness, csrf: str, roles: list[str] | None = None) -> dict[str, Any]:
    body = {
        "email": _email(h),
        "display_name": "Rohan Kulkarni",
        "roles": roles or ["SUPPORT_ADMIN"],
    }
    data: dict[str, Any] = _data(await h.post(USERS, csrf, body), 201)
    return data


async def _version(h: PlatformHarness, user_id: Any) -> int:
    version: int = _data(await h.client.get(f"{USERS}/{user_id}"))["version"]
    return version


# --- Create and invitation (D7-3) ------------------------------------------------------------


async def test_an_invited_user_sets_a_password_then_must_enrol_mfa(h: PlatformHarness) -> None:
    csrf = await h.admin()
    email = _email(h)
    response = await h.post(
        USERS,
        csrf,
        {"email": email.upper(), "display_name": "Rohan Kulkarni", "roles": ["SUPPORT_ADMIN"]},
    )
    created = _data(response, 201)
    assert created["email"] == email
    assert created["status"] == "INVITED"
    assert created["roles"] == ["SUPPORT_ADMIN"]
    assert [row[0] for row in await h.audit(response)] == [
        "platform.user.created",
        "platform.user.invitation.sent",
    ]
    message = h.email.sent[-1]
    assert message.to == email
    assert "/platform/accept-invitation#token=" in message.body
    token = _token(h)
    stored = await h.owner(
        "SELECT token_hash FROM platform_user_invitations WHERE platform_user_id = :u",
        u=uuid.UUID(created["id"]),
    )
    assert token not in str(stored)

    # An invited user cannot sign in.
    h.client.cookies.clear()
    login = await h.client.post(
        "/api/v1/platform/auth/login", json={"email": email, "password": "Pilot ladder rigged"}
    )
    assert login.status_code == 401

    preview = await h.client.post(f"{INVITATIONS}/preview", json={"token": token})
    assert _data(preview)["email"] == f"o•••@{email.split('@')[1]}"
    weak = await h.client.post(f"{INVITATIONS}/accept", json={"token": token, "password": "short"})
    assert weak.status_code == 422
    accept = await h.client.post(
        f"{INVITATIONS}/accept", json={"token": token, "password": "Pilot ladder rigged"}
    )
    assert accept.status_code == 204, accept.text
    assert [row[0] for row in await h.audit(accept)] == ["platform.auth.invitation.accepted"]
    # Single use.
    again = await h.client.post(
        f"{INVITATIONS}/accept", json={"token": token, "password": "Pilot ladder rigged"}
    )
    assert again.status_code == 404
    login = await h.client.post(
        "/api/v1/platform/auth/login", json={"email": email, "password": "Pilot ladder rigged"}
    )
    assert _data(login)["status"] == "mfa_enrolment_required"


async def test_unusable_invitations_look_the_same(h: PlatformHarness) -> None:
    csrf = await h.admin()
    created = await _create(h, csrf)
    expired = _token(h)
    await h.owner(
        "UPDATE platform_user_invitations SET expires_at = now() - interval '1 hour' "
        "WHERE platform_user_id = :u",
        u=uuid.UUID(created["id"]),
    )
    bodies = set()
    for token in (expired, "A" * 43):
        response = await h.client.post(f"{INVITATIONS}/preview", json={"token": token})
        assert response.status_code == 404
        bodies.add(response.json()["error"]["code"])
    assert bodies == {"NOT_FOUND"}


async def test_create_needs_step_up_and_a_unique_email(h: PlatformHarness) -> None:
    csrf = await h.admin()
    created = await _create(h, csrf)
    duplicate = await h.post(
        USERS, csrf, {"email": created["email"], "display_name": "Copy", "roles": ["BILLING_ADMIN"]}
    )
    assert duplicate.status_code == 409
    no_roles = await h.post(USERS, csrf, {"email": _email(h), "display_name": "X", "roles": []})
    assert no_roles.status_code == 422
    smuggled = await h.post(
        USERS,
        csrf,
        {"email": _email(h), "display_name": "X", "roles": ["SUPER_ADMIN"], "status": "ACTIVE"},
    )
    assert smuggled.status_code == 422
    await h.stale("nora")
    stale = await h.post(
        USERS, csrf, {"email": _email(h), "display_name": "X", "roles": ["SUPPORT_ADMIN"]}
    )
    assert stale.status_code == 403
    assert stale.json()["error"]["code"] == "STEP_UP_REQUIRED"


async def test_resend_replaces_the_invitation_of_invited_users_only(h: PlatformHarness) -> None:
    csrf = await h.admin()
    created = await _create(h, csrf)
    first = _token(h)
    response = await h.post(f"{USERS}/{created['id']}/invitation", csrf)
    assert response.status_code == 202
    assert [row[0] for row in await h.audit(response)] == [
        "platform.user.invitation.revoked",
        "platform.user.invitation.sent",
    ]
    assert (await h.client.post(f"{INVITATIONS}/preview", json={"token": first})).status_code == 404
    active = await h.post(f"{USERS}/{h.world.users['pia']}/invitation", csrf)
    assert active.status_code == 409


# --- Directory and authorization -------------------------------------------------------------


async def test_the_directory_lists_and_filters(h: PlatformHarness) -> None:
    csrf = await h.admin()
    created = await _create(h, csrf, roles=["CUSTOMER_SUCCESS_ADMIN", "BILLING_ADMIN"])
    found = await h.client.get(USERS, params={"q": created["email"], "role": "BILLING_ADMIN"})
    listing = found.json()
    assert [item["id"] for item in listing["data"]] == [created["id"]]
    assert listing["data"][0]["roles"] == ["BILLING_ADMIN", "CUSTOMER_SUCCESS_ADMIN"]
    assert listing["meta"]["page"]["total"] == 1
    for item in listing["data"]:
        assert set(item) == {
            "id",
            "email",
            "display_name",
            "status",
            "roles",
            "created_at",
            "updated_at",
            "version",
        }
    suspended = await h.client.get(USERS, params={"q": h.world.suffix, "status": "SUSPENDED"})
    assert [item["id"] for item in suspended.json()["data"]] == [str(h.world.users["quinn"])]
    assert (await h.client.get(f"{USERS}/{uuid.uuid7()}")).status_code == 404
    assert (await h.client.get(USERS, params={"sort": "password"})).status_code == 422


async def test_every_route_needs_its_permission(h: PlatformHarness) -> None:
    csrf = await h.admin("omar")  # audit.read only
    target = h.world.users["pia"]
    calls = [
        ("GET", USERS, None),
        ("GET", f"{USERS}/{target}", None),
        ("POST", USERS, {"email": _email(h), "display_name": "X", "roles": ["SUPPORT_ADMIN"]}),
        ("PATCH", f"{USERS}/{target}", {"version": 1, "display_name": "X"}),
        ("POST", f"{USERS}/{target}/suspend", {"reason": "x", "version": 1}),
        ("POST", f"{USERS}/{target}/reactivate", {"reason": "x", "version": 1}),
        ("POST", f"{USERS}/{target}/invitation", None),
        ("POST", f"{USERS}/{target}/mfa/reset", {"reason": "x"}),
    ]
    for method, path, body in calls:
        if method == "GET":
            response = await h.client.get(path)
        else:
            response = await h.send(method, path, csrf, body)
        assert response.status_code == 403, (method, path)
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"


# --- Update (roles, name) -------------------------------------------------------------------


async def test_roles_and_name_change_with_the_current_version(h: PlatformHarness) -> None:
    csrf = await h.admin()
    target = h.world.users["pia"]
    version = await _version(h, target)
    response = await h.send(
        "PATCH",
        f"{USERS}/{target}",
        csrf,
        {"version": version, "display_name": "Pia  Fernandes", "roles": ["SUPPORT_ADMIN"]},
    )
    updated = _data(response)
    assert updated["display_name"] == "Pia Fernandes"
    assert updated["roles"] == ["SUPPORT_ADMIN"]
    assert updated["version"] == version + 1
    assert [(row[0], row[1]) for row in await h.audit(response)] == [
        (
            "platform.user.updated",
            {
                "display_name_changed": True,
                "roles_added": ["SUPPORT_ADMIN"],
                "roles_removed": ["BILLING_ADMIN"],
            },
        )
    ]
    stale = await h.send(
        "PATCH", f"{USERS}/{target}", csrf, {"version": version, "display_name": "Old"}
    )
    assert stale.status_code == 409


async def test_nobody_changes_their_own_roles(h: PlatformHarness) -> None:
    csrf = await h.admin()
    me = h.world.users["nora"]
    version = await _version(h, me)
    demote = await h.send(
        "PATCH", f"{USERS}/{me}", csrf, {"version": version, "roles": ["BILLING_ADMIN"]}
    )
    assert demote.status_code == 403
    assert [row[0] for row in await h.audit(demote)] == ["platform.user.self_action_refused"]
    rename = await h.send(
        "PATCH", f"{USERS}/{me}", csrf, {"version": version, "display_name": "Nora D"}
    )
    assert _data(rename)["roles"] == ["SUPER_ADMIN"]


# --- Suspend and reactivate (D7-4, D7-5) ---------------------------------------------------


async def test_suspension_needs_step_up_and_ends_the_users_sessions(h: PlatformHarness) -> None:
    await h.enrol("pia")  # a live, full session for pia
    pia_cookie = h.client.cookies[PLATFORM_COOKIE]
    h.client.cookies.clear()
    csrf = await h.admin()
    target = h.world.users["pia"]
    version = await _version(h, target)
    await h.stale("nora")
    step_up = await h.post(
        f"{USERS}/{target}/suspend", csrf, {"reason": "Left the company", "version": version}
    )
    assert step_up.status_code == 403
    assert step_up.json()["error"]["code"] == "STEP_UP_REQUIRED"
    await h.post("/api/v1/platform/session/step-up", csrf, {"code": h.code("nora")})
    response = await h.post(
        f"{USERS}/{target}/suspend", csrf, {"reason": "Left the company", "version": version}
    )
    assert _data(response)["status"] == "SUSPENDED"
    events = await h.audit(response)
    assert [(row[0], row[1]) for row in events] == [
        ("platform.user.suspended", {"reason": "Left the company", "revoked": 1})
    ]
    revoked = await h.owner(
        "SELECT revoke_reason FROM platform_sessions WHERE platform_user_id = :u "
        "AND mfa_verified_at IS NOT NULL ORDER BY created_at DESC LIMIT 1",
        u=target,
    )
    assert revoked[0][0] == "admin_suspended"
    h.client.cookies.set(PLATFORM_COOKIE, pia_cookie)
    assert (await h.client.get("/api/v1/platform/session")).status_code == 401
    h.client.cookies.clear()

    # Reactivation restores ACTIVE; MFA is still required at sign-in.
    await h.sign_in("nora")
    csrf = _data(await h.client.get("/api/v1/platform/session"))["csrf_token"]
    version = await _version(h, target)
    reactivated = await h.post(
        f"{USERS}/{target}/reactivate", csrf, {"reason": "Rehired", "version": version}
    )
    assert _data(reactivated)["status"] == "ACTIVE"
    h.client.cookies.clear()
    assert _data(await h.login("pia"))["status"] == "mfa_required"


async def test_nobody_suspends_or_resets_themselves(h: PlatformHarness) -> None:
    csrf = await h.admin()
    me = h.world.users["nora"]
    version = await _version(h, me)
    suspend = await h.post(f"{USERS}/{me}/suspend", csrf, {"reason": "Oops", "version": version})
    assert suspend.status_code == 403
    reset = await h.post(f"{USERS}/{me}/mfa/reset", csrf, {"reason": "Lost phone"})
    assert reset.status_code == 403
    status = await h.owner("SELECT status FROM platform_users WHERE id = :u", u=me)
    assert status[0][0] == "ACTIVE"


async def test_an_invited_user_reactivates_as_invited(h: PlatformHarness) -> None:
    csrf = await h.admin()
    created = await _create(h, csrf)
    suspended = await h.post(
        f"{USERS}/{created['id']}/suspend", csrf, {"reason": "Wrong person", "version": 1}
    )
    assert _data(suspended)["status"] == "SUSPENDED"
    assert [row[0] for row in await h.audit(suspended)] == [
        "platform.user.suspended",
        "platform.user.invitation.revoked",
    ]
    reactivated = await h.post(
        f"{USERS}/{created['id']}/reactivate", csrf, {"reason": "Right person", "version": 2}
    )
    assert _data(reactivated)["status"] == "INVITED"
    again = await h.post(
        f"{USERS}/{created['id']}/reactivate", csrf, {"reason": "Twice", "version": 3}
    )
    assert again.status_code == 409


async def test_the_last_active_guardian_is_kept(
    h: PlatformHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await h.admin()
    target = h.world.users["pia"]
    version = await _version(h, target)
    # Make pia a guardian, then pretend nobody else is one.
    _data(
        await h.send(
            "PATCH", f"{USERS}/{target}", csrf, {"version": version, "roles": ["SUPER_ADMIN"]}
        )
    )

    async def nobody_else(*_: Any, **__: Any) -> int:
        return 0

    monkeypatch.setattr(admin_repository, "active_guardians", nobody_else)
    version += 1
    suspend = await h.post(
        f"{USERS}/{target}/suspend", csrf, {"reason": "Audit", "version": version}
    )
    assert suspend.status_code == 409
    demote = await h.send(
        "PATCH", f"{USERS}/{target}", csrf, {"version": version, "roles": ["BILLING_ADMIN"]}
    )
    assert demote.status_code == 409
    assert _data(await h.client.get(f"{USERS}/{target}"))["roles"] == ["SUPER_ADMIN"]


async def _try_lock(h: PlatformHarness, context: RequestContext) -> None:
    async with context_transaction(h.factory, context) as second:
        await second.execute(text("SET LOCAL lock_timeout = '200ms'"))
        await admin_repository.lock_guardians(second)


async def test_guardian_changes_are_serialised(h: PlatformHarness) -> None:
    """D7-5: a second transaction waits for the guardian lock of the first."""
    context = RequestContext(
        realm=Realm.PLATFORM, request_id=uuid.uuid7(), principal_id=h.world.users["nora"]
    )
    async with admin_target_transaction(
        h.factory, context=context, target_user_id=h.world.users["pia"]
    ) as first:
        await admin_repository.lock_guardians(first)
        with pytest.raises(DBAPIError, match="lock timeout"):
            await _try_lock(h, context)
    with anyio.fail_after(5):  # released at commit
        async with context_transaction(h.factory, context) as third:
            await admin_repository.lock_guardians(third)


async def test_guardian_count_excludes_the_target_and_inactive_users(h: PlatformHarness) -> None:
    context_user = h.world.users["nora"]
    context = RequestContext(
        realm=Realm.PLATFORM, request_id=uuid.uuid7(), principal_id=context_user
    )
    async with context_transaction(h.factory, context) as db:
        with_nora = await admin_repository.active_guardians(db, excluding=h.world.users["pia"])
        without_nora = await admin_repository.active_guardians(db, excluding=context_user)
        without_quinn = await admin_repository.active_guardians(
            db, excluding=h.world.users["quinn"]
        )
    assert with_nora - without_nora == 1  # nora is an active guardian
    assert without_quinn == with_nora  # quinn is suspended: never counted


# --- MFA reset route (D6-3) ----------------------------------------------------------------


async def test_the_mfa_reset_route_forces_re_enrolment(h: PlatformHarness) -> None:
    await h.enrol("pia")
    h.client.cookies.clear()
    csrf = await h.admin()
    target = h.world.users["pia"]
    no_reason = await h.post(f"{USERS}/{target}/mfa/reset", csrf, {"reason": "  "})
    assert no_reason.status_code == 422
    response = await h.post(f"{USERS}/{target}/mfa/reset", csrf, {"reason": "Lost phone at sea"})
    assert _data(response) == {"factors_disabled": 1, "sessions_revoked": 1}
    assert [row[0] for row in await h.audit(response)] == ["platform.mfa.reset"]
    h.client.cookies.clear()
    assert _data(await h.login("pia"))["status"] == "mfa_enrolment_required"
