"""Batch tables (Phase 02-6; migration ``0014``).

* ``batches`` — one intake of one course at one campus. ``UNIQUE (tenant_id,
  code)``; ``UNIQUE (tenant_id, id, course_id, campus_id)`` is the target of
  the allocation's key, so an allocation's course and campus are its batch's.
  ``allocated_count`` is maintained **by the database** (trigger
  ``batch_allocations_count``) and checked against ``capacity``: no code path,
  concurrent or not, can over-fill a batch or allocate into a batch that is
  not ``OPEN``.
* ``batch_allocations`` — admission ↔ batch history. Its admission, student,
  course and campus are one admission's (the five-column key of ``0011``) and
  its batch's (above). One ``ACTIVE`` allocation per admission (partial
  unique index). Never deleted (no DELETE privilege): ending keeps the row.
* ``batch_activities`` — append-only work history of batches and allocations
  (the Student 360 timeline reads the allocation kinds).

Tenant-scoped with realm-agnostic tenant Row-Level Security.
"""

import uuid
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TimestampMixin, VersionedMixin
from app.core.tenancy import TenantScopedMixin, tenant_foreign_key
from app.modules.batches.domain import (
    CAPACITY_MAX,
    CAPACITY_MIN,
    CODE_MAX_LENGTH,
    CODE_PATTERN,
    INTAKE_MAX_LENGTH,
    NAME_MAX_LENGTH,
    REASON_MAX_LENGTH,
    ActivityKind,
    AllocationStatus,
    BatchStatus,
    EndReason,
    InvoiceState,
    PaymentBasis,
)


def _in(column: str, values: Iterable[str]) -> str:
    return f"{column} IN ({', '.join(repr(str(value)) for value in values)})"


class Batch(TenantScopedMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "batches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "code"),
        UniqueConstraint("tenant_id", "id", "course_id", "campus_id"),
        tenant_foreign_key("course_id", "courses", name="fk_batches_course"),
        tenant_foreign_key("campus_id", "campuses", name="fk_batches_campus"),
        tenant_foreign_key(
            "created_by_membership_id", "tenant_memberships", name="fk_batches_created_by"
        ),
        CheckConstraint(f"code ~ '{CODE_PATTERN}'", name="code_format"),
        CheckConstraint("btrim(name) <> ''", name="name"),
        CheckConstraint("intake_label IS NULL OR btrim(intake_label) <> ''", name="intake_label"),
        CheckConstraint(f"capacity BETWEEN {CAPACITY_MIN} AND {CAPACITY_MAX}", name="capacity"),
        CheckConstraint(
            "allocated_count >= 0 AND allocated_count <= capacity", name="allocated_count"
        ),
        CheckConstraint("end_date >= start_date", name="dates"),
        CheckConstraint(_in("status", BatchStatus), name="status"),
        CheckConstraint("status <> 'CANCELLED' OR allocated_count = 0", name="cancelled_empty"),
        Index(None, "tenant_id", "campus_id", "status", "start_date"),
        Index(None, "tenant_id", "course_id", "status"),
    )

    course_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    campus_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    code: Mapped[str] = mapped_column(String(CODE_MAX_LENGTH), nullable=False)
    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), nullable=False)
    intake_label: Mapped[str | None] = mapped_column(String(INTAKE_MAX_LENGTH))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    allocated_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    status_reason: Mapped[str | None] = mapped_column(String(REASON_MAX_LENGTH))
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)


class BatchAllocation(TenantScopedMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "batch_allocations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "batch_id", "course_id", "campus_id"],
            ["batches.tenant_id", "batches.id", "batches.course_id", "batches.campus_id"],
            name="fk_batch_allocations_batch",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "admission_id", "student_id", "campus_id", "course_id"],
            [
                "admissions.tenant_id",
                "admissions.id",
                "admissions.student_id",
                "admissions.campus_id",
                "admissions.course_id",
            ],
            name="fk_batch_allocations_admission",
            ondelete="RESTRICT",
        ),
        tenant_foreign_key(
            "transferred_from_id", "batch_allocations", name="fk_batch_allocations_from"
        ),
        tenant_foreign_key(
            "allocated_by_membership_id",
            "tenant_memberships",
            name="fk_batch_allocations_allocated_by",
        ),
        tenant_foreign_key(
            "ended_by_membership_id", "tenant_memberships", name="fk_batch_allocations_ended_by"
        ),
        CheckConstraint(_in("status", AllocationStatus), name="status"),
        CheckConstraint(f"end_reason IS NULL OR {_in('end_reason', EndReason)}", name="end_reason"),
        CheckConstraint(
            "(status = 'ENDED') = (end_reason IS NOT NULL) "
            "AND (status = 'ENDED') = (ended_at IS NOT NULL) "
            "AND (status = 'ENDED') = (ended_by_membership_id IS NOT NULL)",
            name="ended",
        ),
        CheckConstraint(
            "(end_reason IS NULL) = (end_note IS NULL) "
            "AND (end_note IS NULL OR btrim(end_note) <> '')",
            name="end_note",
        ),
        CheckConstraint(_in("payment_basis", PaymentBasis), name="payment_basis"),
        CheckConstraint(
            "(payment_basis = 'TRANSFER') = (transferred_from_id IS NOT NULL)",
            name="transfer_basis",
        ),
        CheckConstraint(
            "(payment_basis = 'OVERRIDE') = (override_reason IS NOT NULL) "
            "AND (payment_basis = 'OVERRIDE') = (override_invoice_state IS NOT NULL) "
            "AND (override_reason IS NULL OR btrim(override_reason) <> '')",
            name="override",
        ),
        CheckConstraint(
            f"override_invoice_state IS NULL OR "
            f"({_in('override_invoice_state', InvoiceState)} "
            "AND override_invoice_state <> 'PAID')",
            name="override_invoice_state",
        ),
        CheckConstraint(
            "override_outstanding_minor IS NULL OR "
            "(payment_basis = 'OVERRIDE' AND override_outstanding_minor > 0)",
            name="override_outstanding",
        ),
        Index(None, "tenant_id", "batch_id", "status"),
        Index(None, "tenant_id", "student_id"),
        Index(None, "tenant_id", "admission_id"),
        Index(
            "uq_batch_allocations_tenant_id_admission_id_active",
            "tenant_id",
            "admission_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    campus_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    admission_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    payment_basis: Mapped[str] = mapped_column(String(16), nullable=False)
    override_reason: Mapped[str | None] = mapped_column(String(REASON_MAX_LENGTH))
    override_invoice_state: Mapped[str | None] = mapped_column(String(16))
    override_outstanding_minor: Mapped[int | None] = mapped_column(BigInteger)
    transferred_from_id: Mapped[uuid.UUID | None] = mapped_column()
    allocated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    allocated_by_membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    end_reason: Mapped[str | None] = mapped_column(String(16))
    end_note: Mapped[str | None] = mapped_column(String(REASON_MAX_LENGTH))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_by_membership_id: Mapped[uuid.UUID | None] = mapped_column()


class BatchActivity(TenantScopedMixin, Base):
    __tablename__ = "batch_activities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_foreign_key("batch_id", "batches", name="fk_batch_activities_batch"),
        tenant_foreign_key(
            "allocation_id", "batch_allocations", name="fk_batch_activities_allocation"
        ),
        tenant_foreign_key(
            "actor_membership_id", "tenant_memberships", name="fk_batch_activities_actor"
        ),
        CheckConstraint(_in("kind", ActivityKind), name="kind"),
        CheckConstraint("jsonb_typeof(details) = 'object'", name="details_object"),
        Index(None, "tenant_id", "batch_id", "created_at"),
        Index(None, "tenant_id", "allocation_id"),
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    allocation_id: Mapped[uuid.UUID | None] = mapped_column()
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_membership_id: Mapped[uuid.UUID | None] = mapped_column()
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, sort_order=90
    )
