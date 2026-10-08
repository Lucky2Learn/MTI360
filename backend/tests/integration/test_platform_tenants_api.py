"""Platform tenant administration over HTTP (T01-07; D7-1, D7-6, D7-7, D7-8, D15).

The real application, PostgreSQL and Redis. Provisioning creates a working
institute (the owner accepts through the T01-04 invitation flow and gets the
owner role); suspension ends the institute's sessions; the platform never
reaches another tenant's rows.
"""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from conftest import DatabaseUnderTest
from identity_support import COOKIE as TENANT_COOKIE
from identity_support import add_session, add_user, build_world
from platform_support import PlatformHarness, platform_harness

from app.core.tenancy import system_context

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

TENANTS = "/api/v1/platform/tenants"


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[PlatformHarness]:
    async with platform_harness(migrated_database, redis_url) as harness:
        yield harness


def _data(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()["data"]


def _body(h: PlatformHarness, owner_email: str | None = None, **overrides: Any) -> dict[str, Any]:
    suffix = uuid.uuid7().hex[-8:]
    body: dict[str, Any] = {
        "name": f"Coastal Maritime Training Institute {suffix}",
        "campus": {"name": "Kochi Campus", "code": f"koc-{suffix}"},
        "owner": {
            "email": owner_email or f"principal.{suffix}@coastalmaritime.example",
            "display_name": "Captain Meera Nair",
        },
    }
    body.update(overrides)
    return body


def _token(h: PlatformHarness) -> str:
    return str(h.email.sent[-1].body.split("#token=")[1].split()[0])


async def _provision(h: PlatformHarness, csrf: str, **kwargs: Any) -> dict[str, Any]:
    response = await h.post(TENANTS, csrf, _body(h, **kwargs))
    data: dict[str, Any] = _data(response, 201)
    return data


# --- Provisioning (D7-1, D7-7) -------------------------------------------------------------


async def test_provisioning_creates_a_working_institute(h: PlatformHarness) -> None:
    csrf = await h.admin()
    body = _body(h)
    response = await h.post(TENANTS, csrf, body)
    data = _data(response, 201)
    tenant = data["tenant"]
    assert tenant["status"] == "TRIAL"
    assert tenant["owner"] == {
        "display_name": "Captain Meera Nair",
        "email": body["owner"]["email"],
        "status": "INVITED",
    }
    assert data["campus"]["code"] == body["campus"]["code"].upper()
    assert data["owner_account"] == "new"
    tenant_id = uuid.UUID(tenant["id"])

    # One transaction: tenant, campus, the four system roles (two since Phase 02-1),
    # membership, role, invitation; audited.
    counts = await h.owner(
        "SELECT (SELECT count(*) FROM campuses WHERE tenant_id = :t), "
        "(SELECT count(*) FROM roles WHERE tenant_id = :t AND is_system), "
        "(SELECT count(*) FROM tenant_memberships WHERE tenant_id = :t AND status = 'INVITED'), "
        "(SELECT count(*) FROM membership_roles mr JOIN roles r ON r.id = mr.role_id "
        "  WHERE mr.tenant_id = :t AND r.template_code = 'INSTITUTE_OWNER'), "
        "(SELECT count(*) FROM user_invitations WHERE tenant_id = :t)",
        t=tenant_id,
    )
    assert tuple(counts[0]) == (1, 4, 1, 1, 1)
    events = await h.audit(response)
    assert [row[0] for row in events] == [
        "platform.tenant.created",
        "platform.tenant.owner_invited",
    ]
    stored = await h.owner(
        "SELECT tenant_id, principal_id, realm FROM audit_events WHERE request_id = :r",
        r=uuid.UUID(response.headers["X-Request-ID"]),
    )
    assert {tuple(row) for row in stored} == {(tenant_id, h.world.users["nora"], "platform")}

    # The email goes to the owner with a fragment link; the token is stored only as an HMAC.
    message = h.email.sent[-1]
    assert message.to == body["owner"]["email"]
    assert "/accept-invitation#token=" in message.body
    token = _token(h)
    assert token not in str(events)
    hashes = await h.owner(
        "SELECT token_hash FROM user_invitations WHERE tenant_id = :t", t=tenant_id
    )
    assert token not in str(hashes)

    # The owner accepts through the T01-04 flow and gets every tenant permission.
    accept = await h.client.post(
        "/api/v1/auth/invitations/accept",
        json={"token": token, "display_name": "Meera Nair", "password": "Monsoon swell off Kochi"},
    )
    assert accept.status_code == 204, accept.text
    login = await h.client.post(
        "/api/v1/auth/login",
        json={"email": body["owner"]["email"], "password": "Monsoon swell off Kochi"},
    )
    assert login.status_code == 200, login.text
    session = await h.client.get("/api/v1/session")
    assert session.json()["data"]["roles"] == [{"name": "Institute owner", "is_system": True}]


async def test_an_existing_account_is_invited_without_changing_it(h: PlatformHarness) -> None:
    world = await build_world(h.factory)
    csrf = await h.admin()
    before = await h.owner(
        "SELECT u.display_name, u.status, c.password_hash FROM users u "
        "JOIN user_credentials c ON c.user_id = u.id WHERE u.id = :u",
        u=world.users["erin"],
    )
    data = await _provision(h, csrf, owner_email=world.email("erin"))
    assert data["owner_account"] == "existing"
    assert data["tenant"]["owner"]["display_name"] == "Erin"  # the existing name is kept
    after = await h.owner(
        "SELECT u.display_name, u.status, c.password_hash FROM users u "
        "JOIN user_credentials c ON c.user_id = u.id WHERE u.id = :u",
        u=world.users["erin"],
    )
    assert after == before
    preview = await h.client.post("/api/v1/auth/invitations/preview", json={"token": _token(h)})
    assert preview.json()["data"]["account"] == "existing"


async def test_a_disabled_identity_cannot_be_the_owner(h: PlatformHarness) -> None:
    world = await build_world(h.factory)
    async with system_context(h.factory) as db:
        await add_user(db, world, "fiona", status="DISABLED")
    csrf = await h.admin()
    response = await h.post(TENANTS, csrf, _body(h, owner_email=world.email("fiona")))
    assert response.status_code == 409
    assert h.email.sent == [] or all(m.to != world.email("fiona") for m in h.email.sent)


async def test_provisioning_validates_and_rejects_unknown_fields(h: PlatformHarness) -> None:
    csrf = await h.admin()
    bad_code = _body(h)
    bad_code["campus"]["code"] = "-bad code"
    assert (await h.post(TENANTS, csrf, bad_code)).status_code == 422
    smuggled = _body(h)
    smuggled["status"] = "ACTIVE"
    assert (await h.post(TENANTS, csrf, smuggled)).status_code == 422
    smuggled = _body(h)
    smuggled["tenant_id"] = str(uuid.uuid7())
    assert (await h.post(TENANTS, csrf, smuggled)).status_code == 422
    bad_email = _body(h)
    bad_email["owner"]["email"] = "not an email"
    assert (await h.post(TENANTS, csrf, bad_email)).status_code == 422


async def test_provisioning_never_touches_another_tenant(h: PlatformHarness) -> None:
    world = await build_world(h.factory)
    snapshot = (
        "SELECT (SELECT count(*) FROM campuses WHERE tenant_id = ANY(:t)) "
        "+ (SELECT count(*) FROM roles WHERE tenant_id = ANY(:t)) "
        "+ (SELECT count(*) FROM tenant_memberships WHERE tenant_id = ANY(:t)) "
        "+ (SELECT count(*) FROM user_invitations WHERE tenant_id = ANY(:t))"
    )
    tenants = [world.tenant_a, world.tenant_b]
    before = (await h.owner(snapshot, t=tenants))[0][0]
    csrf = await h.admin()
    await _provision(h, csrf)
    assert (await h.owner(snapshot, t=tenants))[0][0] == before


# --- Authorization -----------------------------------------------------------------------------


async def test_provisioning_needs_the_permission(h: PlatformHarness) -> None:
    csrf = await h.admin("omar")  # SECURITY_AUDIT_ADMIN: audit.read only
    response = await h.post(TENANTS, csrf, _body(h))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"
    assert (await h.client.get(TENANTS)).status_code == 403


async def test_a_tenant_session_cannot_administer_tenants(h: PlatformHarness) -> None:
    world = await build_world(h.factory)
    _, token = await add_session(h.factory, world, "alice", tenant_id=world.tenant_a)
    h.client.cookies.set(TENANT_COOKIE, token)
    assert (await h.client.get(TENANTS)).status_code == 401
    assert (await h.client.get(f"{TENANTS}/{world.tenant_a}")).status_code == 401


# --- List and detail ---------------------------------------------------------------------------


async def test_list_search_filter_and_detail(h: PlatformHarness) -> None:
    csrf = await h.admin()
    created = await _provision(h, csrf)
    name = created["tenant"]["name"]
    found = await h.client.get(TENANTS, params={"q": name[-8:], "status": "TRIAL"})
    data = found.json()
    assert [item["name"] for item in data["data"]] == [name]
    assert data["meta"]["page"] == {"limit": 25, "offset": 0, "total": 1}
    assert "owner" not in data["data"][0]
    detail = await h.client.get(f"{TENANTS}/{created['tenant']['id']}")
    assert _data(detail)["owner"]["status"] == "INVITED"
    assert (await h.client.get(f"{TENANTS}/{uuid.uuid7()}")).status_code == 404
    assert (await h.client.get(TENANTS, params={"sort": "owner"})).status_code == 422
    assert (await h.client.get(TENANTS, params={"limit": 101})).status_code == 422


async def test_the_detail_shows_only_the_owner(h: PlatformHarness) -> None:
    world = await build_world(h.factory)  # tenant A has members but no owner pointer
    await h.admin()
    detail = _data(await h.client.get(f"{TENANTS}/{world.tenant_a}"))
    assert detail["owner"] is None
    assert world.email("alice") not in str(detail)


# --- Suspension and reactivation (D15, D7-6) ---------------------------------------------------


async def test_suspension_needs_step_up_reason_and_version(h: PlatformHarness) -> None:
    world = await build_world(h.factory)
    csrf = await h.admin()
    path = f"{TENANTS}/{world.tenant_a}/suspend"
    version = _data(await h.client.get(f"{TENANTS}/{world.tenant_a}"))["version"]
    assert (await h.post(path, csrf, {"reason": " ", "version": version})).status_code == 422
    assert (await h.post(path, csrf, {"reason": "x" * 501, "version": version})).status_code == 422
    stale = await h.post(path, csrf, {"reason": "Unpaid invoices", "version": version + 7})
    assert stale.status_code == 409
    await h.stale("nora")
    step_up = await h.post(path, csrf, {"reason": "Unpaid invoices", "version": version})
    assert step_up.status_code == 403
    assert step_up.json()["error"]["code"] == "STEP_UP_REQUIRED"
    status = await h.owner("SELECT status FROM tenants WHERE id = :t", t=world.tenant_a)
    assert status[0][0] == "ACTIVE"


async def test_suspension_ends_the_institutes_sessions_only(h: PlatformHarness) -> None:
    world = await build_world(h.factory)
    alice_a, alice_token = await add_session(h.factory, world, "alice", tenant_id=world.tenant_a)
    bob_b, _ = await add_session(h.factory, world, "bob", tenant_id=world.tenant_b)
    bob_a, _ = await add_session(h.factory, world, "bob", tenant_id=world.tenant_a)
    choosing, _ = await add_session(h.factory, world, "dave")  # no institute yet
    csrf = await h.admin()
    version = _data(await h.client.get(f"{TENANTS}/{world.tenant_a}"))["version"]
    response = await h.post(
        f"{TENANTS}/{world.tenant_a}/suspend",
        csrf,
        {"reason": "Compliance hold: DG Shipping audit", "version": version},
    )
    assert _data(response)["status"] == "SUSPENDED"
    sessions = await h.owner(
        "SELECT id, revoke_reason FROM user_sessions WHERE id = ANY(:ids)",
        ids=[alice_a, bob_b, bob_a, choosing],
    )
    reasons = dict(sessions)
    assert reasons == {
        alice_a: "tenant_suspended",
        bob_a: "tenant_suspended",
        bob_b: None,
        choosing: None,
    }
    events = await h.audit(response)
    assert [(row[0], row[1]["reason"], row[1]["revoked"], row[2]) for row in events] == [
        ("platform.tenant.suspended", "Compliance hold: DG Shipping audit", 2, world.tenant_a)
    ]

    # The revoked session is no longer usable.
    h.client.cookies.clear()
    h.client.cookies.set(TENANT_COOKIE, alice_token)
    assert (await h.client.get("/api/v1/session")).status_code == 401
    h.client.cookies.clear()

    # Suspending again is an invalid transition; reactivation never restores sessions.
    await h.sign_in("nora")
    csrf = _data(await h.client.get("/api/v1/platform/session"))["csrf_token"]
    version = _data(await h.client.get(f"{TENANTS}/{world.tenant_a}"))["version"]
    again = await h.post(
        f"{TENANTS}/{world.tenant_a}/suspend", csrf, {"reason": "Twice", "version": version}
    )
    assert again.status_code == 409
    reactivated = await h.post(
        f"{TENANTS}/{world.tenant_a}/reactivate",
        csrf,
        {"reason": "Audit closed", "version": version},
    )
    assert _data(reactivated)["status"] == "ACTIVE"
    assert [row[0] for row in await h.audit(reactivated)] == ["platform.tenant.reactivated"]
    still = await h.owner(
        "SELECT revoked_at IS NOT NULL FROM user_sessions WHERE id = :s", s=alice_a
    )
    assert still[0][0] is True


async def test_only_suspended_institutes_are_reactivated(h: PlatformHarness) -> None:
    world = await build_world(h.factory)
    csrf = await h.admin()
    version = _data(await h.client.get(f"{TENANTS}/{world.tenant_b}"))["version"]
    response = await h.post(
        f"{TENANTS}/{world.tenant_b}/reactivate", csrf, {"reason": "Not needed", "version": version}
    )
    assert response.status_code == 409


# --- Owner invitation resend (D7-8) ------------------------------------------------------------


async def test_the_owner_invitation_can_be_resent_until_accepted(h: PlatformHarness) -> None:
    csrf = await h.admin()
    created = await _provision(h, csrf)
    first = _token(h)
    path = f"{TENANTS}/{created['tenant']['id']}/owner-invitation/resend"
    response = await h.post(path, csrf)
    assert response.status_code == 202
    second = _token(h)
    assert second != first
    assert [(row[0], row[1]) for row in await h.audit(response)] == [
        ("platform.tenant.owner_invitation.resent", {"revoked": 1})
    ]
    old = await h.client.post("/api/v1/auth/invitations/preview", json={"token": first})
    assert old.status_code == 404
    accept = await h.client.post(
        "/api/v1/auth/invitations/accept",
        json={"token": second, "display_name": "Meera Nair", "password": "Monsoon swell off Kochi"},
    )
    assert accept.status_code == 204
    h.client.cookies.clear()
    await h.sign_in("nora")
    csrf = _data(await h.client.get("/api/v1/platform/session"))["csrf_token"]
    assert (await h.post(path, csrf)).status_code == 409
    assert (
        await h.post(f"{TENANTS}/{uuid.uuid7()}/owner-invitation/resend", csrf)
    ).status_code == 404
