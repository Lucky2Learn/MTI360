"""Migrations ``0012`` / ``0013`` (Phase 02-4, ADR-0024): lead consent rules and the downgrade.

The schema allows a lead without a creator only as a consented website lead.
The ``0012`` downgrade removes such leads (development data loss, like
``0011``), but refuses while one is another lead's duplicate target or has an
application: that would cut admissions history.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import anyio
import pytest
from alembic import command
from conftest import DatabaseUnderTest
from identity_support import World, build_world
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.db import create_sessionmaker

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@pytest.fixture
async def app_db(
    migrated_database: DatabaseUnderTest,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(migrated_database.app_url, poolclass=NullPool)
    try:
        yield create_sessionmaker(engine)
    finally:
        await engine.dispose()


@pytest.fixture
async def world(app_db: async_sessionmaker[AsyncSession]) -> World:
    return await build_world(app_db)


async def _owner(database: DatabaseUnderTest, sql: str, **params: Any) -> list[Any]:
    engine = create_async_engine(database.owner_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            result = await connection.execute(text(sql), params)
            return list(result.all()) if result.returns_rows else []
    finally:
        await engine.dispose()


async def _lead(
    database: DatabaseUnderTest,
    tenant_id: uuid.UUID,
    *,
    source: str = "WEBSITE",
    consent: bool = True,
    duplicate_of: uuid.UUID | None = None,
    created_by: uuid.UUID | None = None,
) -> uuid.UUID:
    lead_id = uuid.uuid7()
    await _owner(
        database,
        "INSERT INTO leads (id, tenant_id, full_name, email, email_normalized, source, status, "
        "duplicate_of_lead_id, status_reason, created_by_membership_id, consent_version, "
        "consented_at, version) VALUES (:id, :t, 'Ananya Iyer', :e, :e, :s, :status, :d, "
        ":reason, :c, :v, :at, 1)",
        id=lead_id,
        t=tenant_id,
        e=f"{lead_id.hex[-8:]}@example.com",
        s=source,
        status="DUPLICATE" if duplicate_of else "NEW",
        d=duplicate_of,
        reason=None,
        c=created_by,
        v="enquiry-2026-10" if consent else None,
        at=datetime.now(UTC) if consent else None,
    )
    return lead_id


async def test_only_a_consented_website_lead_may_have_no_creator(
    migrated_database: DatabaseUnderTest, world: World
) -> None:
    await _lead(migrated_database, world.tenant_a)  # accepted
    with pytest.raises(DBAPIError, match="ck_leads_creator"):
        await _lead(migrated_database, world.tenant_a, source="WALK_IN")
    with pytest.raises(DBAPIError, match="ck_leads_creator"):
        await _lead(migrated_database, world.tenant_a, consent=False)
    with pytest.raises(DBAPIError, match="ck_leads_consent"):
        await _owner(
            migrated_database,
            "UPDATE leads SET consented_at = NULL WHERE tenant_id = :t "
            "AND created_by_membership_id IS NULL",
            t=world.tenant_a,
        )


async def test_the_public_enquiry_migrations_round_trip(
    migrated_database: DatabaseUnderTest, world: World
) -> None:
    config = migrated_database.alembic_config()
    member = world.memberships["alice_a"]
    public = await _lead(migrated_database, world.tenant_a)
    duplicate = await _lead(
        migrated_database, world.tenant_a, duplicate_of=public, created_by=member
    )
    try:
        # A public lead that is another lead's duplicate target blocks the downgrade.
        with pytest.raises(DBAPIError, match="linked to applications or duplicates"):
            await anyio.to_thread.run_sync(command.downgrade, config, "0011")
        assert (await _owner(migrated_database, "SELECT version_num FROM alembic_version"))[0][
            0
        ] in {"0012", "0013"}
        await _owner(migrated_database, "DELETE FROM leads WHERE id = :d", d=duplicate)

        await anyio.to_thread.run_sync(command.downgrade, config, "0011")
        tables = await _owner(
            migrated_database,
            "SELECT count(*) FROM pg_class WHERE relname IN ('tenant_domains', 'outbox_messages')",
        )
        assert tables[0][0] == 0
        assert (
            await _owner(
                migrated_database,
                "SELECT count(*) FROM leads WHERE created_by_membership_id IS NULL",
            )
        )[0][0] == 0
        nullable = await _owner(
            migrated_database,
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = 'leads' AND column_name = 'created_by_membership_id'",
        )
        assert nullable[0][0] == "NO"
    finally:
        await anyio.to_thread.run_sync(command.upgrade, config, "head")
    keys = await _owner(
        migrated_database,
        "SELECT conname FROM pg_constraint WHERE conrelid = 'outbox_messages'::regclass "
        "AND contype = 'u' ORDER BY conname",
    )
    assert [row[0] for row in keys] == [
        "uq_outbox_messages_tenant_id_id",
        "uq_outbox_messages_tenant_id_idempotency_key",
    ]
