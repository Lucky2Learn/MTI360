"""Custom roles and role assignment through the access service (T01-05; D-B2, ADR-0011 §5).

The service is the foundation of tenant role administration (its API arrives
in T01-08). Each operation runs as a real member: the trusted context carries
the member's effective permissions, the transaction runs under RLS, and audit
events are read back from the database.
"""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from typing import Any

import pytest
from conftest import DatabaseUnderTest
from identity_support import Harness, add_membership, add_user, auth_harness
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit.security import security_event_scope
from app.core.context import Realm, RequestContext, context_scope
from app.core.db.session import context_transaction
from app.core.errors import (
    AuthenticationRequiredError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from app.core.tenancy import system_context
from app.modules.access import service

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        yield harness


@dataclass
class Actor:
    harness: Harness
    user: str
    membership: str
    tenant_id: uuid.UUID
    all_campuses: bool = True

    async def context(self) -> RequestContext:
        base = RequestContext(
            realm=Realm.TENANT,
            request_id=uuid.uuid7(),
            principal_id=self.harness.world.users[self.user],
            tenant_id=self.tenant_id,
        )
        async with context_transaction(self.harness.factory, base) as db:
            access = await service.membership_access(
                db,
                tenant_id=self.tenant_id,
                membership_id=self.harness.world.memberships[self.membership],
                all_campuses=self.all_campuses,
            )
        return replace(base, permissions=access.permissions, all_campuses=self.all_campuses)

    @asynccontextmanager
    async def acting(
        self, context: RequestContext | None = None
    ) -> AsyncIterator[tuple[AsyncSession, RequestContext]]:
        """One request: bound context, security-event scope, one transaction."""
        context = context or await self.context()
        with context_scope(context):
            async with (
                security_event_scope(self.harness.factory, context),
                context_transaction(self.harness.factory, context) as db,
            ):
                yield db, context

    async def run(
        self, operation: Callable[[AsyncSession], Awaitable[Any]]
    ) -> tuple[Any, uuid.UUID]:
        async with self.acting() as (db, context):
            return await operation(db), context.request_id

    async def _attempt(
        self, context: RequestContext, operation: Callable[[AsyncSession], Awaitable[Any]]
    ) -> None:
        async with self.acting(context) as (db, _):
            await operation(db)

    async def fails(
        self, error: type[Exception], operation: Callable[[AsyncSession], Awaitable[Any]]
    ) -> uuid.UUID:
        context = await self.context()
        with pytest.raises(error):
            await self._attempt(context, operation)
        return context.request_id


def alice(h: Harness) -> Actor:
    return Actor(h, "alice", "alice_a", h.world.tenant_a)


def carol(h: Harness) -> Actor:
    return Actor(h, "carol", "carol_b", h.world.tenant_b)


def bob_in_b(h: Harness) -> Actor:
    return Actor(h, "bob", "bob_b", h.world.tenant_b)


async def audit(h: Harness, request_id: uuid.UUID) -> list[tuple[str, Any]]:
    rows = await h.owner(
        "SELECT event_type, metadata FROM audit_events WHERE request_id = :r ORDER BY id",
        r=request_id,
    )
    return [(row[0], row[1]) for row in rows]


async def role_codes(h: Harness, role_id: uuid.UUID) -> set[str]:
    rows = await h.owner(
        "SELECT permission_code FROM role_permissions WHERE role_id = :r", r=role_id
    )
    return {row[0] for row in rows}


async def effective(h: Harness, membership: str, tenant_id: uuid.UUID) -> set[str]:
    async with system_context(h.factory, tenant_id=tenant_id) as db:
        access = await service.membership_access(
            db,
            tenant_id=tenant_id,
            membership_id=h.world.memberships[membership],
            all_campuses=True,
        )
    return set(access.permissions)


async def new_member(h: Harness, name: str) -> str:
    """An all-campus member of institute A without any role."""
    async with system_context(h.factory) as db:
        await add_user(db, h.world, name)
    key = f"{name}_a"
    await add_membership(h.factory, h.world, key, user=name, tenant_id=h.world.tenant_a)
    return key


# --- Custom roles ----------------------------------------------------------------------------


async def test_an_owner_creates_updates_and_deletes_a_custom_role(h: Harness) -> None:
    owner = alice(h)
    name = f"Placement officer {h.world.suffix}"
    role_id, created = await owner.run(
        lambda db: service.create_role(
            db,
            name=f"  {name} ",
            description="Placements",
            permissions=["member.read", "campus.read"],
        )
    )
    assert await role_codes(h, role_id) == {"member.read", "campus.read"}
    assert await audit(h, created) == [
        ("role.created", {"name": name, "permission_count": 2}),
    ]

    _, updated = await owner.run(
        lambda db: service.update_role(
            db,
            role_id,
            expected_version=1,
            name=f"{name} (sea)",
            permissions=["member.read", "role.read"],
        )
    )
    assert await role_codes(h, role_id) == {"member.read", "role.read"}
    assert await audit(h, updated) == [
        (
            "role.updated",
            {"name": f"{name} (sea)", "previous_name": name, "description_changed": False},
        ),
        (
            "role.permissions_changed",
            {
                "added": ["role.read"],
                "removed": ["campus.read"],
                "added_count": 1,
                "removed_count": 1,
            },
        ),
    ]
    # A stale version is a conflict, and nothing changes.
    await owner.fails(
        ConflictError,
        lambda db: service.update_role(db, role_id, expected_version=1, name="Stale"),
    )
    _, deleted = await owner.run(lambda db: service.delete_role(db, role_id, expected_version=2))
    assert await role_codes(h, role_id) == set()
    assert await h.owner("SELECT id FROM roles WHERE id = :r", r=role_id) == []
    assert await audit(h, deleted) == [("role.deleted", {"name": f"{name} (sea)"})]


@pytest.mark.parametrize(
    ("permissions", "name"),
    [
        (["campus.archive"], "Unknown permission"),
        (["tenant.read"], "Platform permission"),
        (["campus.*"], "Wildcard"),
        (["*"], "Everything"),
        (["campus.read"], "   "),
        (["campus.read"], "x" * 101),
    ],
)
async def test_invalid_roles_are_rejected(h: Harness, permissions: list[str], name: str) -> None:
    await alice(h).fails(
        ValidationFailedError,
        lambda db: service.create_role(db, name=name, description=None, permissions=permissions),
    )


async def test_role_names_are_unique_per_tenant_ignoring_case(h: Harness) -> None:
    await alice(h).fails(
        ConflictError,
        lambda db: service.create_role(
            db, name="INSTITUTE OWNER", description=None, permissions=[]
        ),
    )
    # The same name in another institute is fine.
    role_id, _ = await carol(h).run(
        lambda db: service.create_role(
            db, name=f"Coordinator A {h.world.suffix}", description=None, permissions=[]
        )
    )
    assert role_id


async def test_an_assigned_custom_role_cannot_be_deleted(h: Harness) -> None:
    await alice(h).fails(
        ConflictError,
        lambda db: service.delete_role(db, h.world.roles["coordinator_a"], expected_version=1),
    )


# --- D-B2 through the service ----------------------------------------------------------------


@pytest.mark.parametrize("role", ["owner_a", "admin_a"])
async def test_system_roles_cannot_be_changed_or_deleted(h: Harness, role: str) -> None:
    owner = alice(h)
    role_id = h.world.roles[role]
    before = await role_codes(h, role_id)
    renamed = await owner.fails(
        PermissionDeniedError,
        lambda db: service.update_role(db, role_id, expected_version=1, name="Captain"),
    )
    regranted = await owner.fails(
        PermissionDeniedError,
        lambda db: service.update_role(db, role_id, expected_version=1, permissions=[]),
    )
    deleted = await owner.fails(
        PermissionDeniedError,
        lambda db: service.delete_role(db, role_id, expected_version=1),
    )
    assert await role_codes(h, role_id) == before
    for request_id, action in ((renamed, "update"), (regranted, "update"), (deleted, "delete")):
        assert await audit(h, request_id) == [("role.system_change_rejected", {"action": action})]


# --- Authorization and no escalation (ADR-0011 §5) -------------------------------------------


async def test_role_administration_requires_its_permissions(h: Harness) -> None:
    # dave: coordinator (campus permissions only).
    dave = Actor(h, "dave", "dave_a", h.world.tenant_a, all_campuses=False)
    await dave.fails(
        PermissionDeniedError,
        lambda db: service.create_role(db, name="Mine", description=None, permissions=[]),
    )
    # bob in A: Administrator, but campus-restricted: tenant-wide role.assign is not his (D-B1).
    bob_a = Actor(h, "bob", "bob_a", h.world.tenant_a, all_campuses=False)
    await bob_a.fails(
        PermissionDeniedError,
        lambda db: service.assign_role(
            db, h.world.memberships["dave_a"], h.world.roles["coordinator_a"]
        ),
    )
    # Administrators cannot delete roles (no role.delete).
    role_id, _ = await carol(h).run(
        lambda db: service.create_role(
            db, name=f"Tmp {h.world.suffix}", description=None, permissions=[]
        )
    )
    await bob_in_b(h).fails(
        PermissionDeniedError, lambda db: service.delete_role(db, role_id, expected_version=1)
    )


async def test_nobody_grants_or_takes_away_what_they_do_not_hold(h: Harness) -> None:
    admin = bob_in_b(h)  # Administrator in B: everything but role.delete
    await admin.fails(
        PermissionDeniedError,
        lambda db: service.create_role(
            db, name="Deleter", description=None, permissions=["role.delete"]
        ),
    )
    # The owner role holds role.delete: an administrator can neither give it ...
    await admin.fails(
        PermissionDeniedError,
        lambda db: service.assign_role(db, h.world.memberships["bob_b"], h.world.roles["owner_b"]),
    )
    # ... nor take it away from the owner.
    await admin.fails(
        PermissionDeniedError,
        lambda db: service.remove_role(
            db, h.world.memberships["carol_b"], h.world.roles["owner_b"]
        ),
    )
    # Within their own permissions they can.
    role_id, _ = await admin.run(
        lambda db: service.create_role(
            db, name=f"Examiner {h.world.suffix}", description=None, permissions=["member.read"]
        )
    )
    await admin.run(lambda db: service.assign_role(db, h.world.memberships["carol_b"], role_id))
    await admin.fails(
        PermissionDeniedError,
        lambda db: service.update_role(
            db, role_id, expected_version=1, permissions=["member.read", "role.delete"]
        ),
    )


async def test_a_context_without_a_principal_is_401(h: Harness) -> None:
    context = RequestContext(
        realm=Realm.TENANT, request_id=uuid.uuid7(), tenant_id=h.world.tenant_a
    )
    with context_scope(context), pytest.raises(AuthenticationRequiredError):
        async with context_transaction(h.factory, context) as db:
            await service.create_role(db, name="Ghost", description=None, permissions=[])


# --- Assignments: union, removal, isolation --------------------------------------------------


async def test_effective_permissions_are_the_union_of_the_roles(h: Harness) -> None:
    owner = alice(h)
    member = await new_member(h, f"frank_{h.world.suffix}")
    membership = h.world.memberships[member]

    async def make(name: str, codes: list[str]) -> uuid.UUID:
        role_id, _ = await owner.run(
            lambda db: service.create_role(
                db, name=f"{name} {h.world.suffix}", description=None, permissions=codes
            )
        )
        return uuid.UUID(str(role_id))

    deck = await make("Deck", ["campus.read", "member.read"])
    engine = await make("Engine", ["member.read", "audit.read"])
    assert await effective(h, member, h.world.tenant_a) == set()

    _, assigned = await owner.run(lambda db: service.assign_role(db, membership, deck))
    assert await effective(h, member, h.world.tenant_a) == {"campus.read", "member.read"}
    await owner.run(lambda db: service.assign_role(db, membership, engine))
    assert await effective(h, member, h.world.tenant_a) == {
        "campus.read",
        "member.read",
        "audit.read",
    }
    # Removing one role keeps what the other grants (member.read is in both).
    _, removed = await owner.run(lambda db: service.remove_role(db, membership, deck))
    assert await effective(h, member, h.world.tenant_a) == {"member.read", "audit.read"}

    assert await audit(h, assigned) == [
        (
            "membership.role_assigned",
            {"role_id": str(deck), "role_name": f"Deck {h.world.suffix}", "is_system": False},
        )
    ]
    assert [event for event, _ in await audit(h, removed)] == ["membership.role_removed"]
    await owner.fails(ConflictError, lambda db: service.assign_role(db, membership, engine))
    await owner.fails(NotFoundError, lambda db: service.remove_role(db, membership, deck))


async def test_another_tenants_roles_and_memberships_are_not_found(h: Harness) -> None:
    owner = alice(h)
    cases: list[Callable[[AsyncSession], Awaitable[Any]]] = [
        lambda db: service.update_role(db, h.world.roles["owner_b"], expected_version=1, name="x"),
        lambda db: service.delete_role(db, h.world.roles["admin_b"], expected_version=1),
        lambda db: service.assign_role(
            db, h.world.memberships["carol_b"], h.world.roles["coordinator_a"]
        ),
        lambda db: service.assign_role(
            db, h.world.memberships["alice_a"], h.world.roles["admin_b"]
        ),
        lambda db: service.remove_role(
            db, h.world.memberships["carol_b"], h.world.roles["owner_b"]
        ),
        lambda db: service.update_role(db, uuid.uuid7(), expected_version=1, name="x"),
    ]
    for operation in cases:
        await owner.fails(NotFoundError, operation)
    assert await role_codes(h, h.world.roles["owner_b"])
