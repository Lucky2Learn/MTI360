"""Application tables (Phase 02-2; ADR-0021 §3-§4, §12-§13).

Both are tenant-scoped (:class:`TenantScopedMixin`) with the realm-agnostic
tenant Row-Level Security policy of migration ``0010``, and reference their
parents through composite tenant foreign keys, so a lead, course, campus or
membership of another tenant is rejected by the database.

* ``applications`` — one application for one course, with the applicant's
  details as entered (no Applicant entity, L2). The campus is required (L6).
  ``DOCUMENT_VERIFICATION`` and ``ELIGIBLE`` are reserved statuses (INC-47).
* ``application_activities`` — the append-only, user-visible timeline (the
  runtime role may only SELECT and INSERT).

No hard delete: the runtime role has no DELETE privilege on either.
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
from app.modules.applications.domain import (
    ADDRESS_MAX_LENGTH,
    CITY_MAX_LENGTH,
    NAME_MAX_LENGTH,
    NUMBER_MAX_LENGTH,
    POSTAL_CODE_MAX_LENGTH,
    QUALIFICATION_MAX_LENGTH,
    REASON_MAX_LENGTH,
    REASON_REQUIRED,
    STATE_MAX_LENGTH,
    TEXT_MAX_LENGTH,
    ActivityKind,
    ApplicationStatus,
)


def _in(column: str, values: Any) -> str:
    return f"{column} IN ({', '.join(repr(value.value) for value in values)})"


class Application(TenantScopedMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "number"),
        tenant_foreign_key("lead_id", "leads", name="fk_applications_lead"),
        tenant_foreign_key("course_id", "courses", name="fk_applications_course"),
        tenant_foreign_key("campus_id", "campuses", name="fk_applications_campus"),
        tenant_foreign_key(
            "owner_membership_id", "tenant_memberships", name="fk_applications_owner"
        ),
        tenant_foreign_key(
            "created_by_membership_id", "tenant_memberships", name="fk_applications_created_by"
        ),
        tenant_foreign_key(
            "reviewed_by_membership_id", "tenant_memberships", name="fk_applications_reviewed_by"
        ),
        tenant_foreign_key(
            "declared_by_membership_id", "tenant_memberships", name="fk_applications_declared_by"
        ),
        CheckConstraint("btrim(full_name) <> ''", name="full_name"),
        CheckConstraint("(mobile IS NULL) = (mobile_key IS NULL)", name="mobile_key"),
        CheckConstraint("(email IS NULL) = (email_normalized IS NULL)", name="email_normalized"),
        CheckConstraint(_in("status", ApplicationStatus), name="status"),
        CheckConstraint(
            f"NOT ({_in('status', sorted(REASON_REQUIRED))}) OR status_reason IS NOT NULL",
            name="status_reason",
        ),
        CheckConstraint("status = 'DRAFT' OR submitted_at IS NOT NULL", name="submitted_at"),
        CheckConstraint(
            "(declared_at IS NULL) = (declared_by_membership_id IS NULL)", name="declaration"
        ),
        CheckConstraint(
            "(reviewed_at IS NULL) = (reviewed_by_membership_id IS NULL)", name="reviewed"
        ),
        CheckConstraint(
            f"char_length(education_details) <= {TEXT_MAX_LENGTH}", name="education_details"
        ),
        CheckConstraint(
            f"char_length(eligibility_notes) <= {TEXT_MAX_LENGTH}", name="eligibility_notes"
        ),
        Index(None, "tenant_id", "status", "created_at"),
        Index(None, "tenant_id", "campus_id", "status"),
        Index(None, "tenant_id", "lead_id"),
        Index(None, "tenant_id", "course_id"),
    )

    number: Mapped[str] = mapped_column(String(NUMBER_MAX_LENGTH), nullable=False)
    lead_id: Mapped[uuid.UUID | None] = mapped_column()
    course_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    campus_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    owner_membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default=text("'DRAFT'"))
    status_reason: Mapped[str | None] = mapped_column(String(REASON_MAX_LENGTH))
    status_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_membership_id: Mapped[uuid.UUID | None] = mapped_column()
    declared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    declared_by_membership_id: Mapped[uuid.UUID | None] = mapped_column()
    full_name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    mobile: Mapped[str | None] = mapped_column(String(32))
    mobile_key: Mapped[str | None] = mapped_column(String(16))
    email: Mapped[str | None] = mapped_column(String(254))
    email_normalized: Mapped[str | None] = mapped_column(String(254))
    address: Mapped[str | None] = mapped_column(String(ADDRESS_MAX_LENGTH))
    city: Mapped[str | None] = mapped_column(String(CITY_MAX_LENGTH))
    state: Mapped[str | None] = mapped_column(String(STATE_MAX_LENGTH))
    postal_code: Mapped[str | None] = mapped_column(String(POSTAL_CODE_MAX_LENGTH))
    highest_qualification: Mapped[str | None] = mapped_column(String(QUALIFICATION_MAX_LENGTH))
    education_details: Mapped[str | None] = mapped_column(Text)
    indos_number: Mapped[str | None] = mapped_column(String(16))
    cdc_number: Mapped[str | None] = mapped_column(String(NUMBER_MAX_LENGTH))
    eligibility_notes: Mapped[str | None] = mapped_column(Text)


class ApplicationActivity(TenantScopedMixin, Base):
    __tablename__ = "application_activities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_foreign_key(
            "application_id", "applications", name="fk_application_activities_application"
        ),
        tenant_foreign_key(
            "actor_membership_id", "tenant_memberships", name="fk_application_activities_actor"
        ),
        CheckConstraint(_in("kind", ActivityKind), name="kind"),
        CheckConstraint("jsonb_typeof(details) = 'object'", name="details_object"),
        Index(None, "tenant_id", "application_id", "created_at"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_membership_id: Mapped[uuid.UUID | None] = mapped_column()
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, sort_order=90
    )

    @property
    def body(self) -> str | None:
        """Application activity has no notes: the shared timeline view reads ``None``."""
        return None
