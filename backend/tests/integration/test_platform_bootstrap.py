"""The ``create-platform-admin`` bootstrap and break-glass path (T01-06, D6-1).

* the first ``SUPER_ADMIN`` is created only while no active one exists, and
  must enrol MFA at the first sign-in;
* break-glass needs a reason; it resets the password, clears MFA and revokes
  sessions (or creates a new ``SUPER_ADMIN``), and is audited;
* the password is never an argument and never printed, logged or audited.
"""

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from conftest import (
    TEST_CSRF_SECRET,
    TEST_DATA_ENCRYPTION_KEY,
    TEST_SESSION_SECRET,
    DatabaseUnderTest,
)
from platform_support import PlatformHarness, platform_harness

from app import cli
from app.modules.identity.passwords import PasswordHasher
from app.modules.platform_identity.bootstrap import BootstrapError, create_platform_admin

pytestmark = [pytest.mark.integration]

PASSWORD = "Lighthouse keeper's log 2026"
HASHER = PasswordHasher(time_cost=1, memory_cost_kib=8, parallelism=1)


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[PlatformHarness]:
    async with platform_harness(migrated_database, redis_url) as harness:
        yield harness


def _email(name: str) -> str:
    return f"{name}.{uuid.uuid7().hex[-8:]}@mti360-platform.example"


async def _suspend_every_super_admin(h: PlatformHarness) -> None:
    """The shared test database keeps earlier worlds: make 'no active SUPER_ADMIN' true."""
    await h.owner(
        "UPDATE platform_users SET status = 'SUSPENDED' WHERE status = 'ACTIVE' AND id IN "
        "(SELECT platform_user_id FROM platform_user_roles WHERE role_code = 'SUPER_ADMIN')"
    )


async def _audit_rows(h: PlatformHarness, user_id: uuid.UUID) -> list[Any]:
    return list(
        await h.owner(
            "SELECT event_type, realm, metadata FROM audit_events WHERE target_id = :u ORDER BY id",
            u=user_id,
        )
    )


@pytest.mark.anyio
async def test_the_first_super_admin_must_enrol_mfa(h: PlatformHarness) -> None:
    await _suspend_every_super_admin(h)
    email = _email("first")
    result = await create_platform_admin(
        h.factory, HASHER, email=email, display_name="First Officer", password=PASSWORD
    )
    assert result.created
    login = await h.client.post(
        "/api/v1/platform/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert login.json()["data"]["status"] == "mfa_enrolment_required"
    rows = await _audit_rows(h, result.platform_user_id)
    bootstrapped = [(row[0], row[1]) for row in rows if row[0].startswith("platform.admin")]
    assert bootstrapped == [("platform.admin.bootstrapped", "system")]
    assert PASSWORD not in str(rows)

    # A second bootstrap is refused while an active SUPER_ADMIN exists ...
    with pytest.raises(BootstrapError, match="already exists"):
        await create_platform_admin(
            h.factory, HASHER, email=_email("second"), display_name="Second", password=PASSWORD
        )


@pytest.mark.anyio
async def test_bootstrap_refuses_a_taken_email_and_weak_passwords(h: PlatformHarness) -> None:
    await _suspend_every_super_admin(h)
    with pytest.raises(BootstrapError, match="email already exists"):
        await create_platform_admin(
            h.factory,
            HASHER,
            email=h.world.email("pia"),
            display_name="Pia",
            password=PASSWORD,
        )
    with pytest.raises(BootstrapError, match="at least 12"):
        await create_platform_admin(
            h.factory, HASHER, email=_email("weak"), display_name="Weak", password="short"
        )


@pytest.mark.anyio
async def test_break_glass_needs_a_reason(h: PlatformHarness) -> None:
    with pytest.raises(BootstrapError, match="reason"):
        await create_platform_admin(
            h.factory,
            HASHER,
            email=h.world.email("nora"),
            display_name="Nora",
            password=PASSWORD,
            break_glass=True,
        )


@pytest.mark.anyio
async def test_break_glass_recovers_an_existing_admin(h: PlatformHarness) -> None:
    await h.enrol("nora")  # enrolled, with a live session
    result = await create_platform_admin(
        h.factory,
        HASHER,
        email=h.world.email("nora"),
        display_name="Nora",
        password=PASSWORD,
        break_glass=True,
        reason="Only SUPER_ADMIN lost the authenticator",
    )
    assert not result.created
    assert result.factors_disabled == 1
    assert result.sessions_revoked >= 1
    # The old session is gone; the new password works and MFA must be set up again.
    assert (await h.client.get("/api/v1/platform/session")).status_code == 401
    login = await h.client.post(
        "/api/v1/platform/auth/login", json={"email": h.world.email("nora"), "password": PASSWORD}
    )
    assert login.json()["data"]["status"] == "mfa_enrolment_required"
    rows = await _audit_rows(h, h.world.users["nora"])
    break_glass = [row for row in rows if row[0] == "platform.admin.break_glass"]
    assert break_glass[-1][2]["reason"] == "Only SUPER_ADMIN lost the authenticator"
    assert PASSWORD not in str(rows)


@pytest.mark.anyio
async def test_break_glass_creates_a_super_admin_for_an_unknown_email(h: PlatformHarness) -> None:
    email = _email("rescue")
    result = await create_platform_admin(
        h.factory,
        HASHER,
        email=email,
        display_name="Rescue Officer",
        password=PASSWORD,
        break_glass=True,
        reason="No usable SUPER_ADMIN",
    )
    assert result.created
    roles = await h.owner(
        "SELECT role_code FROM platform_user_roles WHERE platform_user_id = :u",
        u=result.platform_user_id,
    )
    assert [row[0] for row in roles] == ["SUPER_ADMIN"]


# --- The command line ---------------------------------------------------------------------------


def test_the_password_is_never_an_argument() -> None:
    with pytest.raises(SystemExit):
        cli.parser().parse_args(
            [
                "create-platform-admin",
                "--email",
                "a@b.example",
                "--display-name",
                "A",
                "--password",
                "x",
            ]
        )


def test_the_prompt_rejects_mismatches_and_weak_passwords() -> None:
    answers = iter([PASSWORD, PASSWORD + "!"])
    with pytest.raises(BootstrapError, match="do not match"):
        cli.read_password(lambda _prompt: next(answers))
    with pytest.raises(BootstrapError, match="at least 12"):
        cli.read_password(lambda _prompt: "short")


def test_the_command_never_prints_or_logs_the_password(
    migrated_database: DatabaseUnderTest,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    for name, value in {
        "APP_ENV": "test",
        "SESSION_SECRET": TEST_SESSION_SECRET,
        "CSRF_SECRET": TEST_CSRF_SECRET,
        "DATA_ENCRYPTION_KEY": TEST_DATA_ENCRYPTION_KEY,
        "DATABASE_URL": migrated_database.app_url,
        "MIGRATIONS_DATABASE_URL": migrated_database.owner_url,
        "READONLY_DATABASE_URL": migrated_database.readonly_url,
        "ARGON2_TIME_COST": "1",
        "ARGON2_MEMORY_COST_KIB": "8",
        "ARGON2_PARALLELISM": "1",
    }.items():
        monkeypatch.setenv(name, value)
    prompts: list[str] = []

    def prompt(text: str) -> str:
        prompts.append(text)
        return PASSWORD

    caplog.set_level(logging.DEBUG)
    code = cli.main(
        [
            "create-platform-admin",
            "--email",
            _email("cli"),
            "--display-name",
            "Chief Officer",
            "--break-glass",
            "--reason",
            "CLI test",
        ],
        prompt=prompt,
    )
    out = capsys.readouterr()
    assert code == cli.EXIT_OK
    assert "SUPER_ADMIN created" in out.out
    assert prompts == ["New password: ", "Repeat the password: "]
    for text in (out.out, out.err, caplog.text):
        assert PASSWORD not in text

    refused = cli.main(
        ["create-platform-admin", "--email", _email("cli2"), "--display-name", "Second Officer"],
        prompt=prompt,
    )
    assert refused == cli.EXIT_REFUSED
    assert "already exists" in capsys.readouterr().err
