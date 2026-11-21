"""Public enquiry: resolve the institute, then store a lead and its acknowledgement.

Phase 02-4, ADR-0024. The public realm has no session and no tenant until the
request host resolves (``app.modules.tenants.domains``):

1. **Resolve** — in a public-realm transaction (no tenant), an exact match on
   one ``ACTIVE``, verified ``tenant_domains`` row; then, with that tenant as
   the trusted context, its status must serve the public website
   (``TRIAL`` / ``ACTIVE``). Anything else is 404, the same for every cause.
2. **Admit** — a browser ``Origin`` other than the resolved host is 403. The
   client IP and the institute are rate-limited (Redis, fail closed: 503).
3. **Discard** — a filled-in spam trap is answered exactly like an accepted
   enquiry, and nothing is stored (a security event records it).
4. **Validate** — mandatory consent of the current version, a name, an email
   or a mobile number, an open course of this institute (another institute's
   course is "not available", never "not found").
5. **Store** — one transaction with the resolved tenant: the ``NEW`` lead
   (``WEBSITE``, institute pool, no owner, no creator, consent evidence), its
   ``CREATED`` activity, the message as a note, the ``lead.created`` audit
   event and, with an email, the acknowledgement outbox message. Either all
   of them commit or none. The same contact and course within the duplicate
   window is acknowledged but not stored again (serialized by an advisory
   lock, so concurrent repeats cannot both pass).

The answer never says whether a contact is known, here or at another institute.
"""

import logging
import uuid
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast
from urllib.parse import urlsplit

from sqlalchemy import Table, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.activity import record_activity
from app.core.audit import AuditTarget, record_security_event, write_audit_event
from app.core.context import current_context
from app.core.db.session import context_transaction
from app.core.errors import (
    ErrorDetail,
    NotFoundError,
    PermissionDeniedError,
    RateLimitedError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.core.outbox import OutboxSignal, enqueue
from app.core.ratelimit import (
    Limit,
    RateLimiter,
    RateLimiterUnavailableError,
    RateLimitExceededError,
)
from app.modules.courses.domain import CourseStatus
from app.modules.courses.models import Course
from app.modules.enquiries.domain import (
    ACKNOWLEDGEMENT_KIND,
    CONSENT_VERSION,
    MESSAGE_MAX_LENGTH,
    consent_text,
    privacy_notice,
)
from app.modules.enquiries.events import ENQUIRY_DISCARDED, ENQUIRY_ORIGIN_REJECTED
from app.modules.enquiries.schemas import (
    EnquiryConsent,
    EnquiryCourse,
    EnquiryFormOut,
    EnquiryRequest,
)
from app.modules.leads import events as lead_events
from app.modules.leads.domain import (
    INITIAL_STATUS,
    ActivityKind,
    LeadSource,
    clean_email,
    clean_mobile,
    clean_name,
    clean_text,
    mobile_key,
)
from app.modules.leads.models import Lead, LeadActivity
from app.modules.tenants.domain import TenantStatus, public_access_allowed
from app.modules.tenants.domains import resolve_public_host
from app.modules.tenants.models import Tenant
from app.modules.tenants.scopes import public_site_transaction
from app.modules.tenants.sites import normalize_host

logger = logging.getLogger("app.enquiries")

RATE_LIMIT_NAMESPACE: Final = "public"
ACTIVITIES = cast(Table, LeadActivity.__table__)
LEADS = cast(Table, Lead.__table__)


@dataclass(frozen=True, slots=True)
class EnquiryConfig:
    ip_limit: Limit
    tenant_limit: Limit
    duplicate_window: timedelta
    retention_months: int
    outbox_max_attempts: int


@dataclass(frozen=True, slots=True)
class Institute:
    tenant_id: uuid.UUID
    name: str


@dataclass(frozen=True, slots=True)
class Contact:
    full_name: str
    email: str | None
    email_normalized: str | None
    mobile: str | None
    mobile_key: str | None
    message: str | None


def _invalid(field: str, code: str, message: str) -> ErrorDetail:
    return ErrorDetail(field=field, code=code, message=message)


def _clean(request: EnquiryRequest) -> Contact:
    """The submitted contact, or 422 with every problem (never the submitted values)."""
    problems: list[ErrorDetail] = []
    if not request.consent_accepted:
        problems.append(
            _invalid("consent_accepted", "consent_required", "Agree to the consent to continue.")
        )
    elif request.consent_version != CONSENT_VERSION:
        problems.append(
            _invalid(
                "consent_version",
                "consent_outdated",
                "The consent text has changed. Reload the page and try again.",
            )
        )
    name = clean_name(request.full_name)
    if name is None:
        problems.append(_invalid("full_name", "required", "Enter your name."))
    email: tuple[str, str] | None = None
    try:
        email = clean_email(request.email)
    except ValueError:
        problems.append(_invalid("email", "invalid", "Enter a valid email address."))
    mobile: str | None = None
    try:
        mobile = clean_mobile(request.mobile)
    except ValueError:
        problems.append(_invalid("mobile", "invalid", "Enter a valid phone number."))
    if (
        email is None
        and mobile is None
        and not any(p.field in {"email", "mobile"} for p in problems)
    ):
        problems.append(
            _invalid("email", "contact_required", "Enter an email address or a phone number.")
        )
    message: str | None = None
    try:
        message = clean_text(request.message, MESSAGE_MAX_LENGTH)
    except ValueError:  # pragma: no cover - the schema bounds it first
        problems.append(_invalid("message", "too_long", "The message is too long."))
    if problems:
        raise ValidationFailedError(details=problems)
    return Contact(
        full_name=cast(str, name),
        email=email[0] if email else None,
        email_normalized=email[1] if email else None,
        mobile=mobile,
        mobile_key=mobile_key(mobile),
        message=message,
    )


def _same_origin(origin: str | None, host: str | None) -> bool:
    """No ``Origin`` (not a cross-site browser request), or one naming the page's host."""
    if origin is None:
        return True
    try:
        netloc = urlsplit(origin).netloc
    except ValueError:
        return False
    expected = normalize_host(host)
    return expected is not None and normalize_host(netloc) == expected


class PublicEnquiries:
    """The hosted enquiry page's two operations (form and submit)."""

    def __init__(
        self,
        *,
        factory: async_sessionmaker[AsyncSession],
        limiter: RateLimiter,
        signal: OutboxSignal | None,
        config: EnquiryConfig,
    ) -> None:
        self.factory = factory
        self.limiter = limiter
        self.signal = signal
        self.config = config

    # --- Resolution ------------------------------------------------------------------

    def _scoped(self, tenant_id: uuid.UUID) -> AbstractAsyncContextManager[AsyncSession]:
        """A transaction of the request's public context with the server-resolved tenant."""
        return public_site_transaction(self.factory, context=current_context(), tenant_id=tenant_id)

    async def resolve(self, host: str | None) -> Institute:
        """The institute served at ``host``; 404 when there is none (any reason)."""
        public = current_context()
        async with context_transaction(self.factory, public) as db:
            tenant_id = await resolve_public_host(db, host)
        if tenant_id is None:
            raise NotFoundError()
        async with self._scoped(tenant_id) as db:
            row = (
                await db.execute(select(Tenant.name, Tenant.status).where(Tenant.id == tenant_id))
            ).one_or_none()
        if row is None or not public_access_allowed(TenantStatus(row.status)):
            raise NotFoundError()
        return Institute(tenant_id, row.name)

    # --- Form ------------------------------------------------------------------------

    async def form(self, host: str | None) -> EnquiryFormOut:
        institute = await self.resolve(host)
        async with self._scoped(institute.tenant_id) as db:
            courses = (
                await db.execute(
                    select(Course.id, Course.name, Course.category)
                    .where(Course.status == CourseStatus.ACTIVE.value)
                    .order_by(Course.name, Course.id)
                )
            ).all()
        months = self.config.retention_months
        return EnquiryFormOut(
            institute_name=institute.name,
            courses=[EnquiryCourse(id=c.id, name=c.name, category=c.category) for c in courses],
            consent=EnquiryConsent(
                version=CONSENT_VERSION,
                text=consent_text(institute.name, months),
                retention_months=months,
            ),
            privacy_notice=privacy_notice(institute.name, months),
        )

    # --- Submit ----------------------------------------------------------------------

    async def _limit(self, kind: str, identifier: str, limit: Limit) -> None:
        try:
            await self.limiter.hit(kind, "enquiry", identifier, limit)
        except RateLimitExceededError as error:
            raise RateLimitedError(retry_after=error.retry_after) from None
        except RateLimiterUnavailableError:
            raise ServiceUnavailableError() from None

    async def submit(
        self,
        institute: Institute,
        *,
        host: str | None,
        origin: str | None,
        client_ip: str,
        request: EnquiryRequest,
    ) -> None:
        """Accept one enquiry for ``institute`` (resolved from ``host`` by :meth:`resolve`)."""
        if not _same_origin(origin, host):
            record_security_event(ENQUIRY_ORIGIN_REJECTED)
            raise PermissionDeniedError()
        await self._limit("ip", client_ip, self.config.ip_limit)
        await self._limit("tenant", str(institute.tenant_id), self.config.tenant_limit)
        if request.website.strip():
            record_security_event(ENQUIRY_DISCARDED, metadata={"reason": "honeypot"})
            return
        contact = _clean(request)
        async with self._scoped(institute.tenant_id) as db:
            queued = await self._store(db, institute.tenant_id, contact, request.course_id)
        if queued and self.signal is not None:
            await self.signal.notify()

    async def _store(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        contact: Contact,
        course_id: uuid.UUID | None,
    ) -> bool:
        """Write the lead and everything with it; ``True`` when an acknowledgement is queued."""
        if course_id is not None:
            open_course = await db.scalar(
                select(Course.id).where(
                    Course.id == course_id, Course.status == CourseStatus.ACTIVE.value
                )
            )
            if open_course is None:
                raise ValidationFailedError(
                    details=[
                        _invalid(
                            "course_id", "course_not_available", "Choose a course from the list."
                        )
                    ]
                )
        keys = [k for k in (contact.email_normalized, contact.mobile_key) if k]
        # Serialize submissions of the same contact at this institute (this transaction only).
        for key in sorted(keys):
            await db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
                {"k": f"enquiry:{tenant_id}:{key}"},
            )
        now = datetime.now(UTC)
        same_contact = or_(
            *(
                [LEADS.c.email_normalized == contact.email_normalized]
                if contact.email_normalized
                else []
            ),
            *([LEADS.c.mobile_key == contact.mobile_key] if contact.mobile_key else []),
        )
        repeated = await db.scalar(
            select(func.count())
            .select_from(LEADS)
            .where(
                LEADS.c.tenant_id == tenant_id,
                LEADS.c.source == LeadSource.WEBSITE.value,
                LEADS.c.created_by_membership_id.is_(None),
                LEADS.c.interested_course_id.is_not_distinct_from(course_id),
                LEADS.c.created_at > now - self.config.duplicate_window,
                same_contact,
            )
        )
        if repeated:
            logger.info("enquiry.repeat_suppressed", extra={"tenant_id": str(tenant_id)})
            return False
        known = await db.scalar(
            select(func.count())
            .select_from(LEADS)
            .where(LEADS.c.tenant_id == tenant_id, same_contact)
        )
        lead = Lead(
            tenant_id=tenant_id,
            status=INITIAL_STATUS.value,
            source=LeadSource.WEBSITE.value,
            full_name=contact.full_name,
            email=contact.email,
            email_normalized=contact.email_normalized,
            mobile=contact.mobile,
            mobile_key=contact.mobile_key,
            interested_course_id=course_id,
            campus_id=None,
            owner_membership_id=None,
            created_by_membership_id=None,
            consent_version=CONSENT_VERSION,
            consented_at=now,
        )
        db.add(lead)
        await db.flush()
        await record_activity(
            db,
            ACTIVITIES,
            subject_column="lead_id",
            subject_id=lead.id,
            kind=ActivityKind.CREATED.value,
            actor_membership_id=None,
            details={
                "source": LeadSource.WEBSITE.value,
                "channel": "public_enquiry",
                "consent_version": CONSENT_VERSION,
                "retention_months": self.config.retention_months,
                "possible_duplicates": int(known or 0),
            },
        )
        if contact.message:
            await record_activity(
                db,
                ACTIVITIES,
                subject_column="lead_id",
                subject_id=lead.id,
                kind=ActivityKind.NOTE.value,
                actor_membership_id=None,
                body=contact.message,
            )
        queued = False
        if contact.email is not None:
            queued = await enqueue(
                db,
                kind=ACKNOWLEDGEMENT_KIND,
                idempotency_key=f"{ACKNOWLEDGEMENT_KIND}:{lead.id}",
                payload={"lead_id": str(lead.id)},
                max_attempts=self.config.outbox_max_attempts,
            )
        await write_audit_event(
            db,
            lead_events.LEAD_CREATED,
            target=AuditTarget("lead", lead.id),
            metadata={
                "source": LeadSource.WEBSITE.value,
                "channel": "public_enquiry",
                "consent_version": CONSENT_VERSION,
                "has_course": course_id is not None,
                "has_email": contact.email is not None,
                "has_mobile": contact.mobile is not None,
                "has_message": contact.message is not None,
                "acknowledgement_queued": queued,
            },
        )
        return queued
