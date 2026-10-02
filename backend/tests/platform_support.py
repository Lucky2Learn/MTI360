"""Shared T01-06 test data: platform users built through the system realm.

Platform users are created with ``system_context`` as the application role
(only the system realm may create them), with unique emails, because the
shared test database keeps every row.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any

from conftest import DatabaseUnderTest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from identity_support import FAST_HASHER, ORIGIN, auth_settings
from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.ratelimit import RedisRateLimiter
from app.core.security import totp
from app.core.tenancy import system_context
from app.integrations.email import FakeEmailSender
from app.main import create_app
from app.modules.platform_identity.models import (
    PlatformUser,
    PlatformUserCredential,
    PlatformUserRole,
)
from app.modules.platform_identity.service import PlatformIdentityService


def _table(model: Any) -> Any:
    return model.__table__


PLATFORM_PASSWORD = "Harbour pilot boards at dawn"


@dataclass
class PlatformWorld:
    suffix: str
    users: dict[str, uuid.UUID] = field(default_factory=dict)
    emails: dict[str, str] = field(default_factory=dict)

    def email(self, name: str) -> str:
        return self.emails[name]


async def add_platform_user(
    factory: async_sessionmaker[AsyncSession],
    world: PlatformWorld,
    name: str,
    *,
    password_hash: str,
    roles: tuple[str, ...] = (),
    status: str = "ACTIVE",
) -> uuid.UUID:
    user_id = uuid.uuid7()
    email = f"{name}.{world.suffix}@mti360-platform.example"
    async with system_context(factory) as db:
        await db.execute(
            insert(_table(PlatformUser)).values(
                id=user_id,
                email=email,
                display_name=name.replace("_", " ").title(),
                status=status,
                version=1,
            )
        )
        await db.execute(
            insert(_table(PlatformUserCredential)).values(
                id=uuid.uuid7(),
                platform_user_id=user_id,
                password_hash=password_hash,
                password_changed_at=datetime.now(UTC),
            )
        )
        for role in roles:
            await db.execute(
                insert(_table(PlatformUserRole)).values(
                    id=uuid.uuid7(), platform_user_id=user_id, role_code=role
                )
            )
    world.users[name] = user_id
    world.emails[name] = email
    return user_id


async def build_platform_world(
    factory: async_sessionmaker[AsyncSession], *, password_hash: str
) -> PlatformWorld:
    """``nora`` (SUPER_ADMIN), ``omar`` (SECURITY_AUDIT_ADMIN), ``pia`` (BILLING_ADMIN),
    ``quinn`` (SUPER_ADMIN, suspended)."""
    world = PlatformWorld(uuid.uuid7().hex[-8:])
    await add_platform_user(
        factory, world, "nora", password_hash=password_hash, roles=("SUPER_ADMIN",)
    )
    await add_platform_user(
        factory, world, "omar", password_hash=password_hash, roles=("SECURITY_AUDIT_ADMIN",)
    )
    await add_platform_user(
        factory, world, "pia", password_hash=password_hash, roles=("BILLING_ADMIN",)
    )
    await add_platform_user(
        factory,
        world,
        "quinn",
        password_hash=password_hash,
        roles=("SUPER_ADMIN",),
        status="SUSPENDED",
    )
    return world


# --- HTTP harness (platform API tests) --------------------------------------------------

PLATFORM_COOKIE = "__Host-mti360_psid"


class StepClock:
    """A clock in the recent past that moves forward one TOTP step per ``tick``.

    TOTP replay protection refuses a second code from the same 30-second step,
    so tests advance the service clock instead of sleeping. It starts five
    minutes in the past, so ``mfa_verified_at`` stays fresh for the real clock
    that ``authorize`` uses.
    """

    def __init__(self) -> None:
        self.now = datetime.now(UTC) - timedelta(minutes=5)

    def __call__(self) -> datetime:
        return self.now

    def tick(self, seconds: int = 31) -> datetime:
        self.now += timedelta(seconds=seconds)
        return self.now


@dataclass
class PlatformHarness:
    app: FastAPI
    client: AsyncClient
    world: PlatformWorld
    factory: async_sessionmaker[AsyncSession]
    email: FakeEmailSender
    database: DatabaseUnderTest
    clock: StepClock
    secrets: dict[str, str] = field(default_factory=dict)

    @property
    def service(self) -> PlatformIdentityService:
        service: PlatformIdentityService = self.app.state.platform_identity
        return service

    def code(self, name: str, offset: int = 0) -> str:
        """The current TOTP code of ``name``'s enrolled secret (after a clock tick)."""
        step = totp.time_step(self.clock.tick()) + offset
        return totp.code_at(self.secrets[name], step)

    async def login(self, name: str, password: str = PLATFORM_PASSWORD) -> Any:
        return await self.client.post(
            "/api/v1/platform/auth/login",
            json={"email": self.world.email(name), "password": password},
        )

    async def post(self, path: str, csrf: str, body: dict[str, Any] | None = None) -> Any:
        return await self.client.post(path, json=body or {}, headers={"X-CSRF-Token": csrf})

    async def enrol(self, name: str) -> tuple[Any, list[str]]:
        """Sign in and enrol ``name``; returns the full-session response and recovery codes."""
        login = await self.login(name)
        csrf = login.json()["data"]["csrf_token"]
        enrolment = await self.post("/api/v1/platform/auth/mfa/enrolment", csrf)
        self.secrets[name] = enrolment.json()["data"]["secret"]
        confirmed = await self.post(
            "/api/v1/platform/auth/mfa/enrolment/confirm", csrf, {"code": self.code(name)}
        )
        assert confirmed.status_code == 200, confirmed.text
        return confirmed, confirmed.json()["data"]["recovery_codes"]

    async def sign_in(self, name: str) -> str:
        """Full sign-in of an enrolled user (TOTP); returns the CSRF token."""
        login = await self.login(name)
        csrf = login.json()["data"]["csrf_token"]
        verified = await self.post(
            "/api/v1/platform/auth/mfa/verify", csrf, {"code": self.code(name)}
        )
        assert verified.status_code == 200, verified.text
        token: str = verified.json()["data"]["csrf_token"]
        return token

    async def audit(self, response: Any) -> list[Any]:
        rows = await self.owner(
            "SELECT event_type, metadata, target_id FROM audit_events "
            "WHERE request_id = :r ORDER BY id",
            r=uuid.UUID(response.headers["X-Request-ID"]),
        )
        return list(rows)

    async def owner(self, sql: str, **params: Any) -> Any:
        engine = create_async_engine(self.database.owner_url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                result = await connection.execute(text(sql), params)
                return result.all() if result.returns_rows else []
        finally:
            await engine.dispose()


@asynccontextmanager
async def platform_harness(
    database: DatabaseUnderTest, redis_url: str
) -> AsyncIterator[PlatformHarness]:
    app = create_app(auth_settings(database, redis_url))
    service: PlatformIdentityService = app.state.platform_identity
    await service.rate_limiter.close()
    service.rate_limiter = RedisRateLimiter.from_url(
        redis_url, namespace=f"test:{uuid.uuid7().hex}:auth:platform"
    )
    email = FakeEmailSender()
    service.email_sender = email
    service.config = replace(service.config, reset_response_floor_seconds=0.0)
    clock = StepClock()
    service._clock = clock
    world = await build_platform_world(
        app.state.sessionmaker, password_hash=FAST_HASHER.hash_sync(PLATFORM_PASSWORD)
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with AsyncClient(
            transport=transport, base_url="https://testserver", headers={"Origin": ORIGIN}
        ) as client:
            yield PlatformHarness(
                app, client, world, app.state.sessionmaker, email, database, clock
            )
    finally:
        await service.rate_limiter.close()
        await app.state.identity.rate_limiter.close()
        await app.state.engine.dispose()
