"""Operator command line (T01-06). Run from ``backend/`` (or inside the API image)::

    python -m app.cli create-platform-admin --email ADDRESS --display-name NAME
    python -m app.cli create-platform-admin --email ADDRESS --display-name NAME \\
        --break-glass --reason "Only SUPER_ADMIN lost their authenticator"

    python -m app.cli seed [--file PATH] [--tag TAG]
    python -m app.cli issue-site --tenant UUID --slug SLUG

``seed`` (T01-08, decision D16) loads ``database/seeds/dev.json`` into a
**development** database only (``APP_ENV=development``). Each account gets a
random password that is never printed, logged or stored in clear: developers
set their own with the password reset flow (Mailpit locally). It refuses to
run twice. ``--tag`` (Phase 02-3) loads the same demo again as new, separate
institutes and accounts (``principal.TAG@...``), without touching earlier ones.

``issue-site`` (Phase 02-4, ADR-0024) gives an institute its platform-issued
address ``<slug>.<PUBLIC_SITE_DOMAIN>`` for the hosted enquiry page; it is
refused when any institute holds that address or the institute already has
an active one. Audited as ``platform.tenant.site_issued``.

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
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TextIO

from sqlalchemy import select

from app.core.audit import AuditTarget, write_audit_event
from app.core.config import ConfigurationError, Settings, load_settings
from app.core.db import create_engine, create_sessionmaker
from app.core.tenancy import system_context
from app.integrations.storage import S3ObjectStorage
from app.modules.identity.passwords import PasswordHasher
from app.modules.platform_identity.bootstrap import (
    BootstrapError,
    BootstrapResult,
    create_platform_admin,
    validate_password,
)
from app.modules.tenants.domains import (
    DomainLimitError,
    DomainTakenError,
    issue_platform_subdomain,
)
from app.modules.tenants.events import SITE_ISSUED
from app.modules.tenants.models import Tenant
from app.modules.tenants.sites import InvalidSlugError, clean_slug
from app.seed import (
    DEFAULT_SEED_FILE,
    SeededAccount,
    SeedError,
    SeedInstitute,
    load_seed,
    seed,
    tag_seed,
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
    seed_command = commands.add_parser(
        "seed",
        help="Load the development fixtures (APP_ENV=development only).",
        description="Passwords are random and never shown; use the password reset flow.",
    )
    seed_command.add_argument("--file", type=Path, default=DEFAULT_SEED_FILE)
    seed_command.add_argument(
        "--tag",
        help="Load another, independent copy of the demo (1-16 lowercase letters or digits).",
    )
    site = commands.add_parser(
        "issue-site",
        help="Give an institute its platform-issued site address (<slug>.<site domain>).",
    )
    site.add_argument("--tenant", required=True, type=uuid.UUID)
    site.add_argument("--slug", required=True)
    return root


async def _issue_site(settings: Settings, tenant_id: uuid.UUID, slug: str) -> str:
    engine = create_engine(settings)
    try:
        async with system_context(create_sessionmaker(engine), tenant_id=tenant_id) as db:
            if await db.scalar(select(Tenant.id).where(Tenant.id == tenant_id)) is None:
                raise SiteRefusedError("no such institute")
            hostname = await issue_platform_subdomain(
                db, tenant_id, slug, site_domain=settings.public_site_domain
            )
            await write_audit_event(
                db,
                SITE_ISSUED,
                target=AuditTarget("tenant", tenant_id),
                metadata={"hostname": hostname},
            )
            return hostname
    finally:
        await engine.dispose()


class SiteRefusedError(Exception):
    """The address cannot be issued; the message is safe to print."""


def run_issue_site(
    tenant_id: uuid.UUID,
    slug: str,
    *,
    settings_loader: Callable[[], Settings] = load_settings,
) -> int:
    try:
        cleaned = clean_slug(slug)  # refused before any connection
        settings = settings_loader()
        hostname = asyncio.run(_issue_site(settings, tenant_id, cleaned))
    except InvalidSlugError as error:
        _out(sys.stderr, f"Refused: {error}")
        return EXIT_REFUSED
    except DomainTakenError:
        _out(sys.stderr, "Refused: this address belongs to an institute already.")
        return EXIT_REFUSED
    except DomainLimitError:
        _out(sys.stderr, "Refused: the institute already has an active site address.")
        return EXIT_REFUSED
    except SiteRefusedError as error:
        _out(sys.stderr, f"Refused: {error}")
        return EXIT_REFUSED
    except ConfigurationError as error:
        _out(sys.stderr, str(error))
        return EXIT_CONFIGURATION
    _out(sys.stdout, f"Site address issued: https://{hostname}/enquiry")
    return EXIT_OK


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


async def _seed(settings: Settings, institutes: tuple[SeedInstitute, ...]) -> list[SeededAccount]:
    engine = create_engine(settings)
    try:
        hasher = PasswordHasher(
            time_cost=settings.argon2_time_cost,
            memory_cost_kib=settings.argon2_memory_cost_kib,
            parallelism=settings.argon2_parallelism,
        )
        storage = S3ObjectStorage.create(
            endpoint_url=settings.s3_endpoint_url or None,
            region=settings.s3_region,
            bucket=settings.s3_bucket,
            access_key_id=settings.s3_access_key_id.get_secret_value(),
            secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        )
        return await seed(
            create_sessionmaker(engine),
            hasher,
            institutes,
            storage=storage,
            site_domain=settings.public_site_domain,
        )
    finally:
        await engine.dispose()


def run_seed(
    path: Path,
    *,
    tag: str | None = None,
    settings_loader: Callable[[], Settings] = load_settings,
) -> int:
    try:
        settings = settings_loader()
        if settings.app_env != "development":
            _out(sys.stderr, "Refused: the development seed runs only with APP_ENV=development.")
            return EXIT_REFUSED
        institutes = load_seed(path)
        if tag is not None:
            institutes = tag_seed(institutes, tag)
        accounts = asyncio.run(_seed(settings, institutes))
    except SeedError as refused:
        _out(sys.stderr, f"Refused: {refused}")
        return EXIT_REFUSED
    except ConfigurationError as error:
        _out(sys.stderr, str(error))
        return EXIT_CONFIGURATION
    # Never the passwords (CodeQL: clear-text logging): emails only.
    _out(sys.stdout, "Development seed applied. Institutes:")
    for institute in institutes:
        _out(sys.stdout, f"  {institute.name}")
    _out(sys.stdout, "Accounts (set a password with password reset):")
    for account in accounts:
        _out(sys.stdout, f"  {account.email}")
    return EXIT_OK


def main(argv: Sequence[str] | None = None, *, prompt: Callable[[str], str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "seed":
        return run_seed(args.file, tag=args.tag)
    if args.command == "issue-site":
        return run_issue_site(args.tenant, args.slug)
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
