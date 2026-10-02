"""Platform identity data access (T01-06).

Core statements on the platform tables. Which rows they reach is decided by
the transaction kind (``lookup``) and Row-Level Security (migration ``0006``);
statements still filter by the identifiers the service resolved.
Credentials are read only by the authentication flows here, never by
directory queries.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import Table, func, insert, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_id
from app.modules.platform_identity.domain import PlatformSessionRevokeReason, PlatformUserStatus
from app.modules.platform_identity.models import (
    PlatformPasswordResetToken,
    PlatformSession,
    PlatformUser,
    PlatformUserCredential,
    PlatformUserRole,
)
from app.modules.platform_identity.roles import PlatformRole

USERS = cast(Table, PlatformUser.__table__)
CREDENTIALS = cast(Table, PlatformUserCredential.__table__)
ROLES = cast(Table, PlatformUserRole.__table__)
SESSIONS = cast(Table, PlatformSession.__table__)
RESET_TOKENS = cast(Table, PlatformPasswordResetToken.__table__)


def _rowcount(result: object) -> int:
    return cast(CursorResult[object], result).rowcount


@dataclass(frozen=True, slots=True)
class LoginCandidate:
    user_id: uuid.UUID
    status: PlatformUserStatus
    password_hash: str | None
    locked_until: datetime | None


@dataclass(frozen=True, slots=True)
class PlatformIdentity:
    display_name: str
    email: str
    status: PlatformUserStatus


@dataclass(frozen=True, slots=True)
class SessionRow:
    id: uuid.UUID
    user_id: uuid.UUID
    mfa_verified_at: datetime | None
    mfa_failed_attempts: int
    last_seen_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class ResetTokenRow:
    id: uuid.UUID
    user_id: uuid.UUID
    expires_at: datetime
    used_at: datetime | None
    invalidated_at: datetime | None


# --- Identity and credentials ----------------------------------------------------------------


async def login_candidate(db: AsyncSession, email: str) -> LoginCandidate | None:
    row = (
        await db.execute(
            select(
                USERS.c.id, USERS.c.status, CREDENTIALS.c.password_hash, CREDENTIALS.c.locked_until
            )
            .select_from(USERS.outerjoin(CREDENTIALS, CREDENTIALS.c.platform_user_id == USERS.c.id))
            .where(USERS.c.email == email)
        )
    ).one_or_none()
    if row is None:
        return None
    return LoginCandidate(
        row.id, PlatformUserStatus(row.status), row.password_hash, row.locked_until
    )


async def identity(db: AsyncSession, user_id: uuid.UUID) -> PlatformIdentity | None:
    row = (
        await db.execute(
            select(USERS.c.display_name, USERS.c.email, USERS.c.status).where(USERS.c.id == user_id)
        )
    ).one_or_none()
    if row is None:
        return None
    return PlatformIdentity(row.display_name, row.email, PlatformUserStatus(row.status))


async def roles_of(db: AsyncSession, user_id: uuid.UUID) -> frozenset[PlatformRole]:
    codes = await db.scalars(select(ROLES.c.role_code).where(ROLES.c.platform_user_id == user_id))
    return frozenset(PlatformRole(code) for code in codes)


async def record_failed_login(db: AsyncSession, user_id: uuid.UUID, now: datetime) -> int:
    """Count one failure unless the account is locked; the new count (0 if locked)."""
    count = (
        await db.execute(
            update(CREDENTIALS)
            .where(CREDENTIALS.c.platform_user_id == user_id)
            .where((CREDENTIALS.c.locked_until.is_(None)) | (CREDENTIALS.c.locked_until <= now))
            .values(failed_login_count=CREDENTIALS.c.failed_login_count + 1, updated_at=func.now())
            .returning(CREDENTIALS.c.failed_login_count)
        )
    ).scalar_one_or_none()
    return int(count or 0)


async def lock_account(db: AsyncSession, user_id: uuid.UUID, until: datetime) -> None:
    await db.execute(
        update(CREDENTIALS)
        .where(CREDENTIALS.c.platform_user_id == user_id)
        .values(locked_until=until, updated_at=func.now())
    )


async def record_successful_password(
    db: AsyncSession, user_id: uuid.UUID, new_hash: str | None
) -> None:
    values: dict[str, object] = {
        "failed_login_count": 0,
        "locked_until": None,
        "updated_at": func.now(),
    }
    if new_hash is not None:
        values["password_hash"] = new_hash
    await db.execute(
        update(CREDENTIALS).where(CREDENTIALS.c.platform_user_id == user_id).values(**values)
    )


async def set_password(
    db: AsyncSession, user_id: uuid.UUID, password_hash: str, now: datetime
) -> int:
    result = await db.execute(
        update(CREDENTIALS)
        .where(CREDENTIALS.c.platform_user_id == user_id)
        .values(
            password_hash=password_hash,
            password_changed_at=now,
            failed_login_count=0,
            locked_until=None,
            updated_at=func.now(),
        )
    )
    return _rowcount(result)


# --- Sessions --------------------------------------------------------------------------------

_SESSION_COLUMNS = (
    SESSIONS.c.id,
    SESSIONS.c.platform_user_id,
    SESSIONS.c.mfa_verified_at,
    SESSIONS.c.mfa_failed_attempts,
    SESSIONS.c.last_seen_at,
    SESSIONS.c.idle_expires_at,
    SESSIONS.c.absolute_expires_at,
    SESSIONS.c.revoked_at,
)


async def session_by_token_hash(db: AsyncSession, token_hash: str) -> SessionRow | None:
    row = (
        await db.execute(select(*_SESSION_COLUMNS).where(SESSIONS.c.token_hash == token_hash))
    ).one_or_none()
    return SessionRow(*row) if row else None


async def create_session(
    db: AsyncSession,
    *,
    token_hash: str,
    user_id: uuid.UUID,
    mfa_verified_at: datetime | None,
    now: datetime,
    idle_expires_at: datetime,
    absolute_expires_at: datetime,
    ip: str | None,
    user_agent: str | None,
) -> uuid.UUID:
    session_id = new_id()
    await db.execute(
        insert(SESSIONS).values(
            id=session_id,
            token_hash=token_hash,
            platform_user_id=user_id,
            mfa_verified_at=mfa_verified_at,
            last_seen_at=now,
            idle_expires_at=idle_expires_at,
            absolute_expires_at=absolute_expires_at,
            ip=ip,
            user_agent=(user_agent or "")[:256] or None,
        )
    )
    return session_id


async def touch_session(
    db: AsyncSession, session_id: uuid.UUID, *, now: datetime, idle_expires_at: datetime
) -> None:
    await db.execute(
        update(SESSIONS)
        .where(SESSIONS.c.id == session_id, SESSIONS.c.revoked_at.is_(None))
        .values(last_seen_at=now, idle_expires_at=idle_expires_at, updated_at=func.now())
    )


async def mark_mfa_verified(db: AsyncSession, session_id: uuid.UUID, now: datetime) -> int:
    """Step-up: the session completed MFA again now (D6-5)."""
    result = await db.execute(
        update(SESSIONS)
        .where(
            SESSIONS.c.id == session_id,
            SESSIONS.c.revoked_at.is_(None),
            SESSIONS.c.mfa_verified_at.is_not(None),
        )
        .values(mfa_verified_at=now, mfa_failed_attempts=0, updated_at=func.now())
    )
    return _rowcount(result)


async def record_mfa_failure(db: AsyncSession, session_id: uuid.UUID) -> int:
    count = (
        await db.execute(
            update(SESSIONS)
            .where(SESSIONS.c.id == session_id, SESSIONS.c.revoked_at.is_(None))
            .values(mfa_failed_attempts=SESSIONS.c.mfa_failed_attempts + 1, updated_at=func.now())
            .returning(SESSIONS.c.mfa_failed_attempts)
        )
    ).scalar_one_or_none()
    return int(count or 0)


async def revoke_session(
    db: AsyncSession, session_id: uuid.UUID, reason: PlatformSessionRevokeReason, now: datetime
) -> int:
    result = await db.execute(
        update(SESSIONS)
        .where(SESSIONS.c.id == session_id, SESSIONS.c.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason=reason.value, updated_at=func.now())
    )
    return _rowcount(result)


async def revoke_user_sessions(
    db: AsyncSession, user_id: uuid.UUID, reason: PlatformSessionRevokeReason, now: datetime
) -> int:
    result = await db.execute(
        update(SESSIONS)
        .where(SESSIONS.c.platform_user_id == user_id, SESSIONS.c.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason=reason.value, updated_at=func.now())
    )
    return _rowcount(result)


# --- Password reset tokens ---------------------------------------------------------------


async def replace_reset_token(
    db: AsyncSession, user_id: uuid.UUID, token_hash: str, *, now: datetime, expires_at: datetime
) -> None:
    """Invalidate the user's open reset tokens and store a new one."""
    await db.execute(
        update(RESET_TOKENS)
        .where(
            RESET_TOKENS.c.platform_user_id == user_id,
            RESET_TOKENS.c.used_at.is_(None),
            RESET_TOKENS.c.invalidated_at.is_(None),
        )
        .values(invalidated_at=now, updated_at=func.now())
    )
    await db.execute(
        insert(RESET_TOKENS).values(
            id=new_id(),
            platform_user_id=user_id,
            token_hash=token_hash,
            created_at=now,
            expires_at=expires_at,
        )
    )


async def reset_token_by_hash(db: AsyncSession, token_hash: str) -> ResetTokenRow | None:
    row = (
        await db.execute(
            select(
                RESET_TOKENS.c.id,
                RESET_TOKENS.c.platform_user_id,
                RESET_TOKENS.c.expires_at,
                RESET_TOKENS.c.used_at,
                RESET_TOKENS.c.invalidated_at,
            ).where(RESET_TOKENS.c.token_hash == token_hash)
        )
    ).one_or_none()
    return ResetTokenRow(*row) if row else None


async def consume_reset_token(db: AsyncSession, token_id: uuid.UUID, now: datetime) -> int:
    """Mark the token used if it is still open and unexpired (single use)."""
    result = await db.execute(
        update(RESET_TOKENS)
        .where(
            RESET_TOKENS.c.id == token_id,
            RESET_TOKENS.c.used_at.is_(None),
            RESET_TOKENS.c.invalidated_at.is_(None),
            RESET_TOKENS.c.expires_at > now,
        )
        .values(used_at=now, updated_at=func.now())
    )
    return _rowcount(result)
