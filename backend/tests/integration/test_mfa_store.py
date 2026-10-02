"""The MFA store on both realms' tables (T01-06; D6-4).

Enrolment, confirmation, replay-protected verification, single-use recovery
codes and disabling, through the application role under RLS: the platform
store as a platform principal, the tenant store as a tenant user.
"""

import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from conftest import DatabaseUnderTest
from identity_support import build_world
from platform_support import build_platform_world
from sqlalchemy import Table, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.context import Realm, RequestContext
from app.core.db import create_sessionmaker
from app.core.db.session import context_transaction
from app.core.security import totp
from app.core.security.encryption import KeyRing
from app.core.security.mfa import MfaAlreadyEnabledError, MfaStore
from app.modules.identity.models import UserMfaFactor, UserRecoveryCode
from app.modules.platform_identity.models import PlatformMfaFactor, PlatformRecoveryCode

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

RING = KeyRing("k1", {"k1": b"k" * 32})
SECRET = "mti360-test-session-secret-0123456789abcdef"
NOW = datetime(2026, 10, 2, 9, 30, 10, tzinfo=UTC)

type Opener = Callable[[], AbstractAsyncContextManager[AsyncSession]]


@pytest.fixture
async def app_db(
    migrated_database: DatabaseUnderTest,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(migrated_database.app_url, poolclass=NullPool)
    try:
        yield create_sessionmaker(engine)
    finally:
        await engine.dispose()


def _table(model: Any) -> Table:
    return cast(Table, model.__table__)


PLATFORM_STORE = MfaStore(
    _table(PlatformMfaFactor), _table(PlatformRecoveryCode), "platform_user_id", SECRET, "p"
)
TENANT_STORE = MfaStore(_table(UserMfaFactor), _table(UserRecoveryCode), "user_id", SECRET, "t")


@pytest.fixture(params=["platform", "tenant"])
async def subject(
    request: pytest.FixtureRequest, app_db: async_sessionmaker[AsyncSession]
) -> tuple[MfaStore, uuid.UUID, Opener]:
    if request.param == "platform":
        world = await build_platform_world(app_db, password_hash="x")
        owner, realm, store = world.users["pia"], Realm.PLATFORM, PLATFORM_STORE
    else:
        tenant_world = await build_world(app_db)
        owner, realm, store = tenant_world.users["alice"], Realm.TENANT, TENANT_STORE

    def opener() -> AbstractAsyncContextManager[AsyncSession]:
        context = RequestContext(realm=realm, request_id=uuid.uuid7(), principal_id=owner)
        return context_transaction(app_db, context)

    return store, owner, opener


async def _enrol(store: MfaStore, owner: uuid.UUID, opener: Opener) -> tuple[str, list[str]]:
    async with opener() as db:
        enrolment = await store.start_enrolment(
            db, owner, keyring=RING, account="pia@mti360.example", now=NOW
        )
    code = totp.code_at(enrolment.secret, totp.time_step(NOW))
    async with opener() as db:
        codes = await store.confirm_enrolment(db, owner, code, keyring=RING, now=NOW)
    assert codes is not None
    return enrolment.secret, codes


async def test_enrolment_stores_only_an_encrypted_secret(
    subject: tuple[MfaStore, uuid.UUID, Opener],
) -> None:
    store, owner, opener = subject
    async with opener() as db:
        enrolment = await store.start_enrolment(
            db, owner, keyring=RING, account="pia@mti360.example", now=NOW
        )
        assert not await store.enabled(db, owner)
        stored = (
            await db.execute(
                text(
                    f"SELECT secret_ciphertext FROM {store.factors.name} "  # noqa: S608
                    f"WHERE {store.owner} = :o AND disabled_at IS NULL"
                ),
                {"o": owner},
            )
        ).scalar_one()
    assert enrolment.secret not in stored
    assert stored.startswith("v1:k1:")
    assert enrolment.otpauth_uri.startswith("otpauth://totp/")
    # A wrong first code does not confirm; a second enrolment replaces the first.
    async with opener() as db:
        assert await store.confirm_enrolment(db, owner, "000000", keyring=RING, now=NOW) is None
    async with opener() as db:
        second = await store.start_enrolment(
            db, owner, keyring=RING, account="pia@mti360.example", now=NOW
        )
    async with opener() as db:
        stale = totp.code_at(enrolment.secret, totp.time_step(NOW))
        assert await store.confirm_enrolment(db, owner, stale, keyring=RING, now=NOW) is None
        fresh = totp.code_at(second.secret, totp.time_step(NOW))
        codes = await store.confirm_enrolment(db, owner, fresh, keyring=RING, now=NOW)
        assert codes is not None
        assert len(codes) == totp.RECOVERY_CODE_COUNT
        assert await store.enabled(db, owner)
        assert await store.remaining_codes(db, owner) == totp.RECOVERY_CODE_COUNT
    async with opener() as db:
        with pytest.raises(MfaAlreadyEnabledError):
            await store.start_enrolment(db, owner, keyring=RING, account="x", now=NOW)


async def test_verification_is_replay_protected(
    subject: tuple[MfaStore, uuid.UUID, Opener],
) -> None:
    store, owner, opener = subject
    secret, _ = await _enrol(store, owner, opener)  # the confirmation used step(NOW)
    later = NOW + timedelta(seconds=60)
    step = totp.time_step(later)

    async def verify(code: str, moment: datetime = later) -> bool:
        async with opener() as db:
            return await store.verify_totp(db, owner, code, keyring=RING, now=moment)

    # The code consumed by the confirmation cannot be used again.
    assert not await verify(totp.code_at(secret, totp.time_step(NOW)), NOW)
    assert await verify(totp.code_at(secret, step - 1))  # previous step accepted once
    assert not await verify(totp.code_at(secret, step - 1))  # replay refused
    assert await verify(totp.code_at(secret, step + 1))  # next step (clock skew)
    assert not await verify(totp.code_at(secret, step))  # older than the last accepted step
    assert not await verify(totp.code_at(secret, step + 3))  # outside the window
    assert not await verify("123")


async def test_recovery_codes_are_single_use_and_replaceable(
    subject: tuple[MfaStore, uuid.UUID, Opener],
) -> None:
    store, owner, opener = subject
    _, codes = await _enrol(store, owner, opener)
    async with opener() as db:
        assert await store.use_recovery_code(db, owner, codes[0].upper(), now=NOW)
        assert not await store.use_recovery_code(db, owner, codes[0], now=NOW)
        assert not await store.use_recovery_code(db, owner, "abcde-fghij", now=NOW)
        assert await store.remaining_codes(db, owner) == totp.RECOVERY_CODE_COUNT - 1
        stored = set(
            (
                await db.execute(
                    text(f"SELECT code_hash FROM {store.codes.name} WHERE {store.owner} = :o"),  # noqa: S608
                    {"o": owner},
                )
            ).scalars()
        )
    assert not {code.replace("-", "") for code in codes} & stored
    async with opener() as db:
        fresh = await store.replace_recovery_codes(db, owner, now=NOW)
        assert not await store.use_recovery_code(db, owner, codes[1], now=NOW)  # invalidated
        assert await store.use_recovery_code(db, owner, fresh[0], now=NOW)


async def test_disabling_removes_the_factor_and_its_codes(
    subject: tuple[MfaStore, uuid.UUID, Opener],
) -> None:
    store, owner, opener = subject
    secret, codes = await _enrol(store, owner, opener)
    async with opener() as db:
        assert await store.disable(db, owner, reason="admin_reset", now=NOW) == 1
        assert not await store.enabled(db, owner)
        assert not await store.use_recovery_code(db, owner, codes[0], now=NOW)
        later = NOW + timedelta(minutes=2)
        code = totp.code_at(secret, totp.time_step(later))
        assert not await store.verify_totp(db, owner, code, keyring=RING, now=later)
        assert await store.remaining_codes(db, owner) == 0


async def test_an_undecryptable_secret_fails_closed(
    subject: tuple[MfaStore, uuid.UUID, Opener],
) -> None:
    store, owner, opener = subject
    secret, _ = await _enrol(store, owner, opener)
    later = NOW + timedelta(minutes=2)
    other_ring = KeyRing("k1", {"k1": b"o" * 32})
    async with opener() as db:
        code = totp.code_at(secret, totp.time_step(later))
        assert not await store.verify_totp(db, owner, code, keyring=other_ring, now=later)
        assert await store.verify_totp(db, owner, code, keyring=RING, now=later)
