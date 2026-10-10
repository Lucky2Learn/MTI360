"""Lead tables (Phase 02-1; blueprint §18, ADR-0020 §3, §8).

All three are tenant-scoped (:class:`TenantScopedMixin`) with the
realm-agnostic tenant Row-Level Security policy of migration ``0009``, and
reference their tenant-scoped parents through composite foreign keys, so a
course, campus, membership or lead of another tenant is rejected by the
database.

* ``leads`` — one enquiry. ``campus_id`` NULL is the institute pool (L6).
  ``mobile_key`` / ``email_normalized`` are service-maintained duplicate
  keys (a warning only: no uniqueness). ``APPLICATION`` / ``ADMITTED`` are in
  the status CHECK for 02-2.
* ``lead_follow_ups`` — lightweight scheduled tasks; overdue is derived.
* ``lead_activities`` — the append-only, user-visible timeline (the runtime
  role may only SELECT and INSERT). No ``updated_at`` and no ``version``.

No hard delete: the runtime role has no DELETE privilege on any of them.
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TimestampMixin, VersionedMixin
from app.core.tenancy import TenantScopedMixin, tenant_foreign_key
from app.modules.leads.domain import (
    FOLLOW_UP_TEXT_MAX_LENGTH,
    NOTE_MAX_LENGTH,
    REASON_REQUIRED,
    ActivityKind,
    FollowUpKind,
    FollowUpStatus,
    LeadSource,
    LeadStatus,
)


def _in(column: str, values: Any) -> str:
    return f"{column} IN ({', '.join(repr(value.value) for value in values)})"


class Lead(TenantScopedMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_foreign_key("interested_course_id", "courses", name="fk_leads_course"),
        tenant_foreign_key("campus_id", "campuses", name="fk_leads_campus"),
        tenant_foreign_key("owner_membership_id", "tenant_memberships", name="fk_leads_owner"),
        tenant_foreign_key(
            "created_by_membership_id", "tenant_memberships", name="fk_leads_created_by"
        ),
        tenant_foreign_key("duplicate_of_lead_id", "leads", name="fk_leads_duplicate_of"),
        CheckConstraint("btrim(full_name) <> ''", name="full_name"),
        CheckConstraint("mobile IS NOT NULL OR email IS NOT NULL", name="contact"),
        CheckConstraint("(mobile IS NULL) = (mobile_key IS NULL)", name="mobile_key"),
        CheckConstraint("(email IS NULL) = (email_normalized IS NULL)", name="email_normalized"),
        CheckConstraint(_in("source", LeadSource), name="source"),
        CheckConstraint(_in("status", LeadStatus), name="status"),
        CheckConstraint(
            f"NOT ({_in('status', sorted(REASON_REQUIRED))}) OR status_reason IS NOT NULL",
            name="status_reason",
        ),
        CheckConstraint(
            "(status = 'DUPLICATE') = (duplicate_of_lead_id IS NOT NULL)", name="duplicate_of"
        ),
        CheckConstraint("duplicate_of_lead_id <> id", name="duplicate_not_self"),
        Index(None, "tenant_id", "status", "created_at"),
        Index(None, "tenant_id", "owner_membership_id", "status"),
        Index(None, "tenant_id", "campus_id", "status"),
        Index(None, "tenant_id", "interested_course_id"),
        Index(
            "ix_leads_tenant_id_mobile_key",
            "tenant_id",
            "mobile_key",
            postgresql_where=text("mobile_key IS NOT NULL"),
        ),
        Index(
            "ix_leads_tenant_id_email_normalized",
            "tenant_id",
            "email_normalized",
            postgresql_where=text("email_normalized IS NOT NULL"),
        ),
    )

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    mobile: Mapped[str | None] = mapped_column(String(32))
    mobile_key: Mapped[str | None] = mapped_column(String(16))
    email: Mapped[str | None] = mapped_column(String(254))
    email_normalized: Mapped[str | None] = mapped_column(String(254))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    city: Mapped[str | None] = mapped_column(String(120))
    highest_qualification: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    interested_course_id: Mapped[uuid.UUID | None] = mapped_column()
    campus_id: Mapped[uuid.UUID | None] = mapped_column()
    owner_membership_id: Mapped[uuid.UUID | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'NEW'"))
    status_reason: Mapped[str | None] = mapped_column(String(500))
    status_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    duplicate_of_lead_id: Mapped[uuid.UUID | None] = mapped_column()
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)


class LeadFollowUp(TenantScopedMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "lead_follow_ups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_foreign_key("lead_id", "leads", name="fk_lead_follow_ups_lead"),
        tenant_foreign_key(
            "assignee_membership_id", "tenant_memberships", name="fk_lead_follow_ups_assignee"
        ),
        tenant_foreign_key(
            "completed_by_membership_id",
            "tenant_memberships",
            name="fk_lead_follow_ups_completed_by",
        ),
        tenant_foreign_key(
            "created_by_membership_id", "tenant_memberships", name="fk_lead_follow_ups_created_by"
        ),
        CheckConstraint(_in("kind", FollowUpKind), name="kind"),
        CheckConstraint(_in("status", FollowUpStatus), name="status"),
        CheckConstraint("(status <> 'OPEN') = (completed_at IS NOT NULL)", name="completed_at"),
        CheckConstraint(
            "(status <> 'OPEN') = (completed_by_membership_id IS NOT NULL)", name="completed_by"
        ),
        CheckConstraint("outcome IS NULL OR status = 'DONE'", name="outcome"),
        Index(None, "tenant_id", "lead_id", "status", "due_at"),
        Index(None, "tenant_id", "assignee_membership_id", "status", "due_at"),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    assignee_membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(String(FOLLOW_UP_TEXT_MAX_LENGTH))
    outcome: Mapped[str | None] = mapped_column(String(FOLLOW_UP_TEXT_MAX_LENGTH))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'OPEN'"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by_membership_id: Mapped[uuid.UUID | None] = mapped_column()
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)


class LeadActivity(TenantScopedMixin, Base):
    __tablename__ = "lead_activities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_foreign_key("lead_id", "leads", name="fk_lead_activities_lead"),
        tenant_foreign_key(
            "actor_membership_id", "tenant_memberships", name="fk_lead_activities_actor"
        ),
        CheckConstraint(_in("kind", ActivityKind), name="kind"),
        CheckConstraint(f"char_length(body) <= {NOTE_MAX_LENGTH}", name="body_length"),
        CheckConstraint("(kind = 'NOTE') = (body IS NOT NULL)", name="body_note_only"),
        CheckConstraint("jsonb_typeof(details) = 'object'", name="details_object"),
        Index(None, "tenant_id", "lead_id", "created_at"),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_membership_id: Mapped[uuid.UUID | None] = mapped_column()
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    body: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, sort_order=90
    )
