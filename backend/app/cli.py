"""Operator command line (T01-06). Run from ``backend/`` (or inside the API image)::

    python -m app.cli create-platform-admin --email ADDRESS --display-name NAME
    python -m app.cli create-platform-admin --email ADDRESS --display-name NAME \\
        --break-glass --reason "Only SUPER_ADMIN lost their authenticator"

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
from typing import TextIO

from app.core.config import ConfigurationError, load_settings
from app.core.db import create_engine, create_sessionmaker
from app.modules.identity.passwords import PasswordHasher
from app.modules.platform_identity.bootstrap import (
    BootstrapError,
    BootstrapResult,
    create_platform_admin,
    validate_password,
)

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


def main(argv: Sequence[str] | None = None, *, prompt: Callable[[str], str] | None = None) -> int:
    args = parser().parse_args(argv)
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
