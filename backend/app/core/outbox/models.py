"""``outbox_messages``: the transactional outbox (Phase 02-4, ADR-0024).

A message is written in the same transaction as the business change that
causes it (a public enquiry and its acknowledgement), so either both exist or
neither does. The worker (``python -m app.worker``) delivers it afterwards.

* Tenant-scoped (:class:`TenantScopedMixin`) with tenant Row-Level Security;
  migration ``0012`` adds a system-realm policy so the worker can claim
  messages of every tenant. The application role has no DELETE privilege.
* ``payload`` holds identifiers only, never personal data: the worker reads
  the current values when it delivers.
* ``(tenant_id, idempotency_key)`` is unique: a cause enqueues its message once.
* Status ``PENDING → PROCESSING → SENT``, or back to ``PENDING`` with a later
  ``available_at`` after a temporary failure, or ``FAILED`` after
  ``max_attempts`` or a permanent failure. ``last_error`` is an error class
  name, never provider text.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TimestampMixin
from app.core.outbox.states import ERROR_MAX_LENGTH, KIND_MAX_LENGTH, OutboxStatus
from app.core.tenancy import TenantScopedMixin


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class OutboxMessage(TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "outbox_messages"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "idempotency_key"),
        CheckConstraint(_in("status", [s.value for s in OutboxStatus]), name="status"),
        CheckConstraint("attempts >= 0 AND attempts <= max_attempts", name="attempts"),
        CheckConstraint("max_attempts BETWEEN 1 AND 20", name="max_attempts"),
        CheckConstraint(
            "(status = 'PROCESSING') = (locked_at IS NOT NULL AND locked_by IS NOT NULL)",
            name="locked",
        ),
        CheckConstraint("(status = 'SENT') = (sent_at IS NOT NULL)", name="sent_at"),
        CheckConstraint("(status = 'FAILED') = (failed_at IS NOT NULL)", name="failed_at"),
        Index(
            "ix_outbox_messages_ready",
            "available_at",
            postgresql_where=text("status = 'PENDING'"),
        ),
        Index(
            "ix_outbox_messages_processing",
            "locked_at",
            postgresql_where=text("status = 'PROCESSING'"),
        ),
    )

    kind: Mapped[str] = mapped_column(String(KIND_MAX_LENGTH), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'PENDING'")
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(64))
    last_error: Mapped[str | None] = mapped_column(String(ERROR_MAX_LENGTH))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
