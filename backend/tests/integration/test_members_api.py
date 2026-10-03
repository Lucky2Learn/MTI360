"""Tenant member administration over HTTP (T01-08; D8-1, D8-3, D8-4).

The real application, PostgreSQL and Redis, with the T01-04/T01-05 world:
``alice`` owns institute A (all campuses); ``bob`` is an Administrator of A
(campus A1 only) and of B (all campuses); ``carol`` owns B; ``dave`` holds a
custom campus role in A (A1 and A2); ``erin`` has an account and no
membership. Tests add the members they need.
"""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import anyio
import pytest
from conftest import DatabaseUnderTest
from httpx import ASGITransport, AsyncClient
from identity_support import (
    COOKIE,
    ORIGIN,
    PASSWORD,
    Harness,
    add_membership,
    add_role,
    add_user,
    assign_role,
    auth_harness,
)
from tenant_admin_support import MEMBERS, add_owner, data, send, sign_in, version

from app.core.tenancy import system_context
from app.modules.access.catalog import tenant_permissions

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

ACCEPT = "/api/v1/auth/invitations/accept"
PREVIEW = "/api/v1/auth/invitations/preview"


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        yield harness


def _email(h: Harness, name: str) -> str:
    return f"{name}.{uuid.uuid7().hex[-6:]}.{h.world.suffix}@westernmaritime.example"


def _token(h: Harness) -> str:
    return str(h.email.sent[-1].body.split("#token=")[1].split()[0])


async def _admin(h: Harness, name: str = "gina") -> uuid.UUID:
    """An Administrator of A with all campuses (every tenant permission except role.delete)."""
    return await add_owner(h, name, h.world.tenant_a, "admin_a")


async def _invite(h: Harness, csrf: str, **body: Any) -> dict[str, Any]:
    payload = {"email": _email(h, "cadet"), "display_name": "Deck Cadet Rohan Pillai", **body}
    result: dict[str, Any] = data(
        await send(h, "POST", f"{MEMBERS}/invitations", csrf, payload), 201
    )
    return result


async def _audit_types(h: Harness, response: Any) -> list[str]:
    return [row.event_type for row in await h.audit(response)]


# --- Directory and authorization ----------------------------------------------------------------


async def test_the_member_directory_is_the_active_institute_only(h: Harness) -> None:
    await sign_in(h, "alice")
    listing = (await h.client.get(MEMBERS, params={"limit": 100})).json()
    emails = {item["user"]["email"] for item in listing["data"]}
    assert {h.world.email(n) for n in ("alice", "bob", "dave")} <= emails
    assert h.world.email("carol") not in emails
    assert listing["meta"]["page"]["total"] == len(listing["data"])
    dave = next(i for i in listing["data"] if i["user"]["email"] == h.world.email("dave"))
    assert dave["campus_scope"] == "SELECTED"
    assert sorted(dave["campus_ids"]) == sorted([str(h.world.campus_a1), str(h.world.campus_a2)])
    # Another tenant's member is not found, exactly like a missing one.
    other = await h.client.get(f"{MEMBERS}/{h.world.memberships['carol_b']}")
    missing = await h.client.get(f"{MEMBERS}/{uuid.uuid7()}")
    assert other.status_code == missing.status_code == 404
    assert other.json()["error"]["code"] == missing.json()["error"]["code"]
    found = await h.client.get(MEMBERS, params={"q": h.world.email("dave"), "status": "ACTIVE"})
    assert [i["id"] for i in found.json()["data"]] == [str(h.world.memberships["dave_a"])]


async def test_member_administration_needs_tenant_wide_permissions(h: Harness) -> None:
    # member.read via a custom role, but campus-restricted (D-B1).
    csrf = await sign_in(h, "dave", campus_id=h.world.campus_a1)
    assert (await h.client.get(MEMBERS)).status_code == 403
    invite = await send(
        h, "POST", f"{MEMBERS}/invitations", csrf, {"email": _email(h, "x"), "display_name": "X"}
    )
    assert invite.status_code == 403
    csrf = await sign_in(h, "bob", h.world.tenant_a)  # Administrator, campus A1 only (D-B1)
    assert (await h.client.get(MEMBERS)).status_code == 403
    suspend = await send(
        h, "POST", f"{MEMBERS}/{h.world.memberships['dave_a']}/suspend", csrf, {"version": 1}
    )
    assert suspend.status_code == 403


async def test_requests_cannot_name_a_tenant_or_status(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    for extra in ({"tenant_id": str(h.world.tenant_b)}, {"status": "ACTIVE"}):
        response = await send(
            h,
            "POST",
            f"{MEMBERS}/invitations",
            csrf,
            {"email": _email(h, "x"), "display_name": "X", **extra},
        )
        assert response.status_code == 422


# --- Invitation (D8-1) -----------------------------------------------------------------------


async def test_a_new_invitee_is_created_invited_and_joins_through_t01_04(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    email = _email(h, "cadet")
    response = await send(
        h,
        "POST",
        f"{MEMBERS}/invitations",
        csrf,
        {
            "email": email.upper(),
            "display_name": "Deck Cadet  Rohan Pillai",
            "role_ids": [str(h.world.roles["admin_a"])],
            "campus_scope": "SELECTED",
            "campus_ids": [str(h.world.campus_a1)],
        },
    )
    invited = data(response, 201)
    member = invited["member"]
    assert invited["account"] == "new"
    assert member["status"] == "INVITED"
    assert member["user"] == {"display_name": "Deck Cadet Rohan Pillai", "email": email}
    assert member["campus_ids"] == [str(h.world.campus_a1)]
    assert [r["name"] for r in member["roles"]] == ["Administrator"]
    assert await _audit_types(h, response) == ["member.invited", "membership.role_assigned"]
    identity = await h.owner("SELECT status FROM users WHERE email = :e", e=email)
    assert identity[0][0] == "INVITED"
    token = _token(h)
    assert "/accept-invitation#token=" in h.email.sent[-1].body
    stored = await h.owner(
        "SELECT token_hash FROM user_invitations WHERE membership_id = :m",
        m=uuid.UUID(member["id"]),
    )
    assert token not in str(stored)
    assert token not in str(await h.audit(response))

    preview = data(await h.client.post(PREVIEW, json={"token": token}))
    assert preview["account"] == "new"
    accept = await h.client.post(
        ACCEPT, json={"token": token, "display_name": "Rohan Pillai", "password": PASSWORD}
    )
    assert accept.status_code == 204, accept.text
    again = await h.client.post(
        ACCEPT, json={"token": token, "display_name": "Rohan Pillai", "password": PASSWORD}
    )
    assert again.status_code == 404  # single use
    h.client.cookies.clear()
    login = data(
        await h.client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    )
    assert login["status"] == "ready"
    await sign_in(h, "alice")
    joined = data(await h.client.get(f"{MEMBERS}/{member['id']}"))
    assert joined["status"] == "ACTIVE"
    assert joined["joined_at"] is not None


async def test_an_existing_account_is_reused_unchanged(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    before = await h.owner(
        "SELECT display_name, status, version FROM users WHERE id = :u", u=h.world.users["erin"]
    )
    invited = data(
        await send(
            h,
            "POST",
            f"{MEMBERS}/invitations",
            csrf,
            {"email": h.world.email("erin"), "display_name": "Someone Else"},
        ),
        201,
    )
    assert invited["account"] == "existing"
    assert invited["member"]["user"]["display_name"] == "Erin"
    after = await h.owner(
        "SELECT display_name, status, version FROM users WHERE id = :u", u=h.world.users["erin"]
    )
    assert after == before
    assert data(await h.client.post(PREVIEW, json={"token": _token(h)}))["account"] == "existing"


async def test_disabled_identities_and_existing_members_are_refused(h: Harness) -> None:
    async with system_context(h.factory) as db:
        await add_user(db, h.world, "fiona", status="DISABLED")
    csrf = await sign_in(h, "alice")
    for email in (h.world.email("fiona"), h.world.email("bob"), h.world.email("alice")):
        response = await send(
            h, "POST", f"{MEMBERS}/invitations", csrf, {"email": email, "display_name": "X"}
        )
        assert response.status_code == 409, email
    count = await h.owner(
        "SELECT count(*) FROM tenant_memberships WHERE user_id = :u", u=h.world.users["fiona"]
    )
    assert count[0][0] == 0


async def test_invitation_campuses_must_belong_to_the_institute(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    for body in (
        {"campus_scope": "SELECTED", "campus_ids": [str(h.world.campus_b1)]},
        {"campus_scope": "SELECTED", "campus_ids": []},
        {"campus_scope": "ALL", "campus_ids": [str(h.world.campus_a1)]},
    ):
        response = await send(
            h,
            "POST",
            f"{MEMBERS}/invitations",
            csrf,
            {"email": _email(h, "x"), "display_name": "X", **body},
        )
        assert response.status_code == 422, body


async def test_initial_roles_follow_role_assign_and_no_escalation(h: Harness) -> None:
    await _admin(h)  # Administrator: no role.delete
    csrf = await sign_in(h, "gina")
    email = _email(h, "x")
    escalation = await send(
        h,
        "POST",
        f"{MEMBERS}/invitations",
        csrf,
        {"email": email, "display_name": "X", "role_ids": [str(h.world.roles["owner_a"])]},
    )
    assert escalation.status_code == 403
    # The whole invitation rolled back: no identity, no membership.
    assert (await h.owner("SELECT count(*) FROM users WHERE email = :e", e=email))[0][0] == 0
    other_tenant = await send(
        h,
        "POST",
        f"{MEMBERS}/invitations",
        csrf,
        {"email": email, "display_name": "X", "role_ids": [str(h.world.roles["admin_b"])]},
    )
    assert other_tenant.status_code == 404


async def test_expired_and_resent_invitations_stop_working(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    member = (await _invite(h, csrf))["member"]
    first = _token(h)
    resent = await send(h, "POST", f"{MEMBERS}/{member['id']}/invitation/resend", csrf)
    assert resent.status_code == 202
    assert await _audit_types(h, resent) == ["member.invitation.resent"]
    second = _token(h)
    assert (await h.client.post(PREVIEW, json={"token": first})).status_code == 404
    await h.owner(
        "UPDATE user_invitations SET expires_at = now() - interval '1 minute' "
        "WHERE membership_id = :m",
        m=uuid.UUID(member["id"]),
    )
    assert (await h.client.post(PREVIEW, json={"token": second})).status_code == 404
    active = await send(
        h, "POST", f"{MEMBERS}/{h.world.memberships['dave_a']}/invitation/resend", csrf
    )
    assert active.status_code == 409


# --- Lifecycle (D8-3) ------------------------------------------------------------------------


async def test_active_suspended_round_trip_is_versioned(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    dave = h.world.memberships["dave_a"]
    v = await version(h, dave)
    stale = await send(h, "POST", f"{MEMBERS}/{dave}/suspend", csrf, {"version": v + 3})
    assert stale.status_code == 409
    suspended = await send(h, "POST", f"{MEMBERS}/{dave}/suspend", csrf, {"version": v})
    assert data(suspended)["status"] == "SUSPENDED"
    assert await _audit_types(h, suspended) == ["member.suspended"]
    again = await send(h, "POST", f"{MEMBERS}/{dave}/suspend", csrf, {"version": v + 1})
    assert again.status_code == 409
    reinstated = await send(h, "POST", f"{MEMBERS}/{dave}/reinstate", csrf, {"version": v + 1})
    assert data(reinstated)["status"] == "ACTIVE"
    assert data(reinstated)["version"] == v + 2
    not_suspended = await send(h, "POST", f"{MEMBERS}/{dave}/reinstate", csrf, {"version": v + 2})
    assert not_suspended.status_code == 409


async def test_every_status_can_be_revoked_and_revoked_members_re_invited(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    invited = (await _invite(h, csrf))["member"]
    token = _token(h)
    revoked = await send(h, "POST", f"{MEMBERS}/{invited['id']}/revoke", csrf, {"version": 1})
    assert data(revoked)["status"] == "REVOKED"
    events = await h.audit(revoked)
    assert [(e.event_type, e.metadata) for e in events] == [
        ("member.revoked", {"from": "INVITED", "invitations_revoked": 1})
    ]
    assert (await h.client.post(PREVIEW, json={"token": token})).status_code == 404
    # REVOKED → INVITED on the same row, with a new invitation.
    reinvited = await send(h, "POST", f"{MEMBERS}/{invited['id']}/reinvite", csrf, {"version": 2})
    body = data(reinvited)
    assert (body["id"], body["status"], body["version"]) == (invited["id"], "INVITED", 3)
    assert await _audit_types(h, reinvited) == ["member.reinvited"]
    rows = await h.owner(
        "SELECT count(*) FROM tenant_memberships m JOIN users u ON u.id = m.user_id "
        "WHERE u.email = :e",
        e=invited["user"]["email"],
    )
    assert rows[0][0] == 1
    assert data(await h.client.post(PREVIEW, json={"token": _token(h)}))["account"] == "new"
    # ACTIVE and SUSPENDED members can be revoked too.
    dave = h.world.memberships["dave_a"]
    v = await version(h, dave)
    await send(h, "POST", f"{MEMBERS}/{dave}/suspend", csrf, {"version": v})
    assert (
        data(await send(h, "POST", f"{MEMBERS}/{dave}/revoke", csrf, {"version": v + 1}))["status"]
        == "REVOKED"
    )
    bob = h.world.memberships["bob_a"]
    v = await version(h, bob)
    assert (
        data(await send(h, "POST", f"{MEMBERS}/{bob}/revoke", csrf, {"version": v}))["status"]
        == "REVOKED"
    )
    # Only REVOKED members are re-invited; a revoked member is not suspended.
    assert (
        await send(h, "POST", f"{MEMBERS}/{bob}/suspend", csrf, {"version": v + 1})
    ).status_code == 409
    assert (
        await send(h, "POST", f"{MEMBERS}/{dave}/reinvite", csrf, {"version": 1})
    ).status_code == 409  # stale


# --- Sessions (D8-3: no global revocation) -----------------------------------------------------


async def test_suspension_ends_access_to_that_institute_only(h: Harness) -> None:
    # bob is a member of A and B; his session works in B while his A membership is suspended.
    await sign_in(h, "bob", h.world.tenant_b)
    bob_cookie = h.client.cookies[COOKIE]
    assert (await h.client.get(MEMBERS)).status_code == 200
    await sign_in(h, "dave", campus_id=h.world.campus_a1)
    dave_cookie = h.client.cookies[COOKIE]
    csrf = await sign_in(h, "alice")
    for key in ("bob_a", "dave_a"):
        member = h.world.memberships[key]
        response = await send(
            h, "POST", f"{MEMBERS}/{member}/suspend", csrf, {"version": await version(h, member)}
        )
        assert response.status_code == 200, response.text
    h.client.cookies.clear()
    h.client.cookies.set(COOKIE, dave_cookie)
    session = data(await h.client.get("/api/v1/session"))
    assert session["status"] != "ready"  # no usable institute any more
    assert (await h.client.get("/api/v1/campuses")).status_code == 401
    h.client.cookies.clear()
    h.client.cookies.set(COOKIE, bob_cookie)
    assert (await h.client.get(MEMBERS)).status_code == 200  # institute B still works
    revoked = await h.owner(
        "SELECT count(*) FROM user_sessions WHERE user_id = ANY(:u) AND revoked_at IS NOT NULL "
        "AND revoke_reason <> 'rotated'",
        u=[h.world.users["bob"], h.world.users["dave"]],
    )
    assert revoked[0][0] == 0  # no session was revoked (only sign-in rotations)


# --- Self-protection and the last owner (D8-4) --------------------------------------------------


async def test_nobody_administers_their_own_membership(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    me = h.world.memberships["alice_a"]
    v = await version(h, me)
    calls: list[tuple[str, str, dict[str, Any] | None]] = [
        ("POST", f"{MEMBERS}/{me}/suspend", {"version": v}),
        ("POST", f"{MEMBERS}/{me}/revoke", {"version": v}),
        ("PUT", f"{MEMBERS}/{me}/campus-scope", {"campus_scope": "ALL", "version": v}),
        ("DELETE", f"{MEMBERS}/{me}/roles/{h.world.roles['owner_a']}", None),
    ]
    for method, path, body in calls:
        response = await send(h, method, path, csrf, body)
        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"
        assert await _audit_types(h, response) == ["member.self_action_refused"]
    assert await version(h, me) == v


async def test_the_last_active_owner_is_kept(h: Harness) -> None:
    await _admin(h)
    csrf = await sign_in(h, "gina")
    alice = h.world.memberships["alice_a"]
    v = await version(h, alice)
    for path, body in (
        (f"{MEMBERS}/{alice}/suspend", {"version": v}),
        (f"{MEMBERS}/{alice}/revoke", {"version": v}),
    ):
        response = await send(h, "POST", path, csrf, body)
        assert response.status_code == 409, path
    # An Administrator cannot take the owner role away (no escalation: role.delete) ...
    remove = await send(h, "DELETE", f"{MEMBERS}/{alice}/roles/{h.world.roles['owner_a']}", csrf)
    assert remove.status_code == 403
    # ... and a holder of every tenant permission cannot take it from the last owner.
    await add_role(
        h.factory,
        h.world,
        "superintendent_a",
        tenant_id=h.world.tenant_a,
        permissions=tuple(p.code for p in tenant_permissions()),
    )
    await assign_role(h.factory, h.world, "gina_m", "superintendent_a")
    csrf = await sign_in(h, "gina")
    remove = await send(h, "DELETE", f"{MEMBERS}/{alice}/roles/{h.world.roles['owner_a']}", csrf)
    assert remove.status_code == 409
    assert await version(h, alice) == v
    # With a second active owner, the first can be suspended.
    await add_owner(h, "frank", h.world.tenant_a, "owner_a")
    csrf = await sign_in(h, "gina")
    suspended = await send(h, "POST", f"{MEMBERS}/{alice}/suspend", csrf, {"version": v})
    assert data(suspended)["status"] == "SUSPENDED"


async def test_two_owners_cannot_remove_each_other_concurrently(h: Harness) -> None:
    frank = await add_owner(h, "frank", h.world.tenant_a, "owner_a")
    alice = h.world.memberships["alice_a"]
    transport = ASGITransport(app=h.app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="https://testserver", headers={"Origin": ORIGIN}
    ) as other:
        alice_csrf = await sign_in(h, "alice")
        login = await other.post(
            "/api/v1/auth/login", json={"email": h.world.email("frank"), "password": PASSWORD}
        )
        frank_csrf = login.json()["data"]["csrf_token"]
        statuses: dict[str, int] = {}

        async def alice_suspends_frank() -> None:
            response = await send(
                h, "POST", f"{MEMBERS}/{frank}/suspend", alice_csrf, {"version": 1}
            )
            statuses["alice"] = response.status_code

        async def frank_suspends_alice() -> None:
            response = await other.post(
                f"{MEMBERS}/{alice}/suspend",
                json={"version": await version(h, alice)},
                headers={"X-CSRF-Token": frank_csrf},
            )
            statuses["frank"] = response.status_code

        async with anyio.create_task_group() as group:
            group.start_soon(alice_suspends_frank)
            group.start_soon(frank_suspends_alice)
    assert sorted(statuses.values())[0] == 200
    assert sorted(statuses.values())[1] in {401, 409}  # 401 if the loser was suspended first
    owners = await h.owner(
        "SELECT count(*) FROM tenant_memberships m "
        "JOIN membership_roles mr ON mr.membership_id = m.id JOIN roles r ON r.id = mr.role_id "
        "WHERE m.tenant_id = :t AND m.status = 'ACTIVE' AND r.template_code = 'INSTITUTE_OWNER'",
        t=h.world.tenant_a,
    )
    assert owners[0][0] == 1


# --- Campus scope and roles ----------------------------------------------------------------------


async def test_campus_scope_changes_keep_every_row(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    dave = h.world.memberships["dave_a"]
    path = f"{MEMBERS}/{dave}/campus-scope"
    v = await version(h, dave)
    narrowed = await send(
        h,
        "PUT",
        path,
        csrf,
        {"campus_scope": "SELECTED", "campus_ids": [str(h.world.campus_a1)], "version": v},
    )
    assert data(narrowed)["campus_ids"] == [str(h.world.campus_a1)]
    assert await _audit_types(h, narrowed) == ["member.campus_scope_changed"]
    rows = await h.owner(
        "SELECT campus_id, removed_at IS NOT NULL FROM membership_campuses "
        "WHERE membership_id = :m",
        m=dave,
    )
    assert dict(rows) == {h.world.campus_a1: False, h.world.campus_a2: True}  # never deleted
    widened = await send(
        h,
        "PUT",
        path,
        csrf,
        {
            "campus_scope": "SELECTED",
            "campus_ids": [str(h.world.campus_a1), str(h.world.campus_a2)],
            "version": v + 1,
        },
    )
    assert len(data(widened)["campus_ids"]) == 2
    rows = await h.owner(
        "SELECT count(*), count(removed_at) FROM membership_campuses WHERE membership_id = :m",
        m=dave,
    )
    assert tuple(rows[0]) == (2, 0)
    stale = await send(h, "PUT", path, csrf, {"campus_scope": "ALL", "version": v})
    assert stale.status_code == 409
    foreign = await send(
        h,
        "PUT",
        path,
        csrf,
        {"campus_scope": "SELECTED", "campus_ids": [str(h.world.campus_b1)], "version": v + 2},
    )
    assert foreign.status_code == 422


async def test_roles_are_assigned_and_removed_without_escalation(h: Harness) -> None:
    await _admin(h)
    csrf = await sign_in(h, "gina")
    dave = h.world.memberships["dave_a"]
    assigned = await send(
        h, "POST", f"{MEMBERS}/{dave}/roles", csrf, {"role_id": str(h.world.roles["admin_a"])}
    )
    assert "Administrator" in [r["name"] for r in data(assigned)["roles"]]
    escalation = await send(
        h, "POST", f"{MEMBERS}/{dave}/roles", csrf, {"role_id": str(h.world.roles["owner_a"])}
    )
    assert escalation.status_code == 403
    removed = await send(h, "DELETE", f"{MEMBERS}/{dave}/roles/{h.world.roles['admin_a']}", csrf)
    assert "Administrator" not in [r["name"] for r in data(removed)["roles"]]
    assert await _audit_types(h, removed) == ["membership.role_removed"]
    foreign = await send(
        h,
        "POST",
        f"{MEMBERS}/{h.world.memberships['carol_b']}/roles",
        csrf,
        {"role_id": str(h.world.roles["admin_a"])},
    )
    assert foreign.status_code == 404


async def test_an_invited_new_member_with_a_second_membership_elsewhere(h: Harness) -> None:
    """Another institute's invitation of the same person creates a second, separate membership."""
    csrf = await sign_in(h, "carol")  # owner of B
    email = _email(h, "engine")
    first = data(
        await send(
            h, "POST", f"{MEMBERS}/invitations", csrf, {"email": email, "display_name": "E"}
        ),
        201,
    )
    assert first["account"] == "new"
    csrf = await sign_in(h, "alice")
    second = data(
        await send(
            h, "POST", f"{MEMBERS}/invitations", csrf, {"email": email, "display_name": "E"}
        ),
        201,
    )
    assert second["account"] == "existing"  # the INVITED identity is reused
    tenants = await h.owner(
        "SELECT count(DISTINCT m.tenant_id) FROM tenant_memberships m JOIN users u "
        "ON u.id = m.user_id WHERE u.email = :e",
        e=email,
    )
    assert tenants[0][0] == 2
    assert first["member"]["id"] not in str(
        (await h.client.get(MEMBERS, params={"limit": 100})).json()
    )


async def test_membership_helpers_are_tenant_bound(h: Harness) -> None:
    """A membership created for tenant B is never visible or changeable from A."""
    async with system_context(h.factory) as db:
        await add_user(db, h.world, "hari")
    m = await add_membership(h.factory, h.world, "hari_b", user="hari", tenant_id=h.world.tenant_b)
    await assign_role(h.factory, h.world, "hari_b", "admin_b")
    csrf = await sign_in(h, "alice")
    for method, path, body in (
        ("POST", f"{MEMBERS}/{m}/suspend", {"version": 1}),
        ("POST", f"{MEMBERS}/{m}/revoke", {"version": 1}),
        ("PUT", f"{MEMBERS}/{m}/campus-scope", {"campus_scope": "ALL", "version": 1}),
        ("DELETE", f"{MEMBERS}/{m}/roles/{h.world.roles['admin_b']}", None),
    ):
        response = await send(h, method, path, csrf, body)
        assert response.status_code == 404, path
    assert await version(h, m) == 1
