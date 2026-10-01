"""``audit_events``: the append-only audit table (T01-02; ADR-0013).

One table for every audit category, including security events. It is
**mixed-scope**: ``tenant_id`` is the tenant of a tenant-scoped event and
``NULL`` for platform, system and pre-authentication events.

Deliberate exceptions to the tenant-table conventions (ADR-0013 §3):

* ``tenant_id`` has no foreign key: the ``tenants`` table arrives in T01-03,
  and audit history must outlive tenant records anyway. ``principal_id`` and
  ``target_id`` have none either (their tables belong to later tasks or to
  any module), and there are no relationships.
* Not :class:`TenantScopedMixin`: the table is mixed-scope and protected by
  its own Row-Level Security policies (migration ``0002``).
* No ``updated_at`` or ``version``: rows are immutable. The runtime role may
  only SELECT and INSERT; triggers reject UPDATE, DELETE and TRUNCATE.

Rows are written only by :mod:`app.core.audit.writer`, with a plain INSERT
(no ``RETURNING``, which RLS would also check against the read policy).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.audit.events import (
    EVENT_TYPE_MAX_LENGTH,
    EVENT_TYPE_PATTERN,
    TARGET_TYPE_MAX_LENGTH,
    TARGET_TYPE_PATTERN,
    AuditCategory,
)
from app.core.context import Realm
from app.core.db.base import Base, UUIDPrimaryKeyMixin

METADATA_MAX_DATABASE_BYTES = 8192
"""Database ceiling for the serialized metadata; the writer's own limit is lower."""


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(_in("realm", [realm.value for realm in Realm]), name="realm"),
        CheckConstraint(_in("category", [c.value for c in AuditCategory]), name="category"),
        CheckConstraint(f"event_type ~ '{EVENT_TYPE_PATTERN}'", name="event_type_format"),
        CheckConstraint(f"target_type ~ '{TARGET_TYPE_PATTERN}'", name="target_type_format"),
        CheckConstraint("target_id IS NULL OR target_type IS NOT NULL", name="target_has_type"),
        CheckConstraint("jsonb_typeof(metadata) = 'object'", name="metadata_is_object"),
        CheckConstraint(
            f"octet_length(metadata::text) <= {METADATA_MAX_DATABASE_BYTES}",
            name="metadata_size",
        ),
        # Tenant audit read (T01-08): one tenant's events, newest first.
        Index(None, "tenant_id", "created_at"),
        # Platform audit and security-event views (T01-07): by category, newest first.
        Index(None, "category", "created_at"),
        # Correlation with the request log (support, incident analysis).
        Index(None, "request_id"),
    )

    # Same column as TimestampMixin.created_at; there is no updated_at.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, sort_order=90
    )
    request_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    realm: Mapped[str] = mapped_column(String(16), nullable=False)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    principal_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(EVENT_TYPE_MAX_LENGTH), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(TARGET_TYPE_MAX_LENGTH), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    # ``metadata`` is reserved on declarative classes, hence the attribute name.
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
