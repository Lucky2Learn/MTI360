"""Shared T01-06 test data: platform users built through the system realm.

Platform users are created with ``system_context`` as the application role
(only the system realm may create them), with unique emails, because the
shared test database keeps every row.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.tenancy import system_context
from app.modules.platform_identity.models import (
    PlatformUser,
    PlatformUserCredential,
    PlatformUserRole,
)


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
