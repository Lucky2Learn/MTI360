"""Finance-lite tables (Phase 02-5; ADR-0022; migration ``0011``).

* ``fee_structures`` — the fee heads of one course, institute-wide like the
  course. ``items`` is frozen once the structure leaves ``DRAFT`` (trigger);
  at most one ``ACTIVE`` structure per course.
* ``invoices`` — non-tax fee invoices (§2): one live invoice per admission;
  ``(admission_id, student_id, campus_id, course_id)`` must be one admission's
  (a single composite key). ``paid_minor`` is the sum of confirmed payments.
* ``invoice_lines`` — copied at issue with the structure's amount beside the
  issued one (§7). Insert-only.
* ``payments`` — offline payments (§4); ``(invoice_id, student_id,
  campus_id)`` must be one invoice's.
* ``receipts`` — one per confirmed payment, numbered by financial year (§3).
  Insert-only; a reversed payment's receipt is shown as cancelled.
* ``finance_activities`` — the fee invoice's business timeline. Append-only.

Tenant-scoped with realm-agnostic tenant Row-Level Security; the runtime role
has no DELETE privilege on any of them. Amounts are integer paise in INR.
"""

import uuid
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TimestampMixin, VersionedMixin
from app.core.sequences import NUMBER_MAX_LENGTH
from app.core.tenancy import TenantScopedMixin, tenant_foreign_key
from app.modules.finance.domain import (
    CLEARANCE_METHODS,
    CURRENCY,
    FEE_HEAD_MAX_LENGTH,
    MAX_AMOUNT_MINOR,
    NAME_MAX_LENGTH,
    REASON_MAX_LENGTH,
    REFERENCE_MAX_LENGTH,
    REQUEST_HASH_LENGTH,
    ActivityKind,
    FeeStructureStatus,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
)


def _in(column: str, values: Iterable[str]) -> str:
    return f"{column} IN ({', '.join(repr(str(value)) for value in values)})"


def _amount(column: str, *, positive: bool) -> str:
    low = f"{column} > 0" if positive else f"{column} >= 0"
    return f"{low} AND {column} <= {MAX_AMOUNT_MINOR}"


_CURRENCY = f"currency = '{CURRENCY}'"
_CLEARANCE = _in("method", sorted(CLEARANCE_METHODS))


class FeeStructure(TenantScopedMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "fee_structures"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_foreign_key("course_id", "courses", name="fk_fee_structures_course"),
        tenant_foreign_key(
            "created_by_membership_id", "tenant_memberships", name="fk_fee_structures_created_by"
        ),
        CheckConstraint("btrim(name) <> ''", name="name"),
        CheckConstraint(_in("status", FeeStructureStatus), name="status"),
        CheckConstraint("jsonb_typeof(items) = 'array'", name="items_array"),
        CheckConstraint(_amount("total_minor", positive=True), name="total_minor"),
        CheckConstraint(_CURRENCY, name="currency"),
        CheckConstraint("(status = 'DRAFT') = (activated_at IS NULL)", name="activated_at"),
        CheckConstraint("(status = 'ARCHIVED') = (archived_at IS NOT NULL)", name="archived_at"),
        Index(None, "tenant_id", "course_id", "status"),
        Index(
            "uq_fee_structures_tenant_id_course_id_active",
            "tenant_id",
            "course_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    course_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Invoice(TenantScopedMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "number"),
        UniqueConstraint("tenant_id", "idempotency_key"),
        # Target of the payment's composite key.
        UniqueConstraint("tenant_id", "id", "student_id", "campus_id"),
        ForeignKeyConstraint(
            ["tenant_id", "admission_id", "student_id", "campus_id", "course_id"],
            [
                "admissions.tenant_id",
                "admissions.id",
                "admissions.student_id",
                "admissions.campus_id",
                "admissions.course_id",
            ],
            name="fk_invoices_admission",
            ondelete="RESTRICT",
        ),
        tenant_foreign_key("fee_structure_id", "fee_structures", name="fk_invoices_fee_structure"),
        tenant_foreign_key(
            "issued_by_membership_id", "tenant_memberships", name="fk_invoices_issued_by"
        ),
        tenant_foreign_key(
            "cancelled_by_membership_id", "tenant_memberships", name="fk_invoices_cancelled_by"
        ),
        CheckConstraint(_in("status", InvoiceStatus), name="status"),
        CheckConstraint(_amount("total_minor", positive=True), name="total_minor"),
        CheckConstraint(_amount("structure_total_minor", positive=True), name="structure_total"),
        CheckConstraint("paid_minor >= 0 AND paid_minor <= total_minor", name="paid_minor"),
        CheckConstraint(
            "(status IN ('ISSUED', 'CANCELLED') AND paid_minor = 0) "
            "OR (status = 'PARTIALLY_PAID' AND paid_minor > 0 AND paid_minor < total_minor) "
            "OR (status = 'PAID' AND paid_minor = total_minor)",
            name="status_paid",
        ),
        CheckConstraint(_CURRENCY, name="currency"),
        CheckConstraint("adjusted = (adjustment_reason IS NOT NULL)", name="adjustment_reason"),
        CheckConstraint(
            "(status = 'CANCELLED') = (status_reason IS NOT NULL)", name="status_reason"
        ),
        CheckConstraint(
            "(status = 'CANCELLED') = (cancelled_at IS NOT NULL) "
            "AND (cancelled_at IS NULL) = (cancelled_by_membership_id IS NULL)",
            name="cancelled",
        ),
        CheckConstraint(f"char_length(request_hash) = {REQUEST_HASH_LENGTH}", name="request_hash"),
        Index(None, "tenant_id", "campus_id", "status", "due_date"),
        Index(None, "tenant_id", "student_id"),
        Index(None, "tenant_id", "issued_at"),
        Index(
            "uq_invoices_tenant_id_admission_id_live",
            "tenant_id",
            "admission_id",
            unique=True,
            postgresql_where=text("status <> 'CANCELLED'"),
        ),
    )

    number: Mapped[str] = mapped_column(String(NUMBER_MAX_LENGTH), nullable=False)
    admission_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    campus_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    fee_structure_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    fee_structure_version: Mapped[int] = mapped_column(nullable=False)
    structure_total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    paid_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    adjusted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    adjustment_reason: Mapped[str | None] = mapped_column(String(REASON_MAX_LENGTH))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    status_reason: Mapped[str | None] = mapped_column(String(REASON_MAX_LENGTH))
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    issued_by_membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_membership_id: Mapped[uuid.UUID | None] = mapped_column()
    idempotency_key: Mapped[uuid.UUID] = mapped_column(nullable=False)
    request_hash: Mapped[str] = mapped_column(String(REQUEST_HASH_LENGTH), nullable=False)


class InvoiceLine(TenantScopedMixin, Base):
    __tablename__ = "invoice_lines"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "invoice_id", "position"),
        tenant_foreign_key("invoice_id", "invoices", name="fk_invoice_lines_invoice"),
        CheckConstraint("position BETWEEN 1 AND 100", name="position"),
        CheckConstraint("btrim(fee_head) <> ''", name="fee_head"),
        CheckConstraint(_amount("amount_minor", positive=False), name="amount_minor"),
        CheckConstraint(
            "structure_amount_minor IS NULL OR "
            f"({_amount('structure_amount_minor', positive=False)})",
            name="structure_amount_minor",
        ),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fee_head: Mapped[str] = mapped_column(String(FEE_HEAD_MAX_LENGTH), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    structure_amount_minor: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, sort_order=90
    )


class Payment(TenantScopedMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "idempotency_key"),
        ForeignKeyConstraint(
            ["tenant_id", "invoice_id", "student_id", "campus_id"],
            ["invoices.tenant_id", "invoices.id", "invoices.student_id", "invoices.campus_id"],
            name="fk_payments_invoice",
            ondelete="RESTRICT",
        ),
        tenant_foreign_key(
            "recorded_by_membership_id", "tenant_memberships", name="fk_payments_recorded_by"
        ),
        tenant_foreign_key(
            "confirmed_by_membership_id", "tenant_memberships", name="fk_payments_confirmed_by"
        ),
        tenant_foreign_key(
            "closed_by_membership_id", "tenant_memberships", name="fk_payments_closed_by"
        ),
        CheckConstraint(_amount("amount_minor", positive=True), name="amount_minor"),
        CheckConstraint(_CURRENCY, name="currency"),
        CheckConstraint(_in("method", PaymentMethod), name="method"),
        CheckConstraint(_in("status", PaymentStatus), name="status"),
        CheckConstraint(
            "method = 'CASH' OR (reference IS NOT NULL AND btrim(reference) <> '')",
            name="reference",
        ),
        CheckConstraint(
            f"status NOT IN ('PENDING', 'FAILED') OR {_CLEARANCE}", name="clearance_method"
        ),
        CheckConstraint(
            "(status IN ('FAILED', 'REVERSED')) = (status_reason IS NOT NULL)",
            name="status_reason",
        ),
        CheckConstraint(
            "(status IN ('CONFIRMED', 'REVERSED')) = (confirmed_at IS NOT NULL) "
            "AND (confirmed_at IS NULL) = (confirmed_by_membership_id IS NULL)",
            name="confirmed",
        ),
        CheckConstraint(
            "(status IN ('FAILED', 'REVERSED')) = (closed_at IS NOT NULL) "
            "AND (closed_at IS NULL) = (closed_by_membership_id IS NULL)",
            name="closed",
        ),
        CheckConstraint(f"char_length(request_hash) = {REQUEST_HASH_LENGTH}", name="request_hash"),
        Index(None, "tenant_id", "invoice_id"),
        Index(None, "tenant_id", "campus_id", "status", "received_on"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    campus_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(REFERENCE_MAX_LENGTH))
    received_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    status_reason: Mapped[str | None] = mapped_column(String(REASON_MAX_LENGTH))
    recorded_by_membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by_membership_id: Mapped[uuid.UUID | None] = mapped_column()
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by_membership_id: Mapped[uuid.UUID | None] = mapped_column()
    idempotency_key: Mapped[uuid.UUID] = mapped_column(nullable=False)
    request_hash: Mapped[str] = mapped_column(String(REQUEST_HASH_LENGTH), nullable=False)


class Receipt(TenantScopedMixin, Base):
    __tablename__ = "receipts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "number"),
        UniqueConstraint("tenant_id", "payment_id"),
        tenant_foreign_key("payment_id", "payments", name="fk_receipts_payment"),
        CheckConstraint(_amount("amount_minor", positive=True), name="amount_minor"),
        CheckConstraint(_CURRENCY, name="currency"),
        CheckConstraint(_in("method", PaymentMethod), name="method"),
    )

    number: Mapped[str] = mapped_column(String(NUMBER_MAX_LENGTH), nullable=False)
    payment_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(NUMBER_MAX_LENGTH), nullable=False)
    student_number: Mapped[str] = mapped_column(String(NUMBER_MAX_LENGTH), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, sort_order=90
    )


class FinanceActivity(TenantScopedMixin, Base):
    __tablename__ = "finance_activities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_foreign_key("invoice_id", "invoices", name="fk_finance_activities_invoice"),
        tenant_foreign_key(
            "actor_membership_id", "tenant_memberships", name="fk_finance_activities_actor"
        ),
        CheckConstraint(_in("kind", ActivityKind), name="kind"),
        CheckConstraint("jsonb_typeof(details) = 'object'", name="details_object"),
        Index(None, "tenant_id", "invoice_id", "created_at"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_membership_id: Mapped[uuid.UUID | None] = mapped_column()
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, sort_order=90
    )
