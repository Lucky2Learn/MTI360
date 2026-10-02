"""Authentication and session services (T01-04).

Every operation follows decision D02: short, sequential transactions, with
password hashing outside any transaction, so no connection is held during the
deliberately slow Argon2 work and a failed sign-in can commit its lockout
counter while the request answers 401.

* Lookups before the subject is known use :func:`lookup_transaction` with one
  pre-authentication key (D01); afterwards :func:`subject_transaction` acts as
  the resolved user (and tenant), under the ordinary RLS policies.
* Session state follows D04 (campus semantics) and is re-validated on every
  request (:meth:`IdentityService.resolve`).
* Responses never reveal whether an email has an account, why a sign-in
  failed, or anything about other tenants. Unusable tokens are a generic 404.
* Security events (``events``) go through the T01-02 buffer; the request
  context at sign-in is anonymous and the user is recorded as the target
  (D13). Nothing logged or audited contains a password, hash or token.
* Optional MFA (T01-06): a user with a confirmed TOTP factor gets an
  **MFA-pending** session after the password (5 minutes, no institute, no
  permissions); a TOTP or recovery code completes sign-in and rotates the
  session. Users without MFA sign in exactly as before.
"""

import logging
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Literal, NoReturn, cast

import anyio
from sqlalchemy import Table
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import AuditTarget, record_security_event
from app.core.errors import (
    AuthenticationRequiredError,
    ConflictError,
    ErrorDetail,
    NotFoundError,
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
from app.modules.access.service import NO_ACCESS, MembershipAccess, RoleSummary, membership_access
from app.modules.identity import events
from app.modules.identity import repository as repo
from app.modules.identity.domain import (
    ACCOUNT_LIMIT_ATTEMPTS,
    ACCOUNT_LIMIT_WINDOW_SECONDS,
    IP_LIMIT_ATTEMPTS,
    IP_LIMIT_WINDOW_SECONDS,
    MFA_PENDING_TTL,
    PASSWORD_MESSAGES,
    PASSWORD_RESET_TTL,
    CampusScope,
    CampusState,
    InvalidEmailError,
    MembershipStatus,
    SessionRevokeReason,
    UserStatus,
    lockout_duration,
    mask_email,
    membership_usable,
    normalize_email,
    password_problem,
    resolve_campus,
)
from app.modules.identity.lookup import LookupKey, lookup_transaction, subject_transaction
from app.modules.identity.models import UserMfaFactor, UserRecoveryCode
from app.modules.identity.passwords import PasswordHasher, common_passwords
from app.modules.identity.templates import password_reset_email, reset_link
from app.modules.identity.tokens import (
    TokenPurpose,
    csrf_token,
    is_well_formed,
    new_token,
    token_hash,
)
from app.modules.tenants.domain import TenantStatus, tenant_access_allowed

logger = logging.getLogger("app.identity")

IP_LIMIT = Limit(IP_LIMIT_ATTEMPTS, IP_LIMIT_WINDOW_SECONDS)
ACCOUNT_LIMIT = Limit(ACCOUNT_LIMIT_ATTEMPTS, ACCOUNT_LIMIT_WINDOW_SECONDS)
TOUCH_INTERVAL = timedelta(seconds=60)
"""``last_seen_at`` / idle expiry are written at most once a minute per session."""
MFA_SESSION_ATTEMPTS = 5
"""Wrong MFA codes a session may submit before it is revoked (T01-06)."""
RECOVERY_CODE_PURPOSE = "tenant_recovery_code"

LoginStatus = Literal[
    "ready", "institute_selection_required", "campus_selection_required", "mfa_required"
]
INVALID_CODE = ValidationFailedError(
    details=[
        ErrorDetail(
            field="code",
            code="mfa_code_invalid",
            message="That code didn't work. Check your authenticator app and try again.",
        )
    ]
)
Account = Literal["new", "existing"]


def utc_now() -> datetime:
    return datetime.now(UTC)


# --- Configuration and request information ---------------------------------------------


@dataclass(frozen=True, slots=True)
class IdentityConfig:
    session_secret: str
    csrf_secret: str
    idle_timeout: timedelta
    absolute_timeout: timedelta
    app_base_url: str
    allowed_origins: frozenset[str]
    reset_response_floor_seconds: float = 0.5
    """Minimum duration of a reset request, so existing and unknown emails look alike."""


@dataclass(frozen=True, slots=True)
class RequestInfo:
    request_id: uuid.UUID
    ip: str
    user_agent: str | None


# --- Views ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Institute:
    id: uuid.UUID
    name: str
    is_trial: bool


@dataclass(frozen=True, slots=True)
class SessionView:
    """What the UI may know about the session (UI contract §15, D04 §2.3)."""

    display_name: str
    email: str
    active_institute: Institute | None
    institutes: tuple[Institute, ...]
    active_campus: repo.CampusView | None
    campus_options: tuple[repo.CampusView, ...]
    all_campuses_allowed: bool
    campus_selection_required: bool
    csrf_token: str
    # Authorization in the active institute (T01-05): sorted effective
    # permission codes and the member's roles; empty without an institute.
    permissions: tuple[str, ...] = ()
    roles: tuple[RoleSummary, ...] = ()
    # MFA (T01-06): the session waits for a code; the user has MFA enabled.
    mfa_required: bool = False
    mfa_enabled: bool = False

    @property
    def status(self) -> LoginStatus:
        if self.mfa_required:
            return "mfa_required"
        if self.active_institute is None:
            return "institute_selection_required"
        if self.campus_selection_required:
            return "campus_selection_required"
        return "ready"


@dataclass(frozen=True, slots=True)
class ResolvedSession:
    """A valid session, re-validated for this request (guard → handlers).

    The authorization fields (T01-05) are resolved with it, server-side: the
    effective permissions in the active tenant, whether the member has
    all-campus access (``campus_scope`` ``ALL``) and the permitted campuses.
    The active campus is a view filter and plays no part in them (D-B1).
    """

    session_id: uuid.UUID
    user_id: uuid.UUID
    tenant_id: uuid.UUID | None
    campus_id: uuid.UUID | None
    campus_selection_required: bool
    permissions: frozenset[str] = frozenset()
    all_campuses: bool = False
    campus_ids: frozenset[uuid.UUID] = frozenset()
    # MFA (T01-06): password step only; when MFA was last verified.
    mfa_pending: bool = False
    mfa_verified_at: datetime | None = None

    @property
    def ready(self) -> bool:
        return (
            self.tenant_id is not None
            and not self.campus_selection_required
            and not self.mfa_pending
        )


@dataclass(frozen=True, slots=True)
class IssuedSession:
    token: str
    view: SessionView


@dataclass(frozen=True, slots=True)
class InvitationPreview:
    institute_name: str
    email_masked: str
    account: Account


@dataclass(frozen=True, slots=True)
class _CampusResolution:
    membership: repo.MembershipView
    options: tuple[repo.CampusView, ...]
    state: CampusState


def _usable_institutes(memberships: Sequence[repo.MembershipView]) -> tuple[Institute, ...]:
    """Memberships that can open an institute (D04 rule 5 approximated by the count)."""
    usable: list[Institute] = []
    for membership in memberships:
        campus_usable = (
            membership.campus_scope is CampusScope.ALL or membership.selected_campus_count > 0
        )
        if (
            membership.status is MembershipStatus.ACTIVE
            and _tenant_accessible(membership.tenant_status)
            and campus_usable
        ):
            usable.append(
                Institute(
                    membership.tenant_id,
                    membership.tenant_name,
                    membership.tenant_status == TenantStatus.TRIAL,
                )
            )
    return tuple(usable)


def _tenant_accessible(status: str) -> bool:
    try:
        return tenant_access_allowed(TenantStatus(status))
    except ValueError:
        return False


class IdentityService:
    def __init__(
        self,
        *,
        factory: async_sessionmaker[AsyncSession],
        config: IdentityConfig,
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
            cast(Table, UserMfaFactor.__table__),
            cast(Table, UserRecoveryCode.__table__),
            "user_id",
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

    async def _campus_resolution(
        self,
        db: AsyncSession,
        memberships: Sequence[repo.MembershipView],
        tenant_id: uuid.UUID,
        current_campus: uuid.UUID | None,
    ) -> _CampusResolution | None:
        """D04 for ``tenant_id``; ``None`` when the membership cannot open it."""
        membership = next((m for m in memberships if m.tenant_id == tenant_id), None)
        if membership is None:
            return None
        options = tuple(
            await repo.permitted_campuses(
                db, tenant_id, membership.membership_id, membership.campus_scope
            )
        )
        state = resolve_campus(membership.campus_scope, [c.id for c in options], current_campus)
        if not membership_usable(
            membership.status, _tenant_accessible(membership.tenant_status), state
        ):
            return None
        return _CampusResolution(membership, options, state)

    async def _access(
        self, db: AsyncSession, resolution: _CampusResolution | None
    ) -> MembershipAccess:
        """Effective permissions and roles in the resolution's tenant (T01-05)."""
        if resolution is None:
            return NO_ACCESS
        membership = resolution.membership
        return await membership_access(
            db,
            tenant_id=membership.tenant_id,
            membership_id=membership.membership_id,
            all_campuses=membership.campus_scope is CampusScope.ALL,
        )

    async def _view(
        self,
        db: AsyncSession,
        *,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        memberships: Sequence[repo.MembershipView],
        resolution: _CampusResolution | None,
    ) -> SessionView:
        identity = await repo.user_identity(db, user_id)
        if identity is None:
            raise AuthenticationRequiredError()
        display_name, email, _ = identity
        institutes = _usable_institutes(memberships)
        active_institute = None
        active_campus = None
        options: tuple[repo.CampusView, ...] = ()
        all_allowed = False
        selection_required = False
        if resolution is not None:
            tenant_id = resolution.membership.tenant_id
            active_institute = next((i for i in institutes if i.id == tenant_id), None)
            options = resolution.options
            state = resolution.state
            active_campus = next((c for c in options if c.id == state.active_campus_id), None)
            all_allowed = state.all_campuses_allowed
            selection_required = state.selection_required
        access = await self._access(db, resolution)
        return SessionView(
            display_name=display_name,
            email=email,
            active_institute=active_institute,
            institutes=institutes,
            active_campus=active_campus,
            campus_options=options,
            all_campuses_allowed=all_allowed,
            campus_selection_required=selection_required,
            csrf_token=self.csrf_token(session_id),
            permissions=access.sorted_permissions,
            roles=access.roles,
            mfa_enabled=await self.mfa.enabled(db, user_id),
        )

    async def _issue(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        memberships: Sequence[repo.MembershipView],
        resolution: _CampusResolution | None,
        info: RequestInfo,
        mfa_verified_at: datetime | None = None,
    ) -> IssuedSession:
        now = self._clock()
        token = new_token()
        session_id = await repo.create_session(
            db,
            token_hash=self._hash(TokenPurpose.SESSION, token),
            user_id=user_id,
            tenant_id=resolution.membership.tenant_id if resolution else None,
            campus_id=resolution.state.active_campus_id if resolution else None,
            now=now,
            idle_expires_at=min(now + self.config.idle_timeout, now + self.config.absolute_timeout),
            absolute_expires_at=now + self.config.absolute_timeout,
            ip=info.ip,
            user_agent=info.user_agent,
            mfa_verified_at=mfa_verified_at,
        )
        view = await self._view(
            db,
            session_id=session_id,
            user_id=user_id,
            memberships=memberships,
            resolution=resolution,
        )
        record_security_event(
            events.SESSION_CREATED, target=AuditTarget("user_session", session_id)
        )
        return IssuedSession(token, view)

    async def _revoke_presented(self, token: str | None, info: RequestInfo) -> None:
        """End the session whose token the client presented (rotation at sign-in)."""
        if not token or not is_well_formed(token):
            return
        key = LookupKey.session_token_hash(self._hash(TokenPurpose.SESSION, token))
        async with lookup_transaction(self._factory, request_id=info.request_id, key=key) as db:
            row = await repo.session_by_token_hash(db, key.value)
            if row is not None and row.revoked_at is None:
                await repo.revoke_session(db, row.id, SessionRevokeReason.ROTATED, self._clock())
                record_security_event(
                    events.SESSION_ROTATED, target=AuditTarget("user_session", row.id)
                )

    # --- sign-in --------------------------------------------------------------------------

    async def login(
        self, raw_email: str, password: str, info: RequestInfo, presented_token: str | None
    ) -> IssuedSession:
        await self._limit("ip", "login", info.ip)
        try:
            email: str | None = normalize_email(raw_email)
        except InvalidEmailError:
            email = None
        candidate: repo.LoginCandidate | None = None
        if email is not None:
            await self._limit("account", "login", email)
            key = LookupKey.email(email)
            async with lookup_transaction(self._factory, request_id=info.request_id, key=key) as db:
                candidate = await repo.login_candidate(db, email)

        # Outside any transaction (D02). Unknown accounts verify the dummy hash.
        password_hash = candidate.password_hash if candidate else None
        verified = await self.hasher.verify(password_hash, password)
        now = self._clock()
        locked = bool(candidate and candidate.locked_until and candidate.locked_until > now)
        if (
            candidate is None
            or email is None
            or not verified
            or locked
            or candidate.status is not UserStatus.ACTIVE
        ):
            await self._login_failed(email, candidate, verified=verified, locked=locked, info=info)
            raise AuthenticationRequiredError()

        new_hash = (
            await self.hasher.hash(password)
            if password_hash and self.hasher.needs_rehash(password_hash)
            else None
        )
        await self._revoke_presented(presented_token, info)
        user_id = candidate.user_id
        async with subject_transaction(
            self._factory, request_id=info.request_id, user_id=user_id
        ) as db:
            await repo.record_successful_login(db, user_id, new_hash)
            pending = (
                await self._issue_pending(db, user_id, info)
                if await self.mfa.enabled(db, user_id)
                else None
            )
        if pending is not None:
            record_security_event(events.MFA_CHALLENGED, target=AuditTarget("user", user_id))
            return pending
        return await self._open_institutes(user_id, info, mfa_verified_at=None)

    async def _issue_pending(
        self, db: AsyncSession, user_id: uuid.UUID, info: RequestInfo
    ) -> IssuedSession:
        """The MFA-pending session: no institute, 5 minutes, no permissions (T01-06)."""
        identity = await repo.user_identity(db, user_id)
        if identity is None:
            raise AuthenticationRequiredError()
        now = self._clock()
        token = new_token()
        session_id = await repo.create_session(
            db,
            token_hash=self._hash(TokenPurpose.SESSION, token),
            user_id=user_id,
            tenant_id=None,
            campus_id=None,
            now=now,
            idle_expires_at=now + MFA_PENDING_TTL,
            absolute_expires_at=now + MFA_PENDING_TTL,
            ip=info.ip,
            user_agent=info.user_agent,
            mfa_pending=True,
        )
        record_security_event(
            events.SESSION_CREATED, target=AuditTarget("user_session", session_id)
        )
        view = SessionView(
            display_name=identity[0],
            email=identity[1],
            active_institute=None,
            institutes=(),
            active_campus=None,
            campus_options=(),
            all_campuses_allowed=False,
            campus_selection_required=False,
            csrf_token=self.csrf_token(session_id),
            mfa_required=True,
            mfa_enabled=True,
        )
        return IssuedSession(token, view)

    async def _open_institutes(
        self, user_id: uuid.UUID, info: RequestInfo, *, mfa_verified_at: datetime | None
    ) -> IssuedSession:
        """The rest of sign-in: institute and campus resolution (D04), a new session."""
        async with subject_transaction(
            self._factory, request_id=info.request_id, user_id=user_id
        ) as db:
            memberships = await repo.memberships_of_user(db, user_id)
            institutes = _usable_institutes(memberships)
            if len(institutes) != 1:
                if not institutes:
                    record_security_event(
                        events.LOGIN_FAILED,
                        target=AuditTarget("user", user_id),
                        metadata={"reason": "no_membership"},
                    )
                    raise AuthenticationRequiredError()
                issued = await self._issue(
                    db,
                    user_id=user_id,
                    memberships=memberships,
                    resolution=None,
                    info=info,
                    mfa_verified_at=mfa_verified_at,
                )
        if len(institutes) == 1:
            tenant_id = institutes[0].id
            async with subject_transaction(
                self._factory, request_id=info.request_id, user_id=user_id, tenant_id=tenant_id
            ) as db:
                resolution = await self._campus_resolution(db, memberships, tenant_id, None)
                if resolution is None:  # changed since the first read
                    raise AuthenticationRequiredError()
                issued = await self._issue(
                    db,
                    user_id=user_id,
                    memberships=memberships,
                    resolution=resolution,
                    info=info,
                    mfa_verified_at=mfa_verified_at,
                )
        record_security_event(events.LOGIN_SUCCESS, target=AuditTarget("user", user_id))
        return issued

    async def _login_failed(
        self,
        email: str | None,
        candidate: repo.LoginCandidate | None,
        *,
        verified: bool,
        locked: bool,
        info: RequestInfo,
    ) -> None:
        reason = "unknown_account"
        if candidate is not None:
            reason = (
                "locked"
                if locked
                else "inactive"
                if candidate.status is not UserStatus.ACTIVE
                else "no_credential"
                if candidate.password_hash is None
                else "bad_password"
            )
        if reason == "bad_password" and email is not None and candidate is not None:
            # Durable lockout (D17); counted only for real accounts, never while locked.
            key = LookupKey.email(email)
            async with lookup_transaction(self._factory, request_id=info.request_id, key=key) as db:
                count = await repo.record_failed_login(db, candidate.user_id, self._clock())
                duration = lockout_duration(count)
                if duration is not None:
                    await repo.lock_account(db, candidate.user_id, self._clock() + duration)
                    record_security_event(
                        events.ACCOUNT_LOCKED,
                        target=AuditTarget("user", candidate.user_id),
                        metadata={"minutes": int(duration.total_seconds() // 60)},
                    )
        record_security_event(
            events.LOGIN_FAILED,
            target=AuditTarget("user", candidate.user_id) if candidate else None,
            metadata={"reason": reason},
        )

    # --- session resolution (every request) ---------------------------------------------

    async def resolve(self, token: str | None, info: RequestInfo) -> ResolvedSession:
        """Re-validate the presented session; raise 401 when it cannot be used."""
        if not token or not is_well_formed(token):
            raise AuthenticationRequiredError()
        key = LookupKey.session_token_hash(self._hash(TokenPurpose.SESSION, token))
        async with lookup_transaction(self._factory, request_id=info.request_id, key=key) as db:
            row = await repo.session_by_token_hash(db, key.value)
        now = self._clock()
        if (
            row is None
            or row.revoked_at is not None
            or row.idle_expires_at <= now
            or row.absolute_expires_at <= now
        ):
            raise AuthenticationRequiredError()
        if row.mfa_pending:
            async with subject_transaction(
                self._factory, request_id=info.request_id, user_id=row.user_id
            ) as db:
                identity = await repo.user_identity(db, row.user_id)
            if identity is None or identity[2] is not UserStatus.ACTIVE:
                raise AuthenticationRequiredError()
            return ResolvedSession(row.id, row.user_id, None, None, False, mfa_pending=True)
        async with subject_transaction(
            self._factory,
            request_id=info.request_id,
            user_id=row.user_id,
            tenant_id=row.active_tenant_id,
        ) as db:
            identity = await repo.user_identity(db, row.user_id)
            if identity is None or identity[2] is not UserStatus.ACTIVE:
                raise AuthenticationRequiredError()
            tenant_id, campus_id, required = row.active_tenant_id, row.active_campus_id, False
            resolution = None
            if tenant_id is not None:
                memberships = await repo.memberships_of_user(db, row.user_id)
                resolution = await self._campus_resolution(db, memberships, tenant_id, campus_id)
                if resolution is None:  # membership or tenant no longer usable
                    tenant_id, campus_id = None, None
                else:
                    campus_id = resolution.state.active_campus_id
                    required = resolution.state.selection_required
            access = await self._access(db, resolution)
            if (tenant_id, campus_id) != (row.active_tenant_id, row.active_campus_id):
                await repo.set_session_context(db, row.id, tenant_id=tenant_id, campus_id=campus_id)
            if now - row.last_seen_at >= TOUCH_INTERVAL:
                idle = min(now + self.config.idle_timeout, row.absolute_expires_at)
                await repo.touch_session(db, row.id, now=now, idle_expires_at=idle)
        return ResolvedSession(
            row.id,
            row.user_id,
            tenant_id,
            campus_id,
            required,
            permissions=access.permissions,
            all_campuses=resolution is not None
            and resolution.membership.campus_scope is CampusScope.ALL,
            campus_ids=frozenset(c.id for c in resolution.options) if resolution else frozenset(),
            mfa_verified_at=row.mfa_verified_at,
        )

    async def view(self, db: AsyncSession, resolved: ResolvedSession) -> SessionView:
        """The session read (``GET /session``) in the request's own transaction."""
        memberships = await repo.memberships_of_user(db, resolved.user_id)
        resolution = None
        if resolved.tenant_id is not None:
            resolution = await self._campus_resolution(
                db, memberships, resolved.tenant_id, resolved.campus_id
            )
        return await self._view(
            db,
            session_id=resolved.session_id,
            user_id=resolved.user_id,
            memberships=memberships,
            resolution=resolution,
        )

    # --- institute and campus selection ---------------------------------------------------

    async def switch_tenant(
        self, resolved: ResolvedSession, tenant_id: uuid.UUID, info: RequestInfo
    ) -> IssuedSession:
        """Select an institute: validated membership, rotated session (ADR-0010 §1)."""
        async with subject_transaction(
            self._factory, request_id=info.request_id, user_id=resolved.user_id, tenant_id=tenant_id
        ) as db:
            memberships = await repo.memberships_of_user(db, resolved.user_id)
            resolution = await self._campus_resolution(db, memberships, tenant_id, None)
            if resolution is None:
                raise NotFoundError()
            issued = await self._issue(
                db,
                user_id=resolved.user_id,
                memberships=memberships,
                resolution=resolution,
                info=info,
                mfa_verified_at=resolved.mfa_verified_at,
            )
            await repo.revoke_session(
                db, resolved.session_id, SessionRevokeReason.ROTATED, self._clock()
            )
        record_security_event(events.TENANT_SWITCHED, target=AuditTarget("tenant", tenant_id))
        record_security_event(
            events.SESSION_ROTATED, target=AuditTarget("user_session", resolved.session_id)
        )
        return issued

    async def switch_campus(
        self, db: AsyncSession, resolved: ResolvedSession, campus_id: uuid.UUID | None
    ) -> SessionView:
        """Select a campus (D04 §2.4): no rotation; applies from the next request."""
        if resolved.tenant_id is None:
            raise NotFoundError()
        memberships = await repo.memberships_of_user(db, resolved.user_id)
        resolution = await self._campus_resolution(
            db, memberships, resolved.tenant_id, resolved.campus_id
        )
        if resolution is None:
            raise NotFoundError()
        permitted = {campus.id for campus in resolution.options}
        if campus_id is None:
            if not resolution.state.all_campuses_allowed:
                raise NotFoundError()
        elif campus_id not in permitted:
            raise NotFoundError()
        await repo.set_session_context(
            db, resolved.session_id, tenant_id=resolved.tenant_id, campus_id=campus_id
        )
        record_security_event(
            events.CAMPUS_SWITCHED,
            target=AuditTarget("campus", campus_id) if campus_id else None,
            metadata={"all_campuses": campus_id is None},
        )
        new_state = replace(resolution.state, active_campus_id=campus_id, selection_required=False)
        return await self._view(
            db,
            session_id=resolved.session_id,
            user_id=resolved.user_id,
            memberships=memberships,
            resolution=replace(resolution, state=new_state),
        )

    # --- MFA (T01-06): sign-in step, opt-in enrolment, removal ----------------------------

    async def verify_mfa(
        self, resolved: ResolvedSession, code: str, info: RequestInfo
    ) -> IssuedSession:
        """Complete sign-in with a TOTP code; the pending session is rotated."""
        await self._limit("account", "mfa", str(resolved.user_id))
        async with subject_transaction(
            self._factory, request_id=info.request_id, user_id=resolved.user_id
        ) as db:
            ok = await self.mfa.verify_totp(
                db, resolved.user_id, code, keyring=self.keyring, now=self._clock()
            )
        if not ok:
            await self._mfa_failed(resolved, info, stage="totp")
        return await self._complete_mfa(resolved, info, method="totp")

    async def use_recovery_code(
        self, resolved: ResolvedSession, code: str, info: RequestInfo
    ) -> IssuedSession:
        await self._limit("account", "mfa", str(resolved.user_id))
        async with subject_transaction(
            self._factory, request_id=info.request_id, user_id=resolved.user_id
        ) as db:
            ok = await self.mfa.use_recovery_code(db, resolved.user_id, code, now=self._clock())
            remaining = await self.mfa.remaining_codes(db, resolved.user_id)
        if not ok:
            await self._mfa_failed(resolved, info, stage="recovery_code")
        record_security_event(
            events.MFA_RECOVERY_CODE_USED,
            target=AuditTarget("user", resolved.user_id),
            metadata={"remaining": remaining},
        )
        return await self._complete_mfa(resolved, info, method="recovery_code")

    async def _mfa_failed(
        self, resolved: ResolvedSession, info: RequestInfo, *, stage: str
    ) -> NoReturn:
        """Count the failure on the session and the credential; always raises."""
        now = self._clock()
        async with subject_transaction(
            self._factory, request_id=info.request_id, user_id=resolved.user_id
        ) as db:
            attempts = await repo.record_session_mfa_failure(db, resolved.session_id)
            count = await repo.record_failed_login(db, resolved.user_id, now)
            duration = lockout_duration(count)
            if duration is not None:
                await repo.lock_account(db, resolved.user_id, now + duration)
            revoked = attempts >= MFA_SESSION_ATTEMPTS and await repo.revoke_session(
                db, resolved.session_id, SessionRevokeReason.MFA_FAILED, now
            )
        target = AuditTarget("user", resolved.user_id)
        if duration is not None:
            record_security_event(
                events.ACCOUNT_LOCKED,
                target=target,
                metadata={"minutes": int(duration.total_seconds() // 60)},
            )
        record_security_event(
            events.MFA_FAILED, target=target, metadata={"stage": stage, "attempts": attempts}
        )
        if revoked:
            record_security_event(
                events.SESSION_REVOKED,
                target=AuditTarget("user_session", resolved.session_id),
                metadata={"reason": "mfa_failed"},
            )
            raise AuthenticationRequiredError()
        raise INVALID_CODE

    async def _complete_mfa(
        self, resolved: ResolvedSession, info: RequestInfo, *, method: str
    ) -> IssuedSession:
        now = self._clock()
        async with subject_transaction(
            self._factory, request_id=info.request_id, user_id=resolved.user_id
        ) as db:
            if not await repo.revoke_session(
                db, resolved.session_id, SessionRevokeReason.ROTATED, now
            ):
                raise AuthenticationRequiredError()
        record_security_event(
            events.MFA_VERIFIED,
            target=AuditTarget("user", resolved.user_id),
            metadata={"method": method},
        )
        record_security_event(
            events.SESSION_ROTATED, target=AuditTarget("user_session", resolved.session_id)
        )
        return await self._open_institutes(resolved.user_id, info, mfa_verified_at=now)

    async def start_enrolment(self, resolved: ResolvedSession, info: RequestInfo) -> Enrolment:
        """Opt-in TOTP enrolment for the signed-in user (secret returned once)."""
        async with subject_transaction(
            self._factory, request_id=info.request_id, user_id=resolved.user_id
        ) as db:
            identity = await repo.user_identity(db, resolved.user_id)
            if identity is None:
                raise AuthenticationRequiredError()
            try:
                enrolment = await self.mfa.start_enrolment(
                    db,
                    resolved.user_id,
                    keyring=self.keyring,
                    account=identity[1],
                    now=self._clock(),
                )
            except MfaAlreadyEnabledError:
                raise ConflictError("Multi-factor authentication is already set up.") from None
        record_security_event(
            events.MFA_ENROLMENT_STARTED, target=AuditTarget("user", resolved.user_id)
        )
        return enrolment

    async def confirm_enrolment(
        self, resolved: ResolvedSession, code: str, info: RequestInfo
    ) -> list[str]:
        """Confirm the factor with a first code; recovery codes (returned once)."""
        await self._limit("account", "mfa", str(resolved.user_id))
        now = self._clock()
        async with subject_transaction(
            self._factory, request_id=info.request_id, user_id=resolved.user_id
        ) as db:
            codes = await self.mfa.confirm_enrolment(
                db, resolved.user_id, code, keyring=self.keyring, now=now
            )
            if codes is not None:
                await repo.mark_session_mfa_verified(db, resolved.session_id, now)
        if codes is None:
            await self._mfa_failed(resolved, info, stage="enrolment")
        record_security_event(events.MFA_ENROLLED, target=AuditTarget("user", resolved.user_id))
        return codes

    async def remove_mfa(self, resolved: ResolvedSession, code: str, info: RequestInfo) -> None:
        """Turn MFA off; needs a current TOTP code from the enrolled factor."""
        await self._limit("account", "mfa", str(resolved.user_id))
        now = self._clock()
        async with subject_transaction(
            self._factory, request_id=info.request_id, user_id=resolved.user_id
        ) as db:
            ok = await self.mfa.verify_totp(
                db, resolved.user_id, code, keyring=self.keyring, now=now
            )
            if ok:
                await self.mfa.disable(db, resolved.user_id, reason="user_removed", now=now)
        if not ok:
            await self._mfa_failed(resolved, info, stage="removal")
        record_security_event(events.MFA_REMOVED, target=AuditTarget("user", resolved.user_id))

    # --- sign-out ---------------------------------------------------------------------------

    async def logout(self, token: str | None, info: RequestInfo) -> None:
        """Revoke the presented session if there is one; idempotent."""
        if not token or not is_well_formed(token):
            return
        key = LookupKey.session_token_hash(self._hash(TokenPurpose.SESSION, token))
        async with lookup_transaction(self._factory, request_id=info.request_id, key=key) as db:
            row = await repo.session_by_token_hash(db, key.value)
            if row is not None and await repo.revoke_session(
                db, row.id, SessionRevokeReason.LOGOUT, self._clock()
            ):
                record_security_event(events.LOGOUT, target=AuditTarget("user_session", row.id))

    # --- password reset ---------------------------------------------------------------------

    async def request_password_reset(
        self, raw_email: str, info: RequestInfo
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
            async with lookup_transaction(
                self._factory, request_id=info.request_id, key=LookupKey.email(email)
            ) as db:
                candidate = await repo.login_candidate(db, email)
            if (
                candidate is not None
                and candidate.status is UserStatus.ACTIVE
                and candidate.password_hash is not None
            ):
                token = new_token()
                now = self._clock()
                async with subject_transaction(
                    self._factory, request_id=info.request_id, user_id=candidate.user_id
                ) as db:
                    await repo.replace_reset_token(
                        db,
                        candidate.user_id,
                        self._hash(TokenPurpose.PASSWORD_RESET, token),
                        now=now,
                        expires_at=now + PASSWORD_RESET_TTL,
                    )
                    identity = await repo.user_identity(db, candidate.user_id)
                display_name = identity[0] if identity else ""
                message = password_reset_email(
                    to=email,
                    display_name=display_name,
                    link=reset_link(self.config.app_base_url, token),
                )
                record_security_event(
                    events.PASSWORD_RESET_REQUESTED, target=AuditTarget("user", candidate.user_id)
                )
            else:
                record_security_event(events.PASSWORD_RESET_REQUESTED)
        remaining = self.config.reset_response_floor_seconds - (time.monotonic() - started)
        if remaining > 0:
            await anyio.sleep(remaining)
        return message

    def _password_error(self, password: str, field: str) -> ValidationFailedError | None:
        problem = password_problem(password, common_passwords())
        if problem is None:
            return None
        return ValidationFailedError(
            details=[
                ErrorDetail(field=field, code=problem.value, message=PASSWORD_MESSAGES[problem])
            ]
        )

    async def confirm_password_reset(self, token: str, password: str, info: RequestInfo) -> None:
        await self._limit("ip", "recovery", info.ip)
        if (error := self._password_error(password, "new_password")) is not None:
            raise error
        if not is_well_formed(token):
            raise NotFoundError()
        key = LookupKey.token_hash(self._hash(TokenPurpose.PASSWORD_RESET, token))
        async with lookup_transaction(self._factory, request_id=info.request_id, key=key) as db:
            row = await repo.reset_token_by_hash(db, key.value)
        if (
            row is None
            or row.used_at is not None
            or row.invalidated_at is not None
            or row.expires_at <= self._clock()
        ):
            raise NotFoundError()
        new_hash = await self.hasher.hash(password)
        async with subject_transaction(
            self._factory, request_id=info.request_id, user_id=row.user_id
        ) as db:
            now = self._clock()
            if not await repo.consume_reset_token(db, row.id, now):
                raise NotFoundError()
            identity = await repo.user_identity(db, row.user_id)
            if identity is None or identity[2] is not UserStatus.ACTIVE:
                raise NotFoundError()
            if not await repo.set_password(db, row.user_id, new_hash, now):
                raise NotFoundError()
            revoked = await repo.revoke_user_sessions(
                db, row.user_id, SessionRevokeReason.PASSWORD_RESET, now
            )
        record_security_event(
            events.PASSWORD_RESET_COMPLETED, target=AuditTarget("user", row.user_id)
        )
        if revoked:
            record_security_event(
                events.SESSION_REVOKED,
                target=AuditTarget("user", row.user_id),
                metadata={"reason": "password_reset", "session_count": revoked},
            )

    # --- invitations ----------------------------------------------------------------------

    async def _open_invitation(self, token: str, info: RequestInfo) -> repo.InvitationRow:
        if not is_well_formed(token):
            raise NotFoundError()
        key = LookupKey.token_hash(self._hash(TokenPurpose.INVITATION, token))
        async with lookup_transaction(self._factory, request_id=info.request_id, key=key) as db:
            row = await repo.invitation_by_hash(db, key.value)
        if (
            row is None
            or row.accepted_at is not None
            or row.revoked_at is not None
            or row.expires_at <= self._clock()
            or row.membership_status is not MembershipStatus.INVITED
        ):
            raise NotFoundError()
        return row

    async def _invitation_subject(
        self, db: AsyncSession, invitation: repo.InvitationRow
    ) -> tuple[str, str, Account]:
        """(institute name, email, account) — 404 if the invitation cannot be used."""
        identity = await repo.user_identity(db, invitation.user_id)
        tenant = await repo.tenant_name(db, invitation.tenant_id)
        if identity is None or identity[2] is UserStatus.DISABLED or tenant is None:
            raise NotFoundError()
        if not _tenant_accessible(tenant[1]):
            raise NotFoundError()
        account: Account = (
            "existing" if await repo.has_credential(db, invitation.user_id) else "new"
        )
        return tenant[0], identity[1], account

    async def preview_invitation(self, token: str, info: RequestInfo) -> InvitationPreview:
        """D19: read-only, no audit event, generic 404."""
        await self._limit("ip", "invitation", info.ip)
        invitation = await self._open_invitation(token, info)
        async with subject_transaction(
            self._factory,
            request_id=info.request_id,
            user_id=invitation.user_id,
            tenant_id=invitation.tenant_id,
        ) as db:
            name, email, account = await self._invitation_subject(db, invitation)
        return InvitationPreview(name, mask_email(email), account)

    async def accept_invitation(
        self,
        token: str,
        display_name: str | None,
        password: str | None,
        info: RequestInfo,
    ) -> None:
        """D19 §3.4: new accounts set a name and password; existing ones never do."""
        await self._limit("ip", "invitation", info.ip)
        invitation = await self._open_invitation(token, info)
        subject = {
            "request_id": info.request_id,
            "user_id": invitation.user_id,
            "tenant_id": invitation.tenant_id,
        }
        async with subject_transaction(self._factory, **subject) as db:
            _, _, account = await self._invitation_subject(db, invitation)

        new_hash: str | None = None
        if account == "existing":
            if display_name is not None or password is not None:
                raise ValidationFailedError(
                    details=[
                        ErrorDetail(
                            field="password" if password is not None else "display_name",
                            code="not_allowed_for_existing_account",
                            message="This account already exists. Accept without a password.",
                        )
                    ]
                )
        else:
            missing = [
                ErrorDetail(field=name, code="missing", message="This field is required.")
                for name, value in (("display_name", display_name), ("password", password))
                if not value
            ]
            if missing:
                raise ValidationFailedError(details=missing)
            assert password is not None  # noqa: S101 - checked above
            if (error := self._password_error(password, "password")) is not None:
                raise error
            new_hash = await self.hasher.hash(password)

        async with subject_transaction(self._factory, **subject) as db:
            now = self._clock()
            if not await repo.accept_invitation(db, invitation.tenant_id, invitation.id, now):
                raise NotFoundError()
            if not await repo.activate_membership(
                db, invitation.tenant_id, invitation.membership_id, now
            ):
                raise NotFoundError()
            if new_hash is None:
                await repo.activate_invited_user(db, invitation.user_id, None, now)
            else:
                if await repo.has_credential(db, invitation.user_id):
                    raise NotFoundError()  # became an existing account meanwhile
                if not await repo.activate_invited_user(db, invitation.user_id, display_name, now):
                    raise NotFoundError()
                await repo.create_credential(db, invitation.user_id, new_hash, now)
        record_security_event(
            events.INVITATION_ACCEPTED,
            target=AuditTarget("tenant_membership", invitation.membership_id),
            metadata={"account": account},
        )


async def send_email_safely(
    sender: EmailSender, message: EmailMessage, request_id: uuid.UUID
) -> None:
    """Post-response delivery (backend-foundation.md §5). Never raises; never logs secrets."""
    try:
        await sender.send(message)
    except Exception as error:
        logger.error(
            "email.send_failed",
            extra={
                "request_id": str(request_id),
                "template": message.template,
                "error_type": type(error).__name__,
            },
        )
