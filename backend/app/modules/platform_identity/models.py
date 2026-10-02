"""Platform identity, credentials, roles, sessions and MFA tables (T01-06; ADR-0005, ADR-0010).

The platform realm has its own identity store, never linked to ``users``
(the same email may exist in both realms):

* ``platform_users`` — identity (email, display name, status);
* ``platform_user_credentials`` — 1:1, the Argon2id hash and lockout counters;
* ``platform_user_roles`` — the seven fixed role codes (permissions come from
  the code map in :mod:`app.modules.platform_identity.roles`);
* ``platform_sessions`` — opaque sessions stored as HMACs. A session without
  ``mfa_verified_at`` is **MFA-pending** (5 minutes, no permissions);
* ``platform_mfa_factors`` / ``platform_recovery_codes`` — TOTP factors with
  encrypted secrets and single-use recovery codes stored as HMACs;
* ``platform_password_reset_tokens`` — single-use reset tokens (HMAC).

Row-Level Security, grants and the pre-authentication lookup keys are in
migration ``0006``. Nothing is hard-deleted except role assignments.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin
from app.modules.identity.domain import EMAIL_MAX_LENGTH
from app.modules.identity.models import MFA_KINDS, SECRET_CIPHERTEXT_LENGTH, TOKEN_HASH_LENGTH
from app.modules.identity.tokens import TOKEN_HASH_PATTERN
from app.modules.platform_identity.domain import (
    PlatformSessionRevokeReason,
    PlatformUserStatus,
)
from app.modules.platform_identity.roles import PlatformRole


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _platform_user() -> ForeignKey:
    return ForeignKey("platform_users.id", ondelete="RESTRICT")


class PlatformUser(UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "platform_users"
    __table_args__ = (
        UniqueConstraint("email"),
        CheckConstraint("email = lower(btrim(email)) AND email LIKE '%_@_%'", name="email"),
        CheckConstraint("btrim(display_name) <> ''", name="display_name"),
        CheckConstraint(_in("status", [s.value for s in PlatformUserStatus]), name="status"),
    )

    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)


class PlatformUserCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "platform_user_credentials"
    __table_args__ = (
        UniqueConstraint("platform_user_id"),
        CheckConstraint("failed_login_count >= 0", name="failed_login_count"),
    )

    platform_user_id: Mapped[uuid.UUID] = mapped_column(_platform_user(), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    failed_login_count: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default=text("0")
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlatformUserRole(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "platform_user_roles"
    __table_args__ = (
        UniqueConstraint("platform_user_id", "role_code"),
        CheckConstraint(_in("role_code", [r.value for r in PlatformRole]), name="role_code"),
    )

    platform_user_id: Mapped[uuid.UUID] = mapped_column(_platform_user(), nullable=False)
    role_code: Mapped[str] = mapped_column(String(32), nullable=False)


class PlatformSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "platform_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash"),
        CheckConstraint(f"token_hash ~ '{TOKEN_HASH_PATTERN}'", name="token_hash"),
        CheckConstraint(
            _in("revoke_reason", [r.value for r in PlatformSessionRevokeReason]),
            name="revoke_reason",
        ),
        CheckConstraint("(revoked_at IS NULL) = (revoke_reason IS NULL)", name="revocation"),
        CheckConstraint("mfa_failed_attempts >= 0", name="mfa_failed_attempts"),
        Index(
            "ix_platform_sessions_platform_user_id_live",
            "platform_user_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    token_hash: Mapped[str] = mapped_column(String(TOKEN_HASH_LENGTH), nullable=False)
    platform_user_id: Mapped[uuid.UUID] = mapped_column(_platform_user(), nullable=False)
    mfa_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mfa_failed_attempts: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default=text("0")
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(32))
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(256))


class PlatformMfaFactor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "platform_mfa_factors"
    __table_args__ = (
        CheckConstraint(_in("kind", list(MFA_KINDS)), name="kind"),
        CheckConstraint("(disabled_at IS NULL) = (disabled_reason IS NULL)", name="disabled"),
        Index(
            "uq_platform_mfa_factors_platform_user_id_live",
            "platform_user_id",
            unique=True,
            postgresql_where=text("disabled_at IS NULL"),
        ),
    )

    platform_user_id: Mapped[uuid.UUID] = mapped_column(_platform_user(), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    secret_ciphertext: Mapped[str] = mapped_column(String(SECRET_CIPHERTEXT_LENGTH), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_step: Mapped[int | None] = mapped_column(BigInteger)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_reason: Mapped[str | None] = mapped_column(String(32))


class PlatformRecoveryCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "platform_recovery_codes"
    __table_args__ = (
        UniqueConstraint("code_hash"),
        CheckConstraint(f"code_hash ~ '{TOKEN_HASH_PATTERN}'", name="code_hash"),
        Index(
            "ix_platform_recovery_codes_platform_user_id_open",
            "platform_user_id",
            postgresql_where=text("used_at IS NULL AND invalidated_at IS NULL"),
        ),
    )

    platform_user_id: Mapped[uuid.UUID] = mapped_column(_platform_user(), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(TOKEN_HASH_LENGTH), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlatformPasswordResetToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "platform_password_reset_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash"),
        CheckConstraint(f"token_hash ~ '{TOKEN_HASH_PATTERN}'", name="token_hash"),
        Index(
            "ix_platform_password_reset_tokens_platform_user_id_open",
            "platform_user_id",
            postgresql_where=text("used_at IS NULL AND invalidated_at IS NULL"),
        ),
    )

    platform_user_id: Mapped[uuid.UUID] = mapped_column(_platform_user(), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(TOKEN_HASH_LENGTH), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
