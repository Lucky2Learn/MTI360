"""Platform identity and MFA security suite (T01-06; D6-1 … D6-5).

Realm isolation, generic failures and timing, lockout and rate limits, MFA
brute force and secret exposure, password reset (D6-2) and the MFA reset
capability (D6-3), through the real application, PostgreSQL and Redis.
"""

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from conftest import DatabaseUnderTest
from identity_support import COOKIE as TENANT_COOKIE
from identity_support import add_session, build_world
from platform_support import (
    PLATFORM_COOKIE,
    PLATFORM_PASSWORD,
    PlatformHarness,
    platform_harness,
)
from sqlalchemy import insert, text

from app.api.realms import REALM_PREFIXES, Access, realm_router
from app.core.audit.security import security_event_scope
from app.core.authz import require_permission
from app.core.context import Realm, RequestContext, context_scope, current_context
from app.core.db.session import DbSession
from app.core.errors import (
    NotFoundError,
    PermissionDeniedError,
    StepUpRequiredError,
    ValidationFailedError,
)
from app.core.tenancy import system_context
from app.modules.identity.models import User, UserCredential
from app.modules.platform_identity.permissions import PLATFORM_USER_READ
from app.modules.platform_identity.roles import PlatformRole, platform_permissions

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

AUTH = "/api/v1/platform/auth"


def _probe() -> Any:
    probe = realm_router(Realm.PLATFORM, access=Access.AUTHENTICATED)

    @probe.get("/probe/tenant-data", dependencies=[require_permission(PLATFORM_USER_READ)])
    async def tenant_data(db: DbSession) -> dict[str, Any]:
        context = current_context()
        counts = {}
        for table in ("campuses", "tenant_memberships", "users", "roles", "user_mfa_factors"):
            counts[table] = (await db.execute(text(f"SELECT count(*) FROM {table}"))).scalar()  # noqa: S608
        return {"tenant": context.tenant_id, "counts": counts}

    return probe


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[PlatformHarness]:
    async with platform_harness(migrated_database, redis_url) as harness:
        harness.app.include_router(_probe(), prefix=REALM_PREFIXES[Realm.PLATFORM])
        yield harness


def _error(response: Any) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return {k: v for k, v in body.items() if k != "request_id"}


# --- Realm isolation ------------------------------------------------------------------------------


async def test_tenant_and_platform_sessions_never_cross_realms(h: PlatformHarness) -> None:
    world = await build_world(h.factory)
    _, tenant_token = await add_session(h.factory, world, "alice", tenant_id=world.tenant_a)
    h.client.cookies.set(TENANT_COOKIE, tenant_token)
    assert (await h.client.get("/api/v1/session")).status_code == 200
    for path in ("/api/v1/platform/session", "/api/v1/platform/probe/tenant-data"):
        assert (await h.client.get(path)).status_code == 401
    h.client.cookies.clear()

    await h.enrol("nora")
    assert set(h.client.cookies.keys()) == {PLATFORM_COOKIE}
    assert (await h.client.get("/api/v1/platform/session")).status_code == 200
    assert (await h.client.get("/api/v1/session")).status_code == 401
    # The platform token is not a tenant token either.
    h.client.cookies.set(TENANT_COOKIE, h.client.cookies[PLATFORM_COOKIE])
    assert (await h.client.get("/api/v1/session")).status_code == 401


async def test_a_platform_session_reaches_no_tenant_data(h: PlatformHarness) -> None:
    await build_world(h.factory)
    await h.enrol("nora")  # SUPER_ADMIN, every platform permission
    body = (await h.client.get("/api/v1/platform/probe/tenant-data")).json()
    assert body["tenant"] is None
    assert body["counts"] == dict.fromkeys(
        ("campuses", "tenant_memberships", "users", "roles", "user_mfa_factors"), 0
    )


async def test_the_same_email_is_two_separate_identities(h: PlatformHarness) -> None:
    email = h.world.email("pia")
    user_id = uuid.uuid7()
    tenant_password = "Different tenant password 42"
    hash_ = h.service.hasher.hash_sync(tenant_password)
    async with system_context(h.factory) as db:
        await db.execute(
            insert(User.__table__).values(  # type: ignore[arg-type]
                id=user_id, email=email, display_name="Pia Tenant", status="ACTIVE", version=1
            )
        )
        await db.execute(
            insert(UserCredential.__table__).values(  # type: ignore[arg-type]
                id=uuid.uuid7(),
                user_id=user_id,
                password_hash=hash_,
                password_changed_at=datetime.now(UTC),
            )
        )
    # Each realm accepts only its own credential.
    crossed = await h.client.post(
        f"{AUTH}/login", json={"email": email, "password": tenant_password}
    )
    assert crossed.status_code == 401
    tenant_attempt = await h.client.post(
        "/api/v1/auth/login", json={"email": email, "password": PLATFORM_PASSWORD}
    )
    assert tenant_attempt.status_code == 401
    platform = await h.client.post(
        f"{AUTH}/login", json={"email": email, "password": PLATFORM_PASSWORD}
    )
    assert platform.json()["data"]["status"] == "mfa_enrolment_required"


# --- Authentication: generic failures, timing, lockout, rate limits -------------------------------


async def test_every_sign_in_failure_is_the_same_401(h: PlatformHarness) -> None:
    attempts = [
        {"email": f"nobody.{h.world.suffix}@mti360-platform.example", "password": "x" * 12},
        {"email": h.world.email("omar"), "password": "Wrong but long enough"},
        {"email": h.world.email("quinn"), "password": PLATFORM_PASSWORD},  # suspended
        {"email": "not an email", "password": "x" * 12},
    ]
    bodies = []
    for attempt in attempts:
        response = await h.client.post(f"{AUTH}/login", json=attempt)
        assert response.status_code == 401
        assert PLATFORM_COOKIE not in response.cookies
        bodies.append(_error(response))
    assert all(body == bodies[0] for body in bodies)


async def test_unknown_accounts_still_verify_a_hash(
    h: PlatformHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str | None] = []
    original = h.service.hasher.verify

    async def spy(password_hash: str | None, password: str) -> bool:
        calls.append(password_hash)
        return await original(password_hash, password)

    monkeypatch.setattr(h.service.hasher, "verify", spy)
    await h.client.post(
        f"{AUTH}/login",
        json={"email": f"ghost.{h.world.suffix}@mti360-platform.example", "password": "x" * 12},
    )
    assert calls == [None]  # the dummy hash, same cost as a real one


async def test_five_wrong_passwords_lock_the_account(h: PlatformHarness) -> None:
    for _ in range(5):
        response = await h.client.post(
            f"{AUTH}/login", json={"email": h.world.email("pia"), "password": "Wrong but long 1"}
        )
    events = [row[0] for row in await h.audit(response)]
    assert "platform.auth.account.locked" in events
    locked = await h.login("pia")
    assert locked.status_code == 401


async def test_sign_in_is_rate_limited_per_account(h: PlatformHarness) -> None:
    statuses = []
    for _ in range(11):
        response = await h.client.post(
            f"{AUTH}/login",
            json={"email": f"flood.{h.world.suffix}@mti360-platform.example", "password": "x" * 12},
        )
        statuses.append(response.status_code)
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
    assert int(response.headers["Retry-After"]) >= 1


async def test_sign_in_rotates_a_presented_session(h: PlatformHarness) -> None:
    first = await h.login("pia")
    old = first.cookies[PLATFORM_COOKIE]
    second = await h.login("pia")
    assert second.cookies[PLATFORM_COOKIE] != old
    h.client.cookies.set(PLATFORM_COOKIE, old)
    csrf = first.json()["data"]["csrf_token"]
    assert (await h.post(f"{AUTH}/mfa/enrolment", csrf)).status_code == 401


# --- MFA: brute force and secret exposure ---------------------------------------------------------


async def test_mfa_brute_force_ends_the_session_and_feeds_the_lockout(h: PlatformHarness) -> None:
    await h.enrol("omar")
    await h.client.post(f"{AUTH}/logout")
    csrf = (await h.login("omar")).json()["data"]["csrf_token"]
    statuses = [
        (await h.post(f"{AUTH}/mfa/verify", csrf, {"code": "000000"})).status_code for _ in range(5)
    ]
    assert statuses == [422, 422, 422, 422, 401]
    # Five failures also count toward the credential lockout.
    locked = await h.owner(
        "SELECT locked_until IS NOT NULL FROM platform_user_credentials "
        "WHERE platform_user_id = :u",
        u=h.world.users["omar"],
    )
    assert locked[0][0] is True


async def test_a_totp_code_cannot_be_replayed_across_sign_ins(h: PlatformHarness) -> None:
    await h.enrol("pia")
    await h.client.post(f"{AUTH}/logout")
    csrf = (await h.login("pia")).json()["data"]["csrf_token"]
    code = h.code("pia")
    assert (await h.post(f"{AUTH}/mfa/verify", csrf, {"code": code})).status_code == 200
    await h.client.post(f"{AUTH}/logout")
    csrf = (await h.login("pia")).json()["data"]["csrf_token"]
    assert (await h.post(f"{AUTH}/mfa/verify", csrf, {"code": code})).status_code == 422


async def test_the_secret_is_encrypted_at_rest_and_never_exposed_again(
    h: PlatformHarness, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    _, codes = await h.enrol("nora")
    secret = h.secrets["nora"]
    stored = await h.owner(
        "SELECT id, secret_ciphertext FROM platform_mfa_factors "
        "WHERE platform_user_id = :u AND disabled_at IS NULL",
        u=h.world.users["nora"],
    )
    factor_id, ciphertext = stored[0]
    assert secret not in ciphertext
    keyring = h.app.state.settings.encryption_keyring()
    plain = keyring.decrypt(ciphertext, associated_data=f"platform_mfa_factors:{factor_id}")
    assert plain.decode() == secret
    session = await h.client.get("/api/v1/platform/session")
    assert secret not in session.text
    rows = await h.owner(
        "SELECT metadata::text FROM audit_events WHERE target_id = :u", u=h.world.users["nora"]
    )
    stored_codes = await h.owner(
        "SELECT code_hash FROM platform_recovery_codes WHERE platform_user_id = :u",
        u=h.world.users["nora"],
    )
    for value in (secret, *codes, *(code.replace("-", "") for code in codes)):
        assert value not in caplog.text
        assert value not in str(rows)
        assert value not in str(stored_codes)


# --- Password reset (D6-2) ------------------------------------------------------------------------


async def test_reset_requests_look_the_same_for_every_email(h: PlatformHarness) -> None:
    emails = [
        h.world.email("pia"),
        f"nobody.{h.world.suffix}@mti360-platform.example",
        h.world.email("quinn"),  # suspended
    ]
    bodies = set()
    for email in emails:
        response = await h.client.post(f"{AUTH}/password-reset", json={"email": email})
        assert response.status_code == 202
        bodies.add(response.content)
    assert len(bodies) == 1  # identical responses: no account enumeration
    assert [message.to for message in h.email.sent] == [h.world.email("pia")]
    body = h.email.sent[0].body
    assert "/platform/reset-password#token=" in body


async def test_a_reset_is_single_use_and_expires_and_never_bypasses_mfa(
    h: PlatformHarness,
) -> None:
    await h.enrol("nora")
    await h.client.post(f"{AUTH}/password-reset", json={"email": h.world.email("nora")})
    token = h.email.sent[-1].body.split("#token=")[1].split()[0]
    new_password = "Tide tables checked twice"
    confirm = await h.client.post(
        f"{AUTH}/password-reset/confirm", json={"token": token, "new_password": new_password}
    )
    assert confirm.status_code == 204
    assert token not in str(await h.audit(confirm))
    # Single use; every session ended (including the one used to enrol).
    again = await h.client.post(
        f"{AUTH}/password-reset/confirm", json={"token": token, "new_password": new_password}
    )
    assert again.status_code == 404
    assert (await h.client.get("/api/v1/platform/session")).status_code == 401
    # MFA is still required with the new password.
    login = await h.client.post(
        f"{AUTH}/login", json={"email": h.world.email("nora"), "password": new_password}
    )
    assert login.json()["data"]["status"] == "mfa_required"

    # An expired token is refused like an unknown one.
    await h.client.post(f"{AUTH}/password-reset", json={"email": h.world.email("pia")})
    expired = h.email.sent[-1].body.split("#token=")[1].split()[0]
    await h.owner(
        "UPDATE platform_password_reset_tokens SET expires_at = now() - interval '1 hour' "
        "WHERE platform_user_id = :u",
        u=h.world.users["pia"],
    )
    stale = await h.client.post(
        f"{AUTH}/password-reset/confirm", json={"token": expired, "new_password": new_password}
    )
    assert stale.status_code == 404


# --- MFA reset for a lost device (D6-3) -----------------------------------------------------------


@asynccontextmanager
async def _acting(
    h: PlatformHarness, name: str, *, verified_ago: timedelta | None = timedelta(minutes=1)
) -> AsyncIterator[RequestContext]:
    roles = {
        "nora": {PlatformRole.SUPER_ADMIN},
        "omar": {PlatformRole.SECURITY_AUDIT_ADMIN},
    }[name]
    context = RequestContext(
        realm=Realm.PLATFORM,
        request_id=uuid.uuid7(),
        principal_id=h.world.users[name],
        permissions=platform_permissions(frozenset(roles)),
        mfa_verified_at=datetime.now(UTC) - verified_ago if verified_ago else None,
    )
    with context_scope(context):
        async with security_event_scope(h.factory, context):
            yield context


async def test_mfa_reset_requires_the_permission_step_up_and_a_reason(h: PlatformHarness) -> None:
    target = h.world.users["pia"]
    async with _acting(h, "omar"):  # no platform_user.update
        with pytest.raises(PermissionDeniedError):
            await h.service.reset_mfa(target, "Lost phone")
    async with _acting(h, "nora", verified_ago=timedelta(minutes=11)):
        with pytest.raises(StepUpRequiredError):
            await h.service.reset_mfa(target, "Lost phone")
    async with _acting(h, "nora"):
        for reason in ("", "   ", "x" * 501):
            with pytest.raises(ValidationFailedError):
                await h.service.reset_mfa(target, reason)
        with pytest.raises(PermissionDeniedError):
            await h.service.reset_mfa(h.world.users["nora"], "My own device")
        with pytest.raises(NotFoundError):
            await h.service.reset_mfa(uuid.uuid7(), "Unknown user")


async def test_mfa_reset_revokes_sessions_and_forces_re_enrolment(h: PlatformHarness) -> None:
    await h.enrol("pia")  # enrolled, with a live session in the client
    target = h.world.users["pia"]
    async with _acting(h, "nora") as context:
        result = await h.service.reset_mfa(target, "Lost phone on the vessel")
    assert (result.factors_disabled, result.sessions_revoked) == (1, 1)
    assert (await h.client.get("/api/v1/platform/session")).status_code == 401
    login = await h.login("pia")
    assert login.json()["data"]["status"] == "mfa_enrolment_required"
    events = await h.owner(
        "SELECT event_type, metadata, principal_id FROM audit_events WHERE request_id = :r",
        r=context.request_id,
    )
    assert [(row[0], row[1]["reason"], row[2]) for row in events] == [
        ("platform.mfa.reset", "Lost phone on the vessel", h.world.users["nora"])
    ]
    codes = await h.owner(
        "SELECT count(*) FROM platform_recovery_codes WHERE platform_user_id = :u "
        "AND used_at IS NULL AND invalidated_at IS NULL",
        u=target,
    )
    assert codes[0][0] == 0


async def test_settings_require_the_encryption_key_for_the_platform(h: PlatformHarness) -> None:
    # The application under test was built with a real key ring (not the development key).
    ring = h.app.state.settings.encryption_keyring()
    assert ring.current_id == "k1"
    assert replace(h.service.config).session_secret
