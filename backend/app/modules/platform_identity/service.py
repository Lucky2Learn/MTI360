"""Platform authentication, sessions and MFA (T01-06; ADR-0005, ADR-0010, D6-1 … D6-5).

Same discipline as the tenant realm (T01-04 D01/D02): short sequential
transactions, password hashing outside them, generic failures, dummy-hash
timing, Redis rate limits (``auth:platform`` namespace) and the database
lockout. On top of it, MFA is **mandatory**:

1. A correct password creates an **MFA-pending** session (5 minutes, no
   permissions). It may only enrol (no confirmed factor yet), verify a TOTP
   code, use a recovery code, or sign out.
2. MFA success **rotates** the session (the pending one is revoked) and
   records ``mfa_verified_at``; only then are the platform permissions
   loaded from the user's roles (T01-05 code map).
3. Step-up (D6-5) refreshes ``mfa_verified_at`` on the full session.

Wrong codes count on the session (5 → the pending session is revoked) and
toward the credential lockout. A password reset never touches MFA (D6-2).
An MFA reset (D6-3) is the service capability T01-07 exposes.

Nothing logged, audited or returned contains a password, hash, secret, code
or token — except the secret and recovery codes returned **once** to their
owner at enrolment or regeneration.
"""

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Literal, NoReturn, cast

import anyio
from sqlalchemy import Table
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import AuditTarget, record_security_event
from app.core.authz import STEP_UP_WINDOW, authorize, require_fresh_mfa
from app.core.context import current_context
from app.core.errors import (
    AuthenticationRequiredError,
    ConflictError,
    ErrorDetail,
    NotFoundError,
    PermissionDeniedError,
    RateLimitedError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.core.ratelimit import (
    Limit,
    RateLimiter,
    RateLimiterUnavailableError,
    RateLimitExceededError,
)
from app.core.security.encryption import KeyRing
from app.core.security.mfa import Enrolment, MfaAlreadyEnabledError, MfaStore
from app.integrations.email import EmailMessage, EmailSender
from app.modules.identity.domain import (
    ACCOUNT_LIMIT_ATTEMPTS,
    ACCOUNT_LIMIT_WINDOW_SECONDS,
    IP_LIMIT_ATTEMPTS,
    IP_LIMIT_WINDOW_SECONDS,
    MFA_PENDING_TTL,
    PASSWORD_MESSAGES,
    PASSWORD_RESET_TTL,
    InvalidEmailError,
    lockout_duration,
    normalize_email,
    password_problem,
)
from app.modules.identity.passwords import PasswordHasher, common_passwords
from app.modules.identity.tokens import (
    TokenPurpose,
    csrf_token,
    is_well_formed,
    new_token,
    token_hash,
)
from app.modules.platform_identity import events
from app.modules.platform_identity import repository as repo
from app.modules.platform_identity.domain import (
    MFA_RESET_REASON_MAX_LENGTH,
    PlatformSessionRevokeReason,
    PlatformUserStatus,
)
from app.modules.platform_identity.lookup import (
    PlatformLookupKey,
    mfa_reset_transaction,
    platform_lookup_transaction,
    platform_subject_transaction,
)
from app.modules.platform_identity.models import PlatformMfaFactor, PlatformRecoveryCode
from app.modules.platform_identity.permissions import PLATFORM_USER_UPDATE
from app.modules.platform_identity.roles import PlatformRole, platform_permissions
from app.modules.platform_identity.templates import (
    platform_password_reset_email,
    platform_reset_link,
)

IP_LIMIT = Limit(IP_LIMIT_ATTEMPTS, IP_LIMIT_WINDOW_SECONDS)
ACCOUNT_LIMIT = Limit(ACCOUNT_LIMIT_ATTEMPTS, ACCOUNT_LIMIT_WINDOW_SECONDS)
MFA_SESSION_ATTEMPTS: Final = 5
"""Wrong codes a session may submit before it is revoked."""
TOUCH_INTERVAL: Final = timedelta(seconds=60)
RECOVERY_CODE_PURPOSE: Final = "platform_recovery_code"
RATE_LIMIT_NAMESPACE: Final = "auth:platform"
"""Redis key namespace of platform authentication limits (separate from ``auth``)."""

PlatformStatus = Literal["authenticated", "mfa_required", "mfa_enrolment_required"]

INVALID_CODE = ValidationFailedError(
    details=[
        ErrorDetail(
            field="code",
            code="mfa_code_invalid",
            message="That code didn't work. Check your authenticator app and try again.",
        )
    ]
)


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class PlatformIdentityConfig:
    session_secret: str
    csrf_secret: str
    idle_timeout: timedelta
    absolute_timeout: timedelta
    app_base_url: str
    reset_response_floor_seconds: float = 0.5


@dataclass(frozen=True, slots=True)
class PlatformRequestInfo:
    request_id: uuid.UUID
    ip: str
    user_agent: str | None


@dataclass(frozen=True, slots=True)
class ResolvedPlatformSession:
    """A valid platform session, re-validated for this request (guard → handlers)."""

    session_id: uuid.UUID
    user_id: uuid.UUID
    mfa_verified_at: datetime | None
    roles: frozenset[PlatformRole]

    @property
    def mfa_pending(self) -> bool:
        return self.mfa_verified_at is None

    @property
    def permissions(self) -> frozenset[str]:
        """Platform permissions; none until MFA is complete."""
        return frozenset() if self.mfa_pending else platform_permissions(self.roles)


@dataclass(frozen=True, slots=True)
class PlatformSessionView:
    status: PlatformStatus
    display_name: str | None
    email: str | None
    permissions: tuple[str, ...]
    roles: tuple[str, ...]
    mfa_enrolled: bool
    mfa_verified_at: datetime | None
    step_up_expires_at: datetime | None
    recovery_codes_remaining: int | None
    csrf_token: str


@dataclass(frozen=True, slots=True)
class IssuedPlatformSession:
    token: str
    view: PlatformSessionView


@dataclass(frozen=True, slots=True)
class MfaResetResult:
    factors_disabled: int
    sessions_revoked: int


class PlatformIdentityService:
    def __init__(
        self,
        *,
        factory: async_sessionmaker[AsyncSession],
        config: PlatformIdentityConfig,
        hasher: PasswordHasher,
        rate_limiter: RateLimiter,
        email_sender: EmailSender,
        keyring: KeyRing,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._factory = factory
        self.config = config
        self.hasher = hasher
        self.rate_limiter = rate_limiter
        self.email_sender = email_sender
        self.keyring = keyring
        self._clock = clock
        self.mfa = MfaStore(
            cast(Table, PlatformMfaFactor.__table__),
            cast(Table, PlatformRecoveryCode.__table__),
            "platform_user_id",
            config.session_secret,
            RECOVERY_CODE_PURPOSE,
        )

    # --- helpers ------------------------------------------------------------------------

    def _hash(self, purpose: TokenPurpose, token: str) -> str:
        return token_hash(self.config.session_secret, purpose, token)

    def csrf_token(self, session_id: uuid.UUID) -> str:
        return csrf_token(self.config.csrf_secret, session_id)

    async def _limit(self, kind: str, action: str, identifier: str) -> None:
        limit = IP_LIMIT if kind == "ip" else ACCOUNT_LIMIT
        try:
            await self.rate_limiter.hit(kind, action, identifier, limit)
        except RateLimitExceededError as exceeded:
            record_security_event(events.RATE_LIMITED, metadata={"kind": kind, "action": action})
            raise RateLimitedError(retry_after=exceeded.retry_after) from None
        except RateLimiterUnavailableError:
            raise ServiceUnavailableError() from None

    async def _view(
        self, db: AsyncSession, session_id: uuid.UUID, resolved: ResolvedPlatformSession
    ) -> PlatformSessionView:
        enrolled = await self.mfa.enabled(db, resolved.user_id)
        csrf = self.csrf_token(session_id)
        if resolved.mfa_pending:
            status: PlatformStatus = "mfa_required" if enrolled else "mfa_enrolment_required"
            return PlatformSessionView(status, None, None, (), (), enrolled, None, None, None, csrf)
        person = await repo.identity(db, resolved.user_id)
        if person is None:
            raise AuthenticationRequiredError()
        verified = resolved.mfa_verified_at
        return PlatformSessionView(
            status="authenticated",
            display_name=person.display_name,
            email=person.email,
            permissions=tuple(sorted(resolved.permissions)),
            roles=tuple(sorted(role.value for role in resolved.roles)),
            mfa_enrolled=enrolled,
            mfa_verified_at=verified,
            step_up_expires_at=verified + STEP_UP_WINDOW if verified else None,
            recovery_codes_remaining=await self.mfa.remaining_codes(db, resolved.user_id),
            csrf_token=csrf,
        )

    async def _issue(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        roles: frozenset[PlatformRole],
        mfa_verified_at: datetime | None,
        info: PlatformRequestInfo,
    ) -> IssuedPlatformSession:
        now = self._clock()
        token = new_token()
        if mfa_verified_at is None:  # pending: short, fixed lifetime
            idle = absolute = now + MFA_PENDING_TTL
        else:
            absolute = now + self.config.absolute_timeout
            idle = min(now + self.config.idle_timeout, absolute)
        session_id = await repo.create_session(
            db,
            token_hash=self._hash(TokenPurpose.PLATFORM_SESSION, token),
            user_id=user_id,
            mfa_verified_at=mfa_verified_at,
            now=now,
            idle_expires_at=idle,
            absolute_expires_at=absolute,
            ip=info.ip,
            user_agent=info.user_agent,
        )
        resolved = ResolvedPlatformSession(session_id, user_id, mfa_verified_at, roles)
        return IssuedPlatformSession(token, await self._view(db, session_id, resolved))

    async def _revoke_presented(self, token: str | None, info: PlatformRequestInfo) -> None:
        if not token or not is_well_formed(token):
            return
        key = PlatformLookupKey.session_token_hash(self._hash(TokenPurpose.PLATFORM_SESSION, token))
        async with platform_lookup_transaction(
            self._factory, request_id=info.request_id, key=key
        ) as db:
            row = await repo.session_by_token_hash(db, key.value)
            if row is not None and await repo.revoke_session(
                db, row.id, PlatformSessionRevokeReason.ROTATED, self._clock()
            ):
                record_security_event(
                    events.SESSION_ROTATED, target=AuditTarget("platform_session", row.id)
                )

    # --- sign-in (password step) ----------------------------------------------------------

    async def login(
        self, raw_email: str, password: str, info: PlatformRequestInfo, presented: str | None
    ) -> IssuedPlatformSession:
        """Verify the password and open an MFA-pending session. Failures: one generic 401."""
        await self._limit("ip", "login", info.ip)
        try:
            email: str | None = normalize_email(raw_email)
        except InvalidEmailError:
            email = None
        candidate: repo.LoginCandidate | None = None
        if email is not None:
            await self._limit("account", "login", email)
            async with platform_lookup_transaction(
                self._factory, request_id=info.request_id, key=PlatformLookupKey.email(email)
            ) as db:
                candidate = await repo.login_candidate(db, email)

        password_hash = candidate.password_hash if candidate else None
        verified = await self.hasher.verify(password_hash, password)  # dummy hash if unknown
        now = self._clock()
        locked = bool(candidate and candidate.locked_until and candidate.locked_until > now)
        if (
            candidate is None
            or email is None
            or not verified
            or locked
            or candidate.status is not PlatformUserStatus.ACTIVE
        ):
            await self._login_failed(email, candidate, verified=verified, locked=locked, info=info)
            raise AuthenticationRequiredError()

        new_hash = (
            await self.hasher.hash(password)
            if password_hash and self.hasher.needs_rehash(password_hash)
            else None
        )
        await self._revoke_presented(presented, info)
        async with platform_subject_transaction(
            self._factory, request_id=info.request_id, user_id=candidate.user_id
        ) as db:
            await repo.record_successful_password(db, candidate.user_id, new_hash)
            issued = await self._issue(
                db, user_id=candidate.user_id, roles=frozenset(), mfa_verified_at=None, info=info
            )
        record_security_event(
            events.MFA_CHALLENGED,
            target=AuditTarget("platform_user", candidate.user_id),
            metadata={"enrolment_required": issued.view.status == "mfa_enrolment_required"},
        )
        return issued

    async def _login_failed(
        self,
        email: str | None,
        candidate: repo.LoginCandidate | None,
        *,
        verified: bool,
        locked: bool,
        info: PlatformRequestInfo,
    ) -> None:
        reason = "unknown_account"
        if candidate is not None:
            if locked:
                reason = "locked"
            elif candidate.status is not PlatformUserStatus.ACTIVE:
                reason = "inactive"
            elif candidate.password_hash is None:
                reason = "no_credential"
            else:
                reason = "bad_password"
        if reason == "bad_password" and email is not None and candidate is not None:
            async with platform_lookup_transaction(
                self._factory, request_id=info.request_id, key=PlatformLookupKey.email(email)
            ) as db:
                await self._count_failure(db, candidate.user_id)
        record_security_event(
            events.LOGIN_FAILED,
            target=AuditTarget("platform_user", candidate.user_id) if candidate else None,
            metadata={"reason": reason},
        )

    async def _count_failure(self, db: AsyncSession, user_id: uuid.UUID) -> None:
        """One credential failure (password or MFA code); locks per the T01-04 schedule."""
        now = self._clock()
        count = await repo.record_failed_login(db, user_id, now)
        duration = lockout_duration(count)
        if duration is not None:
            await repo.lock_account(db, user_id, now + duration)
            record_security_event(
                events.ACCOUNT_LOCKED,
                target=AuditTarget("platform_user", user_id),
                metadata={"minutes": int(duration.total_seconds() // 60)},
            )

    # --- session resolution (every request) ---------------------------------------------

    async def resolve(
        self, token: str | None, info: PlatformRequestInfo
    ) -> ResolvedPlatformSession:
        if not token or not is_well_formed(token):
            raise AuthenticationRequiredError()
        key = PlatformLookupKey.session_token_hash(self._hash(TokenPurpose.PLATFORM_SESSION, token))
        async with platform_lookup_transaction(
            self._factory, request_id=info.request_id, key=key
        ) as db:
            row = await repo.session_by_token_hash(db, key.value)
        now = self._clock()
        if (
            row is None
            or row.revoked_at is not None
            or row.idle_expires_at <= now
            or row.absolute_expires_at <= now
        ):
            raise AuthenticationRequiredError()
        async with platform_subject_transaction(
            self._factory, request_id=info.request_id, user_id=row.user_id
        ) as db:
            person = await repo.identity(db, row.user_id)
            if person is None or person.status is not PlatformUserStatus.ACTIVE:
                raise AuthenticationRequiredError()
            roles = await repo.roles_of(db, row.user_id)
            if row.mfa_verified_at is not None and now - row.last_seen_at >= TOUCH_INTERVAL:
                idle = min(now + self.config.idle_timeout, row.absolute_expires_at)
                await repo.touch_session(db, row.id, now=now, idle_expires_at=idle)
        return ResolvedPlatformSession(row.id, row.user_id, row.mfa_verified_at, roles)

    async def view(
        self, resolved: ResolvedPlatformSession, info: PlatformRequestInfo
    ) -> PlatformSessionView:
        async with platform_subject_transaction(
            self._factory, request_id=info.request_id, user_id=resolved.user_id
        ) as db:
            return await self._view(db, resolved.session_id, resolved)

    # --- MFA step (pending session) -----------------------------------------------------------

    async def start_enrolment(
        self, resolved: ResolvedPlatformSession, info: PlatformRequestInfo
    ) -> Enrolment:
        """A new TOTP secret for a user without a confirmed factor (returned once)."""
        async with platform_subject_transaction(
            self._factory, request_id=info.request_id, user_id=resolved.user_id
        ) as db:
            person = await repo.identity(db, resolved.user_id)
            if person is None:
                raise AuthenticationRequiredError()
            try:
                enrolment = await self.mfa.start_enrolment(
                    db,
                    resolved.user_id,
                    keyring=self.keyring,
                    account=person.email,
                    now=self._clock(),
                )
            except MfaAlreadyEnabledError:
                raise ConflictError("Multi-factor authentication is already set up.") from None
        record_security_event(
            events.MFA_ENROLMENT_STARTED, target=AuditTarget("platform_user", resolved.user_id)
        )
        return enrolment

    async def confirm_enrolment(
        self, resolved: ResolvedPlatformSession, code: str, info: PlatformRequestInfo
    ) -> tuple[IssuedPlatformSession, list[str]]:
        """Confirm the factor with a first code; rotate to a full session; codes once."""
        await self._limit("account", "mfa", str(resolved.user_id))
        async with platform_subject_transaction(
            self._factory, request_id=info.request_id, user_id=resolved.user_id
        ) as db:
            codes = await self.mfa.confirm_enrolment(
                db, resolved.user_id, code, keyring=self.keyring, now=self._clock()
            )
        if codes is None:
            await self._mfa_failed(resolved, info, stage="enrolment")
        record_security_event(
            events.MFA_ENROLLED, target=AuditTarget("platform_user", resolved.user_id)
        )
        return await self._complete(resolved, info, method="enrolment"), codes

    async def verify_mfa(
        self, resolved: ResolvedPlatformSession, code: str, info: PlatformRequestInfo
    ) -> IssuedPlatformSession:
        await self._limit("account", "mfa", str(resolved.user_id))
        async with platform_subject_transaction(
            self._factory, request_id=info.request_id, user_id=resolved.user_id
        ) as db:
            ok = await self.mfa.verify_totp(
                db, resolved.user_id, code, keyring=self.keyring, now=self._clock()
            )
        if not ok:
            await self._mfa_failed(resolved, info, stage="totp")
        return await self._complete(resolved, info, method="totp")

    async def use_recovery_code(
        self, resolved: ResolvedPlatformSession, code: str, info: PlatformRequestInfo
    ) -> IssuedPlatformSession:
        await self._limit("account", "mfa", str(resolved.user_id))
        async with platform_subject_transaction(
            self._factory, request_id=info.request_id, user_id=resolved.user_id
        ) as db:
            ok = await self.mfa.use_recovery_code(db, resolved.user_id, code, now=self._clock())
            remaining = await self.mfa.remaining_codes(db, resolved.user_id)
        if not ok:
            await self._mfa_failed(resolved, info, stage="recovery_code")
        record_security_event(
            events.RECOVERY_CODE_USED,
            target=AuditTarget("platform_user", resolved.user_id),
            metadata={"remaining": remaining},
        )
        return await self._complete(resolved, info, method="recovery_code")

    async def _mfa_failed(
        self, resolved: ResolvedPlatformSession, info: PlatformRequestInfo, *, stage: str
    ) -> NoReturn:
        """Count the failure on the session and the credential; always raises."""
        async with platform_subject_transaction(
            self._factory, request_id=info.request_id, user_id=resolved.user_id
        ) as db:
            attempts = await repo.record_mfa_failure(db, resolved.session_id)
            await self._count_failure(db, resolved.user_id)
            revoked = attempts >= MFA_SESSION_ATTEMPTS and bool(
                await repo.revoke_session(
                    db, resolved.session_id, PlatformSessionRevokeReason.MFA_FAILED, self._clock()
                )
            )
        record_security_event(
            events.STEP_UP_FAILED if not resolved.mfa_pending else events.MFA_FAILED,
            target=AuditTarget("platform_user", resolved.user_id),
            metadata={"stage": stage, "attempts": attempts},
        )
        if revoked:
            record_security_event(
                events.SESSION_REVOKED,
                target=AuditTarget("platform_session", resolved.session_id),
                metadata={"reason": "mfa_failed"},
            )
            raise AuthenticationRequiredError()
        raise INVALID_CODE

    async def _complete(
        self, resolved: ResolvedPlatformSession, info: PlatformRequestInfo, *, method: str
    ) -> IssuedPlatformSession:
        """MFA done: revoke the pending session and issue a full one (rotation)."""
        now = self._clock()
        async with platform_subject_transaction(
            self._factory, request_id=info.request_id, user_id=resolved.user_id
        ) as db:
            if not await repo.revoke_session(
                db, resolved.session_id, PlatformSessionRevokeReason.ROTATED, now
            ):
                raise AuthenticationRequiredError()  # raced with another completion
            roles = await repo.roles_of(db, resolved.user_id)
            issued = await self._issue(
                db, user_id=resolved.user_id, roles=roles, mfa_verified_at=now, info=info
            )
        target = AuditTarget("platform_user", resolved.user_id)
        record_security_event(events.MFA_VERIFIED, target=target, metadata={"method": method})
        record_security_event(
            events.SESSION_ROTATED, target=AuditTarget("platform_session", resolved.session_id)
        )
        record_security_event(events.LOGIN_SUCCESS, target=target)
        return issued

    # --- full session: step-up and recovery codes --------------------------------------------

    async def step_up(
        self, resolved: ResolvedPlatformSession, code: str, info: PlatformRequestInfo
    ) -> PlatformSessionView:
        """Re-verify TOTP on a full session: refreshes the step-up window (D6-5)."""
        await self._limit("account", "mfa", str(resolved.user_id))
        now = self._clock()
        async with platform_subject_transaction(
            self._factory, request_id=info.request_id, user_id=resolved.user_id
        ) as db:
            ok = await self.mfa.verify_totp(
                db, resolved.user_id, code, keyring=self.keyring, now=now
            )
            if ok and not await repo.mark_mfa_verified(db, resolved.session_id, now):
                raise AuthenticationRequiredError()
        if not ok:
            await self._mfa_failed(resolved, info, stage="step_up")
        record_security_event(
            events.STEP_UP_SUCCEEDED, target=AuditTarget("platform_user", resolved.user_id)
        )
        refreshed = ResolvedPlatformSession(
            resolved.session_id, resolved.user_id, now, resolved.roles
        )
        return await self.view(refreshed, info)

    async def regenerate_recovery_codes(
        self, resolved: ResolvedPlatformSession, info: PlatformRequestInfo
    ) -> list[str]:
        """New recovery codes (old ones invalidated); needs a fresh step-up."""
        require_fresh_mfa(current_context())
        async with platform_subject_transaction(
            self._factory, request_id=info.request_id, user_id=resolved.user_id
        ) as db:
            if not await self.mfa.enabled(db, resolved.user_id):
                raise ConflictError("Multi-factor authentication is not set up.")
            codes = await self.mfa.replace_recovery_codes(db, resolved.user_id, now=self._clock())
        record_security_event(
            events.RECOVERY_CODES_REGENERATED, target=AuditTarget("platform_user", resolved.user_id)
        )
        return codes

    # --- sign-out ---------------------------------------------------------------------------

    async def logout(self, token: str | None, info: PlatformRequestInfo) -> None:
        if not token or not is_well_formed(token):
            return
        key = PlatformLookupKey.session_token_hash(self._hash(TokenPurpose.PLATFORM_SESSION, token))
        async with platform_lookup_transaction(
            self._factory, request_id=info.request_id, key=key
        ) as db:
            row = await repo.session_by_token_hash(db, key.value)
            if row is not None and await repo.revoke_session(
                db, row.id, PlatformSessionRevokeReason.LOGOUT, self._clock()
            ):
                record_security_event(events.LOGOUT, target=AuditTarget("platform_session", row.id))

    # --- password reset (D6-2) ----------------------------------------------------------------

    async def request_password_reset(
        self, raw_email: str, info: PlatformRequestInfo
    ) -> EmailMessage | None:
        """Issue a reset token if the account can use one; always looks the same."""
        started = time.monotonic()
        await self._limit("ip", "recovery", info.ip)
        message: EmailMessage | None = None
        try:
            email: str | None = normalize_email(raw_email)
        except InvalidEmailError:
            email = None
        if email is not None:
            await self._limit("account", "recovery", email)
            async with platform_lookup_transaction(
                self._factory, request_id=info.request_id, key=PlatformLookupKey.email(email)
            ) as db:
                candidate = await repo.login_candidate(db, email)
            if (
                candidate is not None
                and candidate.status is PlatformUserStatus.ACTIVE
                and candidate.password_hash is not None
            ):
                token = new_token()
                now = self._clock()
                async with platform_subject_transaction(
                    self._factory, request_id=info.request_id, user_id=candidate.user_id
                ) as db:
                    await repo.replace_reset_token(
                        db,
                        candidate.user_id,
                        self._hash(TokenPurpose.PLATFORM_PASSWORD_RESET, token),
                        now=now,
                        expires_at=now + PASSWORD_RESET_TTL,
                    )
                    person = await repo.identity(db, candidate.user_id)
                message = platform_password_reset_email(
                    to=email,
                    display_name=person.display_name if person else "",
                    link=platform_reset_link(self.config.app_base_url, token),
                )
                record_security_event(
                    events.PASSWORD_RESET_REQUESTED,
                    target=AuditTarget("platform_user", candidate.user_id),
                )
            else:
                record_security_event(events.PASSWORD_RESET_REQUESTED)
        remaining = self.config.reset_response_floor_seconds - (time.monotonic() - started)
        if remaining > 0:
            await anyio.sleep(remaining)
        return message

    async def confirm_password_reset(
        self, token: str, password: str, info: PlatformRequestInfo
    ) -> None:
        """New password with a single-use token; signs out everywhere; MFA unchanged."""
        await self._limit("ip", "recovery", info.ip)
        problem = password_problem(password, common_passwords())
        if problem is not None:
            raise ValidationFailedError(
                details=[
                    ErrorDetail(
                        field="new_password", code=problem.value, message=PASSWORD_MESSAGES[problem]
                    )
                ]
            )
        if not is_well_formed(token):
            raise NotFoundError()
        key = PlatformLookupKey.token_hash(self._hash(TokenPurpose.PLATFORM_PASSWORD_RESET, token))
        async with platform_lookup_transaction(
            self._factory, request_id=info.request_id, key=key
        ) as db:
            row = await repo.reset_token_by_hash(db, key.value)
        if (
            row is None
            or row.used_at is not None
            or row.invalidated_at is not None
            or row.expires_at <= self._clock()
        ):
            raise NotFoundError()
        new_hash = await self.hasher.hash(password)
        async with platform_subject_transaction(
            self._factory, request_id=info.request_id, user_id=row.user_id
        ) as db:
            now = self._clock()
            if not await repo.consume_reset_token(db, row.id, now):
                raise NotFoundError()
            person = await repo.identity(db, row.user_id)
            if person is None or person.status is not PlatformUserStatus.ACTIVE:
                raise NotFoundError()
            if not await repo.set_password(db, row.user_id, new_hash, now):
                raise NotFoundError()
            revoked = await repo.revoke_user_sessions(
                db, row.user_id, PlatformSessionRevokeReason.PASSWORD_RESET, now
            )
        target = AuditTarget("platform_user", row.user_id)
        record_security_event(events.PASSWORD_RESET_COMPLETED, target=target)
        if revoked:
            record_security_event(
                events.SESSION_REVOKED,
                target=target,
                metadata={"reason": "password_reset", "session_count": revoked},
            )

    # --- MFA reset for a lost device (D6-3; exposed by T01-07) -----------------------------

    async def reset_mfa(self, target_user_id: uuid.UUID, reason: str) -> MfaResetResult:
        """Disable another platform user's MFA, revoke their sessions, force re-enrolment.

        Requires ``platform_user.update`` with a fresh step-up (enforced by
        ``authorize``) and a reason; audited. Resetting one's own MFA is refused:
        that is the bootstrap CLI's break-glass path (D6-1).
        """
        context = current_context()
        authorize(context, PLATFORM_USER_UPDATE)
        cleaned = " ".join(reason.split())
        if not cleaned or len(cleaned) > MFA_RESET_REASON_MAX_LENGTH:
            raise ValidationFailedError(
                details=[
                    ErrorDetail(
                        field="reason",
                        code="reason_required",
                        message="Give a reason of up to 500 characters.",
                    )
                ]
            )
        if target_user_id == context.principal_id:
            raise PermissionDeniedError()
        now = self._clock()
        async with mfa_reset_transaction(
            self._factory, context=context, target_user_id=target_user_id
        ) as db:
            if await repo.identity(db, target_user_id) is None:
                raise NotFoundError()
            factors = await self.mfa.disable(db, target_user_id, reason="admin_reset", now=now)
            sessions = await repo.revoke_user_sessions(
                db, target_user_id, PlatformSessionRevokeReason.MFA_RESET, now
            )
        record_security_event(
            events.MFA_RESET,
            target=AuditTarget("platform_user", target_user_id),
            metadata={
                "reason": cleaned,
                "factors_disabled": factors,
                "sessions_revoked": sessions,
            },
        )
        return MfaResetResult(factors, sessions)
