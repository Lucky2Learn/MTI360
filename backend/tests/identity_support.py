"""Shared T01-04 test data: a two-institute world built through the system realm.

Everything is created with ``system_context`` as the application role (the
system realm is the only one allowed to create identities), with unique names
and emails per world, because the shared test database keeps every row.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.tenancy import system_context
from app.modules.identity.models import (
    MembershipCampus,
    PasswordResetToken,
    TenantMembership,
    User,
    UserCredential,
    UserInvitation,
    UserSession,
)
from app.modules.identity.passwords import PasswordHasher
from app.modules.identity.tokens import TokenPurpose, new_token, token_hash
from app.modules.institute.models import Campus
from app.modules.tenants.models import Tenant

TEST_SESSION_SECRET = "mti360-test-session-secret-0123456789abcdef"
PASSWORD = "Bosun's whistle at 0600 hours"
FAST_HASHER = PasswordHasher(time_cost=1, memory_cost_kib=8, parallelism=1)
_HASH = FAST_HASHER.hash_sync(PASSWORD)


def now() -> datetime:
    return datetime.now(UTC)


@dataclass
class World:
    suffix: str
    tenant_a: uuid.UUID
    tenant_b: uuid.UUID
    campus_a1: uuid.UUID
    campus_a2: uuid.UUID
    campus_b1: uuid.UUID
    users: dict[str, uuid.UUID] = field(default_factory=dict)
    emails: dict[str, str] = field(default_factory=dict)
    memberships: dict[str, uuid.UUID] = field(default_factory=dict)

    def email(self, name: str) -> str:
        return self.emails[name]


def _table(model: Any) -> Any:
    return model.__table__


async def add_user(
    db: AsyncSession,
    world: World,
    name: str,
    *,
    status: str = "ACTIVE",
    credential: bool = True,
    password_hash: str = _HASH,
) -> uuid.UUID:
    user_id = uuid.uuid7()
    email = f"{name}.{world.suffix}@westernmaritime.example"
    await db.execute(
        insert(_table(User)).values(
            id=user_id,
            email=email,
            display_name=name.replace("_", " ").title(),
            status=status,
            version=1,
        )
    )
    if credential:
        await db.execute(
            insert(_table(UserCredential)).values(
                id=uuid.uuid7(),
                user_id=user_id,
                password_hash=password_hash,
                password_changed_at=now(),
            )
        )
    world.users[name] = user_id
    world.emails[name] = email
    return user_id


async def add_membership(
    factory: async_sessionmaker[AsyncSession],
    world: World,
    key: str,
    *,
    user: str,
    tenant_id: uuid.UUID,
    status: str = "ACTIVE",
    scope: str = "ALL",
    campuses: tuple[uuid.UUID, ...] = (),
) -> uuid.UUID:
    membership_id = uuid.uuid7()
    async with system_context(factory, tenant_id=tenant_id) as db:
        await db.execute(
            insert(_table(TenantMembership)).values(
                id=membership_id,
                tenant_id=tenant_id,
                user_id=world.users[user],
                status=status,
                campus_scope=scope,
                joined_at=now() if status == "ACTIVE" else None,
                version=1,
            )
        )
        for campus_id in campuses:
            await db.execute(
                insert(_table(MembershipCampus)).values(
                    id=uuid.uuid7(),
                    tenant_id=tenant_id,
                    membership_id=membership_id,
                    campus_id=campus_id,
                )
            )
    world.memberships[key] = membership_id
    return membership_id


async def build_world(factory: async_sessionmaker[AsyncSession]) -> World:
    """Institutes A (two campuses) and B (one campus) and these people:

    * ``alice`` — A only, all campuses;
    * ``bob`` — A (selected: A1) and B (all campuses);
    * ``carol`` — B only;
    * ``dave`` — A, selected campuses A1 and A2 (campus choice required);
    * ``erin`` — no membership.
    """
    suffix = uuid.uuid7().hex[-8:]
    async with system_context(factory) as db:
        tenant_a = Tenant(name=f"Western Maritime Academy {suffix}", status="ACTIVE")
        tenant_b = Tenant(name=f"Konkan Nautical Institute {suffix}", status="TRIAL")
        db.add_all([tenant_a, tenant_b])
    campuses: dict[str, uuid.UUID] = {}
    for tenant, codes in ((tenant_a, ("MUM", "PUNE")), (tenant_b, ("GOA",))):
        async with system_context(factory, tenant_id=tenant.id) as db:
            for code in codes:
                campus = Campus(tenant_id=tenant.id, name=f"{code.title()} Campus", code=code)
                db.add(campus)
                await db.flush()
                campuses[code] = campus.id
    world = World(
        suffix, tenant_a.id, tenant_b.id, campuses["MUM"], campuses["PUNE"], campuses["GOA"]
    )
    async with system_context(factory) as db:
        for name in ("alice", "bob", "carol", "dave", "erin"):
            await add_user(db, world, name)
    await add_membership(factory, world, "alice_a", user="alice", tenant_id=world.tenant_a)
    await add_membership(
        factory,
        world,
        "bob_a",
        user="bob",
        tenant_id=world.tenant_a,
        scope="SELECTED",
        campuses=(world.campus_a1,),
    )
    await add_membership(factory, world, "bob_b", user="bob", tenant_id=world.tenant_b)
    await add_membership(factory, world, "carol_b", user="carol", tenant_id=world.tenant_b)
    await add_membership(
        factory,
        world,
        "dave_a",
        user="dave",
        tenant_id=world.tenant_a,
        scope="SELECTED",
        campuses=(world.campus_a1, world.campus_a2),
    )
    return world


async def add_session(
    factory: async_sessionmaker[AsyncSession],
    world: World,
    user: str,
    *,
    tenant_id: uuid.UUID | None = None,
    campus_id: uuid.UUID | None = None,
    secret: str = TEST_SESSION_SECRET,
    idle: timedelta = timedelta(minutes=30),
) -> tuple[uuid.UUID, str]:
    token = new_token()
    session_id = uuid.uuid7()
    moment = now()
    async with system_context(factory) as db:
        await db.execute(
            insert(_table(UserSession)).values(
                id=session_id,
                token_hash=token_hash(secret, TokenPurpose.SESSION, token),
                user_id=world.users[user],
                realm="tenant",
                active_tenant_id=tenant_id,
                active_campus_id=campus_id,
                created_at=moment - timedelta(hours=1),
                last_seen_at=moment - timedelta(hours=1),
                idle_expires_at=moment + idle,
                absolute_expires_at=moment + timedelta(hours=8),
            )
        )
    return session_id, token


async def add_reset_token(
    factory: async_sessionmaker[AsyncSession],
    world: World,
    user: str,
    *,
    expires_in: timedelta = timedelta(minutes=30),
    secret: str = TEST_SESSION_SECRET,
) -> tuple[uuid.UUID, str]:
    token = new_token()
    token_id = uuid.uuid7()
    async with system_context(factory) as db:
        await db.execute(
            insert(_table(PasswordResetToken)).values(
                id=token_id,
                user_id=world.users[user],
                token_hash=token_hash(secret, TokenPurpose.PASSWORD_RESET, token),
                created_at=now() - timedelta(minutes=1),
                expires_at=now() + expires_in,
            )
        )
    return token_id, token


async def add_invitation(
    factory: async_sessionmaker[AsyncSession],
    world: World,
    user: str,
    *,
    tenant_id: uuid.UUID,
    new_account: bool,
    expires_in: timedelta = timedelta(days=7),
    secret: str = TEST_SESSION_SECRET,
) -> tuple[uuid.UUID, str]:
    """An INVITED membership for ``user`` (created if needed) and its invitation."""
    if user not in world.users:
        async with system_context(factory) as db:
            await add_user(
                db,
                world,
                user,
                status="INVITED" if new_account else "ACTIVE",
                credential=not new_account,
            )
    membership_id = await add_membership(
        factory,
        world,
        f"{user}_invited_{tenant_id.hex[-4:]}",
        user=user,
        tenant_id=tenant_id,
        status="INVITED",
    )
    token = new_token()
    invitation_id = uuid.uuid7()
    async with system_context(factory, tenant_id=tenant_id) as db:
        await db.execute(
            insert(_table(UserInvitation)).values(
                id=invitation_id,
                tenant_id=tenant_id,
                membership_id=membership_id,
                token_hash=token_hash(secret, TokenPurpose.INVITATION, token),
                created_at=now() - timedelta(minutes=1),
                expires_at=now() + expires_in,
            )
        )
    return invitation_id, token
