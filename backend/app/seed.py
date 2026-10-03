"""Development seed (T01-08; T01-00 decision D16). Run ``python -m app.cli seed``.

Loads ``database/seeds/dev.json`` (realistic maritime fixtures) into a
**development** database, as the system realm:

* institutes (``TRIAL`` or ``ACTIVE``) with their campuses and system roles
  (cloned from the code templates, T01-05);
* ``ACTIVE`` people with a credential, an ``ACTIVE`` membership, a campus scope
  and one system role each; the first owner of an institute becomes its
  primary administrator (``tenants.owner_membership_id``, T01-07).

Rules (D16): every email uses a reserved ``.example`` domain; every password is
random, generated here, never stored in the file, never printed, logged or
audited (developers set their own through the password reset flow); the seed
refuses to run twice (an email already exists) and the command refuses to run
outside ``APP_ENV=development``.
Role names come from the file and are mapped to the code templates; they are
never authorization logic.
"""

import json
import re
import secrets
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, cast

from sqlalchemy import Table, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import AuditCategory, AuditEventType, AuditTarget, write_audit_event
from app.core.tenancy import system_context
from app.modules.access import repository as access_repo
from app.modules.access.service import clone_system_roles
from app.modules.access.templates import OWNER_TEMPLATE, SystemRole
from app.modules.identity.domain import (
    CampusScope,
    InvalidEmailError,
    MembershipStatus,
    UserStatus,
    normalize_email,
    password_problem,
)
from app.modules.identity.models import MembershipCampus, TenantMembership, User, UserCredential
from app.modules.identity.passwords import PasswordHasher, common_passwords
from app.modules.institute.models import CAMPUS_CODE_PATTERN, Campus
from app.modules.tenants.domain import TenantStatus
from app.modules.tenants.models import Tenant

DEFAULT_SEED_FILE: Final = Path(__file__).resolve().parents[2] / "database" / "seeds" / "dev.json"
SEEDED: Final = AuditEventType("system.seed.applied", AuditCategory.ADMIN)
SEED_STATUSES: Final = frozenset({TenantStatus.TRIAL, TenantStatus.ACTIVE})

USERS = cast(Table, User.__table__)
CREDENTIALS = cast(Table, UserCredential.__table__)
MEMBERSHIPS = cast(Table, TenantMembership.__table__)
MEMBERSHIP_CAMPUSES = cast(Table, MembershipCampus.__table__)
CAMPUSES = cast(Table, Campus.__table__)
TENANTS = cast(Table, Tenant.__table__)


class SeedError(Exception):
    """A refused or invalid seed; the message is safe to print (no secrets)."""


@dataclass(frozen=True, slots=True)
class SeedMember:
    email: str
    display_name: str
    role: SystemRole
    campus_scope: CampusScope
    campuses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SeedInstitute:
    name: str
    status: TenantStatus
    campuses: tuple[tuple[str, str], ...]
    """(code, name)"""
    members: tuple[SeedMember, ...]


@dataclass(frozen=True, slots=True)
class SeededAccount:
    email: str
    password: str


def generate_password() -> str:
    """A random 24-character password (well above the 12-character minimum)."""
    while True:
        candidate = secrets.token_urlsafe(18)
        if password_problem(candidate, common_passwords()) is None:
            return candidate


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SeedError(f"{field}: a non-empty string is required")
    return " ".join(value.split())


def _member(raw: Mapping[str, Any], codes: set[str], where: str) -> SeedMember:
    try:
        email = normalize_email(_text(raw.get("email"), f"{where}.email"))
    except InvalidEmailError:
        raise SeedError(f"{where}.email: not a valid email address") from None
    if not email.rsplit("@", 1)[1].endswith(".example"):
        raise SeedError(f"{where}.email: development emails must use a .example domain")
    try:
        role = SystemRole(str(raw.get("role")))
        scope = CampusScope(raw.get("campus_scope", CampusScope.ALL.value))
    except ValueError:
        raise SeedError(f"{where}: unknown role or campus_scope") from None
    campuses = tuple(raw.get("campuses", ()))
    if scope is CampusScope.SELECTED and not campuses:
        raise SeedError(f"{where}.campuses: a SELECTED scope needs at least one campus")
    if scope is CampusScope.ALL and campuses:
        raise SeedError(f"{where}.campuses: leave empty for all campuses")
    if not set(campuses) <= codes:
        raise SeedError(f"{where}.campuses: unknown campus code")
    return SeedMember(
        email, _text(raw.get("display_name"), f"{where}.display_name"), role, scope, campuses
    )


def parse_seed(data: Mapping[str, Any]) -> tuple[SeedInstitute, ...]:
    """Validate the seed document (``database/seeds/dev.json``)."""
    institutes: list[SeedInstitute] = []
    raw_institutes = data.get("institutes")
    if not isinstance(raw_institutes, list) or not raw_institutes:
        raise SeedError("institutes: a non-empty list is required")
    for index, raw in enumerate(raw_institutes):
        where = f"institutes[{index}]"
        try:
            status = TenantStatus(raw.get("status", TenantStatus.TRIAL.value))
        except ValueError:
            raise SeedError(f"{where}.status: unknown status") from None
        if status not in SEED_STATUSES:
            raise SeedError(f"{where}.status: TRIAL or ACTIVE only")
        campuses: list[tuple[str, str]] = []
        for campus in raw.get("campuses", ()):
            code = _text(campus.get("code"), f"{where}.campuses.code").upper()
            if not re.fullmatch(CAMPUS_CODE_PATTERN, code):
                raise SeedError(f"{where}.campuses.code: invalid campus code")
            campuses.append((code, _text(campus.get("name"), f"{where}.campuses.name")))
        codes = {code for code, _ in campuses}
        if not campuses or len(codes) != len(campuses):
            raise SeedError(f"{where}.campuses: at least one campus, unique codes")
        members = tuple(
            _member(member, codes, f"{where}.members[{i}]")
            for i, member in enumerate(raw.get("members", ()))
        )
        if not any(m.role is OWNER_TEMPLATE for m in members):
            raise SeedError(f"{where}.members: at least one owner is required")
        institutes.append(
            SeedInstitute(_text(raw.get("name"), f"{where}.name"), status, tuple(campuses), members)
        )
    return tuple(institutes)


def load_seed(path: Path = DEFAULT_SEED_FILE) -> tuple[SeedInstitute, ...]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SeedError(f"cannot read the seed file {path.name}: {type(error).__name__}") from None
    if not isinstance(data, dict):
        raise SeedError("the seed file must contain a JSON object")
    return parse_seed(data)


async def _identity(
    db: AsyncSession, email: str, display_name: str, password_hash: str, now: datetime
) -> uuid.UUID:
    user_id = uuid.uuid7()
    await db.execute(
        insert(USERS).values(
            id=user_id,
            email=email,
            display_name=display_name,
            status=UserStatus.ACTIVE.value,
            email_verified_at=now,
            version=1,
        )
    )
    await db.execute(
        insert(CREDENTIALS).values(
            id=uuid.uuid7(), user_id=user_id, password_hash=password_hash, password_changed_at=now
        )
    )
    return user_id


async def seed(
    factory: async_sessionmaker[AsyncSession],
    hasher: PasswordHasher,
    institutes: Sequence[SeedInstitute],
    *,
    password_factory: Callable[[], str] = generate_password,
) -> list[SeededAccount]:
    """Create the fixtures; return each new account's one-time password (refused if seeded)."""
    emails = sorted({m.email for institute in institutes for m in institute.members})
    async with system_context(factory) as db:
        taken = await db.scalars(select(USERS.c.email).where(USERS.c.email.in_(emails)))
        if list(taken):
            raise SeedError("the development seed has already been applied (an email exists)")
    accounts = {email: password_factory() for email in emails}
    hashes = {email: await hasher.hash(password) for email, password in accounts.items()}
    names = {m.email: m.display_name for i in institutes for m in i.members}
    now = datetime.now(UTC)
    users: dict[str, uuid.UUID] = {}
    async with system_context(factory) as db:
        for email in emails:
            users[email] = await _identity(db, email, names[email], hashes[email], now)
    for institute in institutes:
        tenant_id = uuid.uuid7()
        async with system_context(factory) as db:
            await db.execute(
                insert(TENANTS).values(
                    id=tenant_id, name=institute.name, status=institute.status.value, version=1
                )
            )
        async with system_context(factory, tenant_id=tenant_id) as db:
            campus_ids: dict[str, uuid.UUID] = {}
            for code, name in institute.campuses:
                campus_ids[code] = uuid.uuid7()
                await db.execute(
                    insert(CAMPUSES).values(
                        id=campus_ids[code], tenant_id=tenant_id, name=name, code=code, version=1
                    )
                )
            roles = await clone_system_roles(db, tenant_id)
            owner: uuid.UUID | None = None
            for member in institute.members:
                membership_id = uuid.uuid7()
                await db.execute(
                    insert(MEMBERSHIPS).values(
                        id=membership_id,
                        tenant_id=tenant_id,
                        user_id=users[member.email],
                        status=MembershipStatus.ACTIVE.value,
                        campus_scope=member.campus_scope.value,
                        joined_at=now,
                        version=1,
                    )
                )
                for code in member.campuses:
                    await db.execute(
                        insert(MEMBERSHIP_CAMPUSES).values(
                            id=uuid.uuid7(),
                            tenant_id=tenant_id,
                            membership_id=membership_id,
                            campus_id=campus_ids[code],
                        )
                    )
                await access_repo.assign(db, tenant_id, membership_id, roles[member.role.value])
                if owner is None and member.role is OWNER_TEMPLATE:
                    owner = membership_id
            await db.execute(
                update(TENANTS).where(TENANTS.c.id == tenant_id).values(owner_membership_id=owner)
            )
            await write_audit_event(
                db,
                SEEDED,
                target=AuditTarget("tenant", tenant_id),
                metadata={
                    "campus_count": len(institute.campuses),
                    "member_count": len(institute.members),
                },
            )
    return [SeededAccount(email, accounts[email]) for email in emails]
