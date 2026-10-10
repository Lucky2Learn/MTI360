"""Student, admission and number-sequence tables (Phase 02-2; ADR-0021 §2, §6-§7, §13).

* Numbers (student and admission) come from ``tenant_sequences``, which now
  lives in :mod:`app.core.sequences` (ADR-0022 §3).
* ``students`` — the person across courses. The home campus is the campus of
  the first admission (L6); the details are copied from that application.
  ``mobile_key`` / ``email_normalized`` serve the explicit-link candidates
  only (never an automatic match, ADR-0021 Y6).
* ``admissions`` — one per application (``UNIQUE (tenant_id,
  application_id)``: a repeated or concurrent admit cannot create two).

Tenant-scoped with the realm-agnostic tenant RLS of migration ``0010`` and
composite tenant foreign keys; no DELETE privilege.
"""

import uuid
from collections.abc import Iterable
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TimestampMixin, VersionedMixin
from app.core.sequences import NUMBER_MAX_LENGTH
from app.core.tenancy import TenantScopedMixin, tenant_foreign_key
from app.modules.students.domain import AdmissionStatus, StudentStatus


def _in(column: str, values: Iterable[str]) -> str:
    return f"{column} IN ({', '.join(repr(str(value)) for value in values)})"


class Student(TenantScopedMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "student_number"),
        tenant_foreign_key("home_campus_id", "campuses", name="fk_students_home_campus"),
        tenant_foreign_key(
            "created_by_membership_id", "tenant_memberships", name="fk_students_created_by"
        ),
        CheckConstraint("btrim(full_name) <> ''", name="full_name"),
        CheckConstraint("(mobile IS NULL) = (mobile_key IS NULL)", name="mobile_key"),
        CheckConstraint("(email IS NULL) = (email_normalized IS NULL)", name="email_normalized"),
        CheckConstraint(_in("status", [s.value for s in StudentStatus]), name="status"),
        Index(None, "tenant_id", "home_campus_id", "created_at"),
        Index(
            "ix_students_tenant_id_mobile_key",
            "tenant_id",
            "mobile_key",
            postgresql_where=text("mobile_key IS NOT NULL"),
        ),
        Index(
            "ix_students_tenant_id_email_normalized",
            "tenant_id",
            "email_normalized",
            postgresql_where=text("email_normalized IS NOT NULL"),
        ),
    )

    student_number: Mapped[str] = mapped_column(String(NUMBER_MAX_LENGTH), nullable=False)
    home_campus_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'ACTIVE'"))
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    mobile: Mapped[str | None] = mapped_column(String(32))
    mobile_key: Mapped[str | None] = mapped_column(String(16))
    email: Mapped[str | None] = mapped_column(String(254))
    email_normalized: Mapped[str | None] = mapped_column(String(254))
    city: Mapped[str | None] = mapped_column(String(120))
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)


class Admission(TenantScopedMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "admissions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "admission_number"),
        UniqueConstraint("tenant_id", "application_id"),
        tenant_foreign_key("application_id", "applications", name="fk_admissions_application"),
        tenant_foreign_key("student_id", "students", name="fk_admissions_student"),
        tenant_foreign_key("course_id", "courses", name="fk_admissions_course"),
        tenant_foreign_key("campus_id", "campuses", name="fk_admissions_campus"),
        tenant_foreign_key(
            "approved_by_membership_id", "tenant_memberships", name="fk_admissions_approved_by"
        ),
        CheckConstraint(_in("status", [s.value for s in AdmissionStatus]), name="status"),
        Index(None, "tenant_id", "student_id"),
        Index(None, "tenant_id", "campus_id", "created_at"),
    )

    admission_number: Mapped[str] = mapped_column(String(NUMBER_MAX_LENGTH), nullable=False)
    application_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    campus_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'ADMITTED'")
    )
    approved_by_membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
