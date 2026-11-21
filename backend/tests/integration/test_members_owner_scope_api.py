"""Owner campus scope and safe re-invitation over HTTP (ADR-0023).

The T01-08 world (see ``test_members_api``): ``alice`` owns institute A with
all campuses; ``bob`` is an Administrator of A (campus A1 only) and of B;
``carol`` owns B; ``dave`` holds a custom campus role in A (A1 and A2). Tests
add the members they need. Every row here belongs to the test world.
"""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import anyio
import pytest
from conftest import DatabaseUnderTest
from httpx import ASGITransport, AsyncClient
from identity_support import ORIGIN, PASSWORD, Harness, auth_harness
from tenant_admin_support import MEMBERS, add_owner, data, send, sign_in, version

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

ACCEPT = "/api/v1/auth/invitations/accept"
OWNER_SCOPE = "owner_requires_all_campuses"


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        yield harness


def _email(h: Harness, name: str) -> str:
    return f"{name}.{uuid.uuid7().hex[-6:]}.{h.world.suffix}@westernmaritime.example"


def _token(h: Harness) -> str:
    return str(h.email.sent[-1].body.split("#token=")[1].split()[0])


def _owner_scope_refusal(response: Any, field: str) -> None:
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert [(d["field"], d["code"]) for d in error["details"]] == [(field, OWNER_SCOPE)]


async def _scope(h: Harness, membership: uuid.UUID) -> tuple[str, int]:
    rows = await h.owner(
        "SELECT campus_scope, version FROM tenant_memberships WHERE id = :m", m=membership
    )
    return (rows[0][0], rows[0][1])


async def _role_ids(h: Harness, membership: uuid.UUID) -> set[uuid.UUID]:
    rows = await h.owner(
        "SELECT role_id FROM membership_roles WHERE membership_id = :m", m=membership
    )
    return {row[0] for row in rows}


def _limit(campus: uuid.UUID, v: int) -> dict[str, Any]:
    return {"campus_scope": "SELECTED", "campus_ids": [str(campus)], "version": v}


# --- Decision A: owners keep all campuses -----------------------------------------------------


async def test_the_last_owner_cannot_be_limited_to_selected_campuses(h: Harness) -> None:
    await add_owner(h, "gina", h.world.tenant_a, "admin_a")  # Administrator, all campuses
    csrf = await sign_in(h, "gina")
    alice = h.world.memberships["alice_a"]
    before = await _scope(h, alice)
    response = await send(
        h, "PUT", f"{MEMBERS}/{alice}/campus-scope", csrf, _limit(h.world.campus_a1, before[1])
    )
    _owner_scope_refusal(response, "campus_scope")
    assert await h.audit(response) == []
    assert await _scope(h, alice) == before


async def test_an_owner_who_is_not_the_last_cannot_be_limited_either(h: Harness) -> None:
    frank = await add_owner(h, "frank", h.world.tenant_a, "owner_a")
    await add_owner(h, "gina", h.world.tenant_a, "admin_a")
    before = await _scope(h, frank)
    for user in ("gina", "alice"):  # an Administrator, and another owner
        csrf = await sign_in(h, user)
        response = await send(
            h, "PUT", f"{MEMBERS}/{frank}/campus-scope", csrf, _limit(h.world.campus_a2, before[1])
        )
        _owner_scope_refusal(response, "campus_scope")
    assert await _scope(h, frank) == before


async def test_self_protection_still_comes_first(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    alice = h.world.memberships["alice_a"]
    v = await version(h, alice)
    response = await send(
        h, "PUT", f"{MEMBERS}/{alice}/campus-scope", csrf, _limit(h.world.campus_a1, v)
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"
    assert [e.event_type for e in await h.audit(response)] == ["member.self_action_refused"]


async def test_members_without_the_owner_role_can_still_be_limited(h: Harness) -> None:
    await add_owner(h, "gina", h.world.tenant_a, "admin_a")
    hana = await add_owner(h, "hana", h.world.tenant_a, "admin_a")
    csrf = await sign_in(h, "gina")
    v = await version(h, hana)
    limited = await send(
        h, "PUT", f"{MEMBERS}/{hana}/campus-scope", csrf, _limit(h.world.campus_a1, v)
    )
    assert data(limited)["campus_scope"] == "SELECTED"
    assert [e.event_type for e in await h.audit(limited)] == ["member.campus_scope_changed"]


async def test_the_owner_role_is_only_given_with_all_campus_access(h: Harness) -> None:
    hana = await add_owner(h, "hana", h.world.tenant_a, "admin_a")
    await add_owner(h, "gina", h.world.tenant_a, "admin_a")
    dave = h.world.memberships["dave_a"]  # campuses A1 and A2
    owner_role = {"role_id": str(h.world.roles["owner_a"])}
    # An Administrator cannot grant the owner role at all: no escalation stays first.
    csrf = await sign_in(h, "gina")
    escalation = await send(h, "POST", f"{MEMBERS}/{dave}/roles", csrf, owner_role)
    assert escalation.status_code == 403
    # The owner can, but not to a campus-limited member: no silent widening.
    csrf = await sign_in(h, "alice")
    before = (await _role_ids(h, dave), await _scope(h, dave))
    refused = await send(h, "POST", f"{MEMBERS}/{dave}/roles", csrf, owner_role)
    _owner_scope_refusal(refused, "role_id")
    assert await h.audit(refused) == []
    assert (await _role_ids(h, dave), await _scope(h, dave)) == before
    # A member with all campuses can be made owner, and the role is marked as such.
    granted = data(await send(h, "POST", f"{MEMBERS}/{hana}/roles", csrf, owner_role))
    owner = next(r for r in granted["roles"] if r["id"] == str(h.world.roles["owner_a"]))
    assert owner["is_owner"] is True
    assert all(not r["is_owner"] for r in granted["roles"] if r is not owner)
    assert granted["is_owner"] is True
    assert data(await h.client.get(f"{MEMBERS}/{dave}"))["is_owner"] is False
    roles = data(await h.client.get("/api/v1/roles"))
    assert [r["name"] for r in roles if r["is_owner"]] == ["Institute owner"]


async def test_an_owner_invitation_with_selected_campuses_leaves_nothing_behind(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    email = _email(h, "master")
    sent = len(h.email.sent)
    refused = await send(
        h,
        "POST",
        f"{MEMBERS}/invitations",
        csrf,
        {
            "email": email,
            "display_name": "Captain Arjun Nair",
            "role_ids": [str(h.world.roles["owner_a"])],
            "campus_scope": "SELECTED",
            "campus_ids": [str(h.world.campus_a1)],
        },
    )
    _owner_scope_refusal(refused, "campus_scope")
    assert (await h.owner("SELECT count(*) FROM users WHERE email = :e", e=email))[0][0] == 0
    assert await h.audit(refused) == []
    assert len(h.email.sent) == sent
    # With all campuses, the same invitation is accepted.
    invited = data(
        await send(
            h,
            "POST",
            f"{MEMBERS}/invitations",
            csrf,
            {
                "email": email,
                "display_name": "Captain Arjun Nair",
                "role_ids": [str(h.world.roles["owner_a"])],
            },
        ),
        201,
    )
    assert [(r["name"], r["is_owner"]) for r in invited["member"]["roles"]] == [
        ("Institute owner", True)
    ]


async def test_only_owners_with_all_campuses_count_for_the_last_owner_rule(h: Harness) -> None:
    # A campus-limited owner can no longer be created through the API; set one up
    # directly in the test world to prove that such an owner is not counted.
    frank = await add_owner(h, "frank", h.world.tenant_a, "owner_a")
    await h.owner("UPDATE tenant_memberships SET campus_scope = 'SELECTED' WHERE id = :m", m=frank)
    await add_owner(h, "gina", h.world.tenant_a, "admin_a")
    csrf = await sign_in(h, "gina")
    alice = h.world.memberships["alice_a"]
    v = await version(h, alice)
    for path in (f"{MEMBERS}/{alice}/suspend", f"{MEMBERS}/{alice}/revoke"):
        response = await send(h, "POST", path, csrf, {"version": v})
        assert response.status_code == 409, path
    assert await version(h, alice) == v


async def _race_owner_role_and_limit(h: Harness, target: uuid.UUID) -> dict[str, int]:
    """alice gives ``target`` the owner role while gina limits it to campus A1, at once."""
    v = await version(h, target)
    transport = ASGITransport(app=h.app, raise_app_exceptions=False)
    statuses: dict[str, int] = {}
    async with AsyncClient(
        transport=transport, base_url="https://testserver", headers={"Origin": ORIGIN}
    ) as other:
        alice_csrf = await sign_in(h, "alice")
        login = await other.post(
            "/api/v1/auth/login", json={"email": h.world.email("gina"), "password": PASSWORD}
        )
        gina_csrf = login.json()["data"]["csrf_token"]

        async def alice_makes_owner() -> None:
            response = await send(
                h,
                "POST",
                f"{MEMBERS}/{target}/roles",
                alice_csrf,
                {"role_id": str(h.world.roles["owner_a"])},
            )
            statuses["owner"] = response.status_code

        async def gina_limits() -> None:
            response = await other.put(
                f"{MEMBERS}/{target}/campus-scope",
                json=_limit(h.world.campus_a1, v),
                headers={"X-CSRF-Token": gina_csrf},
            )
            statuses["limit"] = response.status_code

        async with anyio.create_task_group() as group:
            group.start_soon(alice_makes_owner)
            group.start_soon(gina_limits)
    return statuses


async def test_limiting_and_making_owner_at_once_never_leaves_a_limited_owner(h: Harness) -> None:
    await add_owner(h, "gina", h.world.tenant_a, "admin_a")
    for name in ("hana", "ivan", "jaya"):  # a few races; the outcome order may differ
        target = await add_owner(h, name, h.world.tenant_a, "admin_a")
        statuses = await _race_owner_role_and_limit(h, target)
        assert sorted(statuses.values()) == [200, 422], statuses
        is_owner = h.world.roles["owner_a"] in await _role_ids(h, target)
        scope, _ = await _scope(h, target)
        assert not (is_owner and scope == "SELECTED"), name
        assert is_owner == (statuses["owner"] == 200)


# --- Decision B: re-invitation clears roles ----------------------------------------------------


async def _removed_member(h: Harness, csrf: str) -> tuple[str, int]:
    """An invited Administrator on campus A1, then removed; returns its ID and version."""
    invited = data(
        await send(
            h,
            "POST",
            f"{MEMBERS}/invitations",
            csrf,
            {
                "email": _email(h, "cadet"),
                "display_name": "Deck Cadet Rohan Pillai",
                "role_ids": [str(h.world.roles["admin_a"])],
                "campus_scope": "SELECTED",
                "campus_ids": [str(h.world.campus_a1)],
            },
        ),
        201,
    )["member"]
    revoked = data(await send(h, "POST", f"{MEMBERS}/{invited['id']}/revoke", csrf, {"version": 1}))
    assert revoked["status"] == "REVOKED"
    assert [r["name"] for r in revoked["roles"]] == ["Administrator"]  # kept until re-invitation
    return invited["id"], revoked["version"]


async def test_reinvitation_clears_every_role_and_keeps_the_campus_scope(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    member_id, v = await _removed_member(h, csrf)
    reinvited = await send(h, "POST", f"{MEMBERS}/{member_id}/reinvite", csrf, {"version": v})
    body = data(reinvited)
    assert (body["status"], body["roles"], body["version"]) == ("INVITED", [], v + 1)
    assert (body["campus_scope"], body["campus_ids"]) == ("SELECTED", [str(h.world.campus_a1)])
    assert await _role_ids(h, uuid.UUID(member_id)) == set()
    (event,) = await h.audit(reinvited)
    assert event.event_type == "member.reinvited"
    assert event.metadata == {
        "revoked": 0,  # the removal already revoked the first invitation
        "roles_cleared": 1,
        "cleared_role_ids": [str(h.world.roles["admin_a"])],
        "cleared_role_names": ["Administrator"],
    }
    assert (event.tenant_id, event.principal_id) == (h.world.tenant_a, h.world.users["alice"])
    assert (event.target_type, event.target_id) == ("tenant_membership", uuid.UUID(member_id))
    assert _token(h) not in str(event)

    # Accepting the new invitation gives an ACTIVE member with no inherited role.
    accept = await h.client.post(
        ACCEPT, json={"token": _token(h), "display_name": "Rohan Pillai", "password": PASSWORD}
    )
    assert accept.status_code == 204, accept.text
    await sign_in(h, "alice")
    joined = data(await h.client.get(f"{MEMBERS}/{member_id}"))
    assert (joined["status"], joined["roles"]) == ("ACTIVE", [])


async def test_an_administrator_reinvites_a_removed_owner_without_the_owner_role(
    h: Harness,
) -> None:
    frank = await add_owner(h, "frank", h.world.tenant_a, "owner_a")
    await add_owner(h, "gina", h.world.tenant_a, "admin_a")  # cannot grant the owner role
    csrf = await sign_in(h, "gina")
    v = await version(h, frank)
    assert data(await send(h, "POST", f"{MEMBERS}/{frank}/revoke", csrf, {"version": v}))
    reinvited = data(await send(h, "POST", f"{MEMBERS}/{frank}/reinvite", csrf, {"version": v + 1}))
    assert reinvited["roles"] == []
    assert await _role_ids(h, frank) == set()


async def test_a_refused_reinvitation_keeps_the_roles(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    member_id, v = await _removed_member(h, csrf)
    member = uuid.UUID(member_id)
    held = {h.world.roles["admin_a"]}
    stale = await send(h, "POST", f"{MEMBERS}/{member_id}/reinvite", csrf, {"version": v - 1})
    assert stale.status_code == 409
    assert await _role_ids(h, member) == held
    await h.owner(
        "UPDATE users SET status = 'DISABLED' WHERE id = "
        "(SELECT user_id FROM tenant_memberships WHERE id = :m)",
        m=member,
    )
    disabled = await send(h, "POST", f"{MEMBERS}/{member_id}/reinvite", csrf, {"version": v})
    assert disabled.status_code == 409
    assert await _role_ids(h, member) == held
    assert await h.audit(stale) == await h.audit(disabled) == []


async def test_reinstatement_keeps_the_roles(h: Harness) -> None:
    hana = await add_owner(h, "hana", h.world.tenant_a, "admin_a")
    csrf = await sign_in(h, "alice")
    v = await version(h, hana)
    await send(h, "POST", f"{MEMBERS}/{hana}/suspend", csrf, {"version": v})
    reinstated = data(
        await send(h, "POST", f"{MEMBERS}/{hana}/reinstate", csrf, {"version": v + 1})
    )
    assert [r["name"] for r in reinstated["roles"]] == ["Administrator"]
    assert await _role_ids(h, hana) == {h.world.roles["admin_a"]}


async def test_another_institutes_member_is_not_found(h: Harness) -> None:
    csrf = await sign_in(h, "alice")
    carol = h.world.memberships["carol_b"]
    roles_before = await _role_ids(h, carol)
    for method, path, body in (
        ("POST", f"{MEMBERS}/{carol}/reinvite", {"version": 1}),
        ("POST", f"{MEMBERS}/{carol}/reinstate", {"version": 1}),
        ("POST", f"{MEMBERS}/{carol}/invitation/resend", None),
        ("PUT", f"{MEMBERS}/{carol}/campus-scope", _limit(h.world.campus_a1, 1)),
        ("POST", f"{MEMBERS}/{carol}/roles", {"role_id": str(h.world.roles["owner_a"])}),
    ):
        response = await send(h, method, path, csrf, body)
        assert response.status_code == 404, path
    assert await _role_ids(h, carol) == roles_before
