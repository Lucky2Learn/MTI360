"""Operator command line (T01-06). Run from ``backend/`` (or inside the API image)::

    python -m app.cli create-platform-admin --email ADDRESS --display-name NAME
    python -m app.cli create-platform-admin --email ADDRESS --display-name NAME \\
        --break-glass --reason "Only SUPER_ADMIN lost their authenticator"

    python -m app.cli seed [--file PATH]

``seed`` (T01-08, decision D16) loads ``database/seeds/dev.json`` into a
**development** database only (``APP_ENV=development``) and prints each new
account's random one-time password once. It refuses to run twice.

``create-platform-admin`` (decision D6-1) creates the first ``SUPER_ADMIN``,
or recovers access with ``--break-glass``. The password is **never** an
argument (shell history, process lists): it is read twice from a no-echo
prompt. Nothing prints or logs it. The account must enrol MFA at its first
sign-in (``/platform/login``).

Uses ``DATABASE_URL`` (the application role, system realm); settings are
validated as for the API.
"""

import argparse
import asyncio
import getpass
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TextIO

from app.core.config import ConfigurationError, Settings, load_settings
from app.core.db import create_engine, create_sessionmaker
from app.modules.identity.passwords import PasswordHasher
from app.modules.platform_identity.bootstrap import (
    BootstrapError,
    BootstrapResult,
    create_platform_admin,
    validate_password,
)
from app.seed import DEFAULT_SEED_FILE, SeededAccount, SeedError, load_seed, seed

EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_CONFIGURATION = 3


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="python -m app.cli", description="MTI 360 operator tools")
    commands = root.add_subparsers(dest="command", required=True)
    create = commands.add_parser(
        "create-platform-admin",
        help="Create the first SUPER_ADMIN or recover access (break-glass).",
        description="The password is read from a no-echo prompt, never from arguments.",
    )
    create.add_argument("--email", required=True)
    create.add_argument("--display-name", required=True)
    create.add_argument(
        "--break-glass",
        action="store_true",
        help="Recover when no usable SUPER_ADMIN exists (resets password and MFA).",
    )
    create.add_argument("--reason", help="Required with --break-glass; recorded in the audit log.")
    seed_command = commands.add_parser(
        "seed",
        help="Load the development fixtures (APP_ENV=development only).",
        description="Prints each new account's random one-time password once.",
    )
    seed_command.add_argument("--file", type=Path, default=DEFAULT_SEED_FILE)
    return root


def read_password(prompt: Callable[[str], str] = getpass.getpass) -> str:
    """Ask twice without echo; raise ``BootstrapError`` on mismatch or a weak password."""
    first = prompt("New password: ")
    validate_password(first)
    if prompt("Repeat the password: ") != first:
        raise BootstrapError("The passwords do not match.")
    return first


async def _run(args: argparse.Namespace, password: str) -> BootstrapResult:
    settings = load_settings()
    engine = create_engine(settings)
    try:
        hasher = PasswordHasher(
            time_cost=settings.argon2_time_cost,
            memory_cost_kib=settings.argon2_memory_cost_kib,
            parallelism=settings.argon2_parallelism,
        )
        return await create_platform_admin(
            create_sessionmaker(engine),
            hasher,
            email=args.email,
            display_name=args.display_name,
            password=password,
            break_glass=args.break_glass,
            reason=args.reason,
        )
    finally:
        await engine.dispose()


def _out(stream: TextIO, message: str) -> None:
    stream.write(message + "\n")


async def _seed(settings: Settings, path: Path) -> list[SeededAccount]:
    institutes = load_seed(path)
    engine = create_engine(settings)
    try:
        hasher = PasswordHasher(
            time_cost=settings.argon2_time_cost,
            memory_cost_kib=settings.argon2_memory_cost_kib,
            parallelism=settings.argon2_parallelism,
        )
        return await seed(create_sessionmaker(engine), hasher, institutes)
    finally:
        await engine.dispose()


def run_seed(path: Path, *, settings_loader: Callable[[], Settings] = load_settings) -> int:
    try:
        settings = settings_loader()
        if settings.app_env != "development":
            _out(sys.stderr, "Refused: the development seed runs only with APP_ENV=development.")
            return EXIT_REFUSED
        accounts = asyncio.run(_seed(settings, path))
    except SeedError as refused:
        _out(sys.stderr, f"Refused: {refused}")
        return EXIT_REFUSED
    except ConfigurationError as error:
        _out(sys.stderr, str(error))
        return EXIT_CONFIGURATION
    _out(sys.stdout, "Development seed applied. One-time passwords (shown only now):")
    for account in accounts:
        _out(sys.stdout, f"  {account.email}  {account.password}")
    return EXIT_OK


def main(argv: Sequence[str] | None = None, *, prompt: Callable[[str], str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "seed":
        return run_seed(args.file)
    try:
        password = read_password(prompt or getpass.getpass)
        result = asyncio.run(_run(args, password))
    except BootstrapError as refused:
        _out(sys.stderr, f"Refused: {refused}")
        return EXIT_REFUSED
    except ConfigurationError as error:
        _out(sys.stderr, str(error))
        return EXIT_CONFIGURATION
    if result.created:
        _out(sys.stdout, "SUPER_ADMIN created. Sign in at /platform/login and set up MFA.")
    else:
        _out(
            sys.stdout,
            "Break-glass complete: password reset, MFA cleared "
            f"({result.factors_disabled} factor(s)), {result.sessions_revoked} session(s) "
            "revoked. Sign in at /platform/login and set up MFA again.",
        )
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    sys.exit(main())
