"""Shared T01-04/T01-05 test data: a two-institute world built through the system realm.

Everything is created with ``system_context`` as the application role (the
system realm is the only one allowed to create identities), with unique names
and emails per world, because the shared test database keeps every row.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any

from conftest import TEST_CSRF_SECRET, DatabaseUnderTest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.realms import REALM_PREFIXES, Access, realm_router
from app.core.audit.writer import AUDIT_TABLE
from app.core.config import Settings
from app.core.context import Realm, RequestContext, current_context
from app.core.db.session import context_transaction
from app.core.ratelimit import RedisRateLimiter
from app.core.tenancy import system_context
from app.integrations.email import FakeEmailSender
from app.main import create_app
from app.modules.access.models import MembershipRole, Role, RolePermission
from app.modules.access.service import clone_system_roles
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
from app.modules.identity.service import IdentityService
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
    roles: dict[str, uuid.UUID] = field(default_factory=dict)
    """``owner_a``, ``admin_a``, ``owner_b``, ``admin_b`` and custom roles by key."""

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


async def add_role(
    factory: async_sessionmaker[AsyncSession],
    world: World,
    key: str,
    *,
    tenant_id: uuid.UUID,
    permissions: tuple[str, ...],
    name: str | None = None,
) -> uuid.UUID:
    """A custom role (system realm) with explicit permissions."""
    role_id = uuid.uuid7()
    async with system_context(factory, tenant_id=tenant_id) as db:
        await db.execute(
            insert(_table(Role)).values(
                id=role_id,
                tenant_id=tenant_id,
                name=name or f"{key.replace('_', ' ').title()} {world.suffix}",
                is_system=False,
                version=1,
            )
        )
        for code in permissions:
            await db.execute(
                insert(_table(RolePermission)).values(
                    id=uuid.uuid7(), tenant_id=tenant_id, role_id=role_id, permission_code=code
                )
            )
    world.roles[key] = role_id
    return role_id


async def assign_role(
    factory: async_sessionmaker[AsyncSession], world: World, membership: str, role: str
) -> None:
    async with system_context(factory) as db:
        tenant_id = await db.scalar(
            select(_table(TenantMembership).c.tenant_id).where(
                _table(TenantMembership).c.id == world.memberships[membership]
            )
        )
    async with system_context(factory, tenant_id=tenant_id) as db:
        await db.execute(
            insert(_table(MembershipRole)).values(
                id=uuid.uuid7(),
                tenant_id=tenant_id,
                membership_id=world.memberships[membership],
                role_id=world.roles[role],
            )
        )


async def build_world(factory: async_sessionmaker[AsyncSession]) -> World:
    """Institutes A (two campuses) and B (one campus) and these people:

    * ``alice`` — A only, all campuses; Institute owner;
    * ``bob`` — A (selected: A1; Administrator) and B (all campuses;
      Administrator);
    * ``carol`` — B only; Institute owner;
    * ``dave`` — A, selected campuses A1 and A2 (campus choice required);
      custom role ``coordinator_a`` (campus.read, campus.update, member.read);
    * ``erin`` — no membership.

    Both institutes have their system roles (``owner_*``, ``admin_*``).
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
    for tenant, label in ((tenant_a, "a"), (tenant_b, "b")):
        async with system_context(factory, tenant_id=tenant.id) as db:
            system_roles = await clone_system_roles(db, tenant.id)
        world.roles[f"owner_{label}"] = system_roles["INSTITUTE_OWNER"]
        world.roles[f"admin_{label}"] = system_roles["ADMIN"]
    await add_role(
        factory,
        world,
        "coordinator_a",
        tenant_id=world.tenant_a,
        permissions=("campus.read", "campus.update", "member.read"),
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
    for membership, role in (
        ("alice_a", "owner_a"),
        ("bob_a", "admin_a"),
        ("bob_b", "admin_b"),
        ("carol_b", "owner_b"),
        ("dave_a", "coordinator_a"),
    ):
        await assign_role(factory, world, membership, role)
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


# --- HTTP harness (API tests) -----------------------------------------------------------

ORIGIN = "http://localhost:3000"
COOKIE = "__Host-mti360_tsid"


@dataclass
class Harness:
    app: FastAPI
    client: AsyncClient
    world: World
    factory: async_sessionmaker[AsyncSession]
    email: FakeEmailSender
    database: DatabaseUnderTest

    @property
    def service(self) -> IdentityService:
        service: IdentityService = self.app.state.identity
        return service

    async def login(self, user: str, password: str = PASSWORD) -> Any:
        return await self.client.post(
            "/api/v1/auth/login", json={"email": self.world.email(user), "password": password}
        )

    async def audit(self, response: Any) -> list[Any]:
        """Audit rows of one response (by its request ID), read as the platform."""
        context = RequestContext(realm=Realm.PLATFORM, request_id=uuid.uuid7())
        async with context_transaction(self.factory, context) as db:
            result = await db.execute(
                select(AUDIT_TABLE)
                .where(AUDIT_TABLE.c.request_id == uuid.UUID(response.headers["X-Request-ID"]))
                .order_by(AUDIT_TABLE.c.id)
            )
            return list(result.all())

    async def owner(self, sql: str, **params: Any) -> Any:
        """Run SQL as the owner (bypasses RLS) for test setup and inspection."""
        engine = create_async_engine(self.database.owner_url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                result = await connection.execute(text(sql), params)
                return result.all() if result.returns_rows else []
        finally:
            await engine.dispose()


def auth_settings(database: DatabaseUnderTest, redis_url: str) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        session_secret=SecretStr(TEST_SESSION_SECRET),
        csrf_secret=SecretStr(TEST_CSRF_SECRET),
        database_url=SecretStr(database.app_url),
        migrations_database_url=SecretStr(database.owner_url),
        readonly_database_url=SecretStr(database.readonly_url),
        redis_url=SecretStr(redis_url),
        argon2_time_cost=1,
        argon2_memory_cost_kib=8,
        argon2_parallelism=1,
    )


def _probe_router() -> Any:
    """A test-only tenant route that needs a ready session (Access.AUTHENTICATED)."""
    probe = realm_router(Realm.TENANT, access=Access.AUTHENTICATED)

    @probe.get("/probe/context", tags=["probe"])
    async def probe_context() -> dict[str, str | None]:
        context = current_context()
        return {
            "user": str(context.principal_id),
            "tenant": str(context.tenant_id) if context.tenant_id else None,
        }

    return probe


@asynccontextmanager
async def auth_harness(database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    app = create_app(auth_settings(database, redis_url))
    app.include_router(_probe_router(), prefix=REALM_PREFIXES[Realm.TENANT])
    service: IdentityService = app.state.identity
    await service.rate_limiter.close()
    service.rate_limiter = RedisRateLimiter.from_url(
        redis_url, namespace=f"test:{uuid.uuid7().hex}:auth"
    )
    email = FakeEmailSender()
    service.email_sender = email
    service.config = replace(service.config, reset_response_floor_seconds=0.0)
    world = await build_world(app.state.sessionmaker)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with AsyncClient(
            transport=transport, base_url="https://testserver", headers={"Origin": ORIGIN}
        ) as client:
            yield Harness(app, client, world, app.state.sessionmaker, email, database)
    finally:
        await service.rate_limiter.close()
        await app.state.engine.dispose()
