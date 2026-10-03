"""First platform administrator and break-glass recovery (T01-06, D6-1).

Run through the ``create-platform-admin`` command (``python -m app.cli``),
as the system realm:

* **Bootstrap** creates the first ``SUPER_ADMIN`` (ACTIVE, password set, no
  MFA factor), refused while an active ``SUPER_ADMIN`` exists or the email is
  taken. The first sign-in must enrol MFA (mandatory for the platform realm).
* **Break-glass** (``--break-glass`` with a reason) recovers when no usable
  ``SUPER_ADMIN`` remains: an existing account is reactivated with a new
  password, the ``SUPER_ADMIN`` role, its MFA disabled (re-enrolment at the
  next sign-in) and its sessions revoked; an unknown email gets a new
  ``SUPER_ADMIN``.

Both write an administrative audit event (system realm) with the email
domain and the reason — never the password. The password is hashed before
the transaction (D02) and never logged.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, cast

from sqlalchemy import Table, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import AuditCategory, AuditEventType, AuditTarget, write_audit_event
from app.core.ids import new_id
from app.core.security.mfa import MfaStore
from app.core.tenancy import system_context
from app.modules.identity.domain import (
    PASSWORD_MESSAGES,
    InvalidEmailError,
    normalize_email,
    password_problem,
)
from app.modules.identity.passwords import PasswordHasher, common_passwords
from app.modules.platform_identity import repository as repo
from app.modules.platform_identity.domain import PlatformSessionRevokeReason, PlatformUserStatus
from app.modules.platform_identity.models import PlatformMfaFactor, PlatformRecoveryCode
from app.modules.platform_identity.roles import PlatformRole

BOOTSTRAPPED: Final = AuditEventType("platform.admin.bootstrapped", AuditCategory.ADMIN)
BREAK_GLASS: Final = AuditEventType("platform.admin.break_glass", AuditCategory.ADMIN)
REASON_MAX_LENGTH: Final = 500


class BootstrapError(Exception):
    """A refused bootstrap; the message is safe to print (no secrets)."""


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    platform_user_id: uuid.UUID
    created: bool
    sessions_revoked: int = 0
    factors_disabled: int = 0


def _mfa_store() -> MfaStore:
    # Only ``disable`` is used here: no recovery-code hashing, so no secret is needed.
    return MfaStore(
        cast(Table, PlatformMfaFactor.__table__),
        cast(Table, PlatformRecoveryCode.__table__),
        "platform_user_id",
        "",
        "unused",
    )


async def _active_super_admins(db: AsyncSession) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(repo.ROLES.join(repo.USERS, repo.USERS.c.id == repo.ROLES.c.platform_user_id))
        .where(
            repo.ROLES.c.role_code == PlatformRole.SUPER_ADMIN.value,
            repo.USERS.c.status == PlatformUserStatus.ACTIVE.value,
        )
    )
    return int(count or 0)


async def _create(
    db: AsyncSession, *, email: str, display_name: str, password_hash: str, now: datetime
) -> uuid.UUID:
    user_id = new_id()
    await db.execute(
        insert(repo.USERS).values(
            id=user_id,
            email=email,
            display_name=display_name,
            status=PlatformUserStatus.ACTIVE.value,
            version=1,
        )
    )
    await db.execute(
        insert(repo.CREDENTIALS).values(
            id=new_id(),
            platform_user_id=user_id,
            password_hash=password_hash,
            password_changed_at=now,
        )
    )
    await db.execute(
        insert(repo.ROLES).values(
            id=new_id(), platform_user_id=user_id, role_code=PlatformRole.SUPER_ADMIN.value
        )
    )
    return user_id


def validate_password(password: str) -> None:
    problem = password_problem(password, common_passwords())
    if problem is not None:
        raise BootstrapError(PASSWORD_MESSAGES[problem])


async def create_platform_admin(
    factory: async_sessionmaker[AsyncSession],
    hasher: PasswordHasher,
    *,
    email: str,
    display_name: str,
    password: str,
    break_glass: bool = False,
    reason: str | None = None,
) -> BootstrapResult:
    try:
        canonical = normalize_email(email)
    except InvalidEmailError:
        raise BootstrapError("Enter a valid email address.") from None
    name = " ".join(display_name.split())
    if not name or len(name) > 200:
        raise BootstrapError("Enter a display name of up to 200 characters.")
    cleaned_reason = " ".join((reason or "").split())
    if break_glass and not (0 < len(cleaned_reason) <= REASON_MAX_LENGTH):
        raise BootstrapError("Break-glass needs --reason (up to 500 characters).")
    validate_password(password)
    password_hash = await hasher.hash(password)  # outside the transaction (D02)

    now = datetime.now(UTC)
    domain = canonical.partition("@")[2]
    async with system_context(factory) as db:
        existing = await db.scalar(select(repo.USERS.c.id).where(repo.USERS.c.email == canonical))
        if not break_glass:
            if await _active_super_admins(db) > 0:
                raise BootstrapError(
                    "A SUPER_ADMIN already exists. Use --break-glass only if none is usable."
                )
            if existing is not None:
                raise BootstrapError("A platform user with this email already exists.")
            user_id = await _create(
                db, email=canonical, display_name=name, password_hash=password_hash, now=now
            )
            await write_audit_event(
                db,
                BOOTSTRAPPED,
                target=AuditTarget("platform_user", user_id),
                metadata={"email_domain": domain},
            )
            return BootstrapResult(user_id, created=True)

        if existing is None:
            user_id = await _create(
                db, email=canonical, display_name=name, password_hash=password_hash, now=now
            )
            result = BootstrapResult(user_id, created=True)
        else:
            user_id = existing
            await db.execute(
                update(repo.USERS)
                .where(repo.USERS.c.id == user_id)
                .values(
                    status=PlatformUserStatus.ACTIVE.value,
                    version=repo.USERS.c.version + 1,
                    updated_at=func.now(),
                )
            )
            if not await repo.set_password(db, user_id, password_hash, now):
                await db.execute(
                    insert(repo.CREDENTIALS).values(
                        id=new_id(),
                        platform_user_id=user_id,
                        password_hash=password_hash,
                        password_changed_at=now,
                    )
                )
            if PlatformRole.SUPER_ADMIN not in await repo.roles_of(db, user_id):
                await db.execute(
                    insert(repo.ROLES).values(
                        id=new_id(),
                        platform_user_id=user_id,
                        role_code=PlatformRole.SUPER_ADMIN.value,
                    )
                )
            factors = await _mfa_store().disable(db, user_id, reason="break_glass", now=now)
            sessions = await repo.revoke_user_sessions(
                db, user_id, PlatformSessionRevokeReason.BREAK_GLASS, now
            )
            result = BootstrapResult(
                user_id, created=False, sessions_revoked=sessions, factors_disabled=factors
            )
        await write_audit_event(
            db,
            BREAK_GLASS,
            target=AuditTarget("platform_user", user_id),
            metadata={
                "email_domain": domain,
                "reason": cleaned_reason,
                "created": result.created,
                "factors_disabled": result.factors_disabled,
                "sessions_revoked": result.sessions_revoked,
            },
        )
        return result
