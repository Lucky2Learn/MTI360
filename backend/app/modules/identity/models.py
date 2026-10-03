"""Identity, membership, session and recovery tables (T01-04; ADR-0010, ADR-0014).

* ``users`` — one global identity per person (no tenant or campus). The email
  is stored canonical (trimmed, lower-case) and unique.
* ``user_credentials`` — 1:1 with ``users``; the Argon2id hash and the
  lockout counters. Only the authentication services read it.
* ``tenant_memberships`` — a user in a tenant (tenant-owned), with the campus
  scope; ``membership_campuses`` lists the campuses of a ``SELECTED`` scope.
  Composite foreign keys keep membership, campus and tenant consistent.
* ``user_sessions`` — opaque server-side sessions, stored as an HMAC of the
  token. The active tenant must be one of the user's memberships and the
  active campus a campus of that tenant (composite foreign keys).
* ``password_reset_tokens`` / ``user_invitations`` — single-use tokens stored
  as HMACs, with expiry.
* ``user_mfa_factors`` / ``user_recovery_codes`` (T01-06) — optional MFA for
  tenant users: TOTP factors with AES-256-GCM encrypted secrets and
  single-use recovery codes stored as HMACs. A session with ``mfa_pending``
  has passed the password step only.

Credentials and sessions are updated with atomic SQL statements (no version
column), so concurrent requests never fail on optimistic locking. Nothing is
hard-deleted: the runtime roles have no DELETE privilege (migration ``0004``).
Row-Level Security policies are defined in the migration.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin
from app.core.tenancy import TenantScopedMixin, tenant_foreign_key
from app.modules.identity.domain import (
    EMAIL_MAX_LENGTH,
    CampusScope,
    MembershipStatus,
    MfaKind,
    SessionRevokeReason,
    UserStatus,
)
from app.modules.identity.tokens import TOKEN_HASH_PATTERN


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _restrict(target: str) -> ForeignKey:
    return ForeignKey(target, ondelete="RESTRICT")


TOKEN_HASH_LENGTH = 64
SECRET_CIPHERTEXT_LENGTH = 512
MFA_KINDS = tuple(kind.value for kind in MfaKind)


class User(UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email"),
        CheckConstraint("email = lower(btrim(email)) AND email LIKE '%_@_%'", name="email"),
        CheckConstraint("btrim(display_name) <> ''", name="display_name"),
        CheckConstraint(_in("status", [s.value for s in UserStatus]), name="status"),
    )

    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_credentials"
    __table_args__ = (
        UniqueConstraint("user_id"),
        CheckConstraint("failed_login_count >= 0", name="failed_login_count"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(_restrict("users.id"), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    failed_login_count: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default=text("0")
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TenantMembership(TenantScopedMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "tenant_memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "user_id"),
        Index(None, "user_id"),
        CheckConstraint(_in("status", [s.value for s in MembershipStatus]), name="status"),
        CheckConstraint(_in("campus_scope", [s.value for s in CampusScope]), name="campus_scope"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(_restrict("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    campus_scope: Mapped[str] = mapped_column(String(16), nullable=False)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(_restrict("users.id"))
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MembershipCampus(TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "membership_campuses"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("membership_id", "campus_id"),
        tenant_foreign_key(
            "membership_id", "tenant_memberships", name="fk_membership_campuses_membership"
        ),
        tenant_foreign_key("campus_id", "campuses"),
    )

    membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    campus_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    # T01-08: a campus taken out of a SELECTED scope is marked, never deleted (T01-04 D16:
    # no DELETE on identity tables); only rows without ``removed_at`` are permitted campuses.
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash"),
        CheckConstraint(f"token_hash ~ '{TOKEN_HASH_PATTERN}'", name="token_hash"),
        CheckConstraint("realm IN ('tenant')", name="realm"),
        CheckConstraint(
            _in("revoke_reason", [r.value for r in SessionRevokeReason]), name="revoke_reason"
        ),
        CheckConstraint("(revoked_at IS NULL) = (revoke_reason IS NULL)", name="revocation"),
        CheckConstraint(
            "active_campus_id IS NULL OR active_tenant_id IS NOT NULL", name="campus_needs_tenant"
        ),
        CheckConstraint("mfa_failed_attempts >= 0", name="mfa_failed_attempts"),
        CheckConstraint("NOT mfa_pending OR active_tenant_id IS NULL", name="pending_no_tenant"),
        # The active tenant is one of the user's memberships; the active campus
        # belongs to the active tenant. NULL columns skip the check (MATCH SIMPLE).
        ForeignKeyConstraint(
            ["active_tenant_id", "user_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.user_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["active_tenant_id", "active_campus_id"],
            ["campuses.tenant_id", "campuses.id"],
            ondelete="RESTRICT",
        ),
        Index(
            "ix_user_sessions_user_id_live",
            "user_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    token_hash: Mapped[str] = mapped_column(String(TOKEN_HASH_LENGTH), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(_restrict("users.id"), nullable=False)
    realm: Mapped[str] = mapped_column(String(16), nullable=False)
    active_tenant_id: Mapped[uuid.UUID | None] = mapped_column()
    active_campus_id: Mapped[uuid.UUID | None] = mapped_column()
    mfa_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mfa_pending: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default=text("false")
    )
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


class PasswordResetToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash"),
        CheckConstraint(f"token_hash ~ '{TOKEN_HASH_PATTERN}'", name="token_hash"),
        Index(
            "ix_password_reset_tokens_user_id_open",
            "user_id",
            postgresql_where=text("used_at IS NULL AND invalidated_at IS NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(_restrict("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(TOKEN_HASH_LENGTH), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserInvitation(TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "user_invitations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("token_hash"),
        CheckConstraint(f"token_hash ~ '{TOKEN_HASH_PATTERN}'", name="token_hash"),
        tenant_foreign_key("membership_id", "tenant_memberships"),
    )

    membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    token_hash: Mapped[str] = mapped_column(String(TOKEN_HASH_LENGTH), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invited_by: Mapped[uuid.UUID | None] = mapped_column(_restrict("users.id"))


class UserMfaFactor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_mfa_factors"
    __table_args__ = (
        CheckConstraint(_in("kind", list(MFA_KINDS)), name="kind"),
        CheckConstraint("(disabled_at IS NULL) = (disabled_reason IS NULL)", name="disabled"),
        Index(
            "uq_user_mfa_factors_user_id_live",
            "user_id",
            unique=True,
            postgresql_where=text("disabled_at IS NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(_restrict("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    secret_ciphertext: Mapped[str] = mapped_column(String(SECRET_CIPHERTEXT_LENGTH), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_step: Mapped[int | None] = mapped_column(BigInteger)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_reason: Mapped[str | None] = mapped_column(String(32))


class UserRecoveryCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_recovery_codes"
    __table_args__ = (
        UniqueConstraint("code_hash"),
        CheckConstraint(f"code_hash ~ '{TOKEN_HASH_PATTERN}'", name="code_hash"),
        Index(
            "ix_user_recovery_codes_user_id_open",
            "user_id",
            postgresql_where=text("used_at IS NULL AND invalidated_at IS NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(_restrict("users.id"), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(TOKEN_HASH_LENGTH), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
