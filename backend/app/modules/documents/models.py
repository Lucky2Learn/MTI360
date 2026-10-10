"""Document tables (Phase 02-2; ADR-0021 §5, §8, §13).

* ``stored_files`` — object-storage metadata (ARCHITECTURE §7): the
  generated object key, the sanitised display name, the verified content
  type, size and SHA-256, and the uploader. Immutable: the runtime role may
  only SELECT and INSERT. A CHECK ties the key to the row's own tenant and
  ID (``tenants/<tenant_id>/files/<id>``), so no row can point into another
  tenant's prefix and no client-chosen key can exist.
* ``application_documents`` — one uploaded document of an application. A
  re-upload is a new row naming the one it replaces (at most one
  replacement each); nothing is deleted.

Both are tenant-scoped with the realm-agnostic tenant RLS of migration
``0010`` and composite tenant foreign keys.
"""

import uuid
from collections.abc import Iterable
from datetime import datetime

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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TimestampMixin, VersionedMixin
from app.core.tenancy import TenantScopedMixin, tenant_foreign_key
from app.modules.documents.domain import REASON_MAX_LENGTH, DocumentStatus, DocumentType
from app.modules.documents.validation import ALLOWED_TYPES, FILE_NAME_MAX_LENGTH, MAX_FILE_BYTES

OBJECT_KEY_MAX_LENGTH = 200


def _in(column: str, values: Iterable[str]) -> str:
    return f"{column} IN ({', '.join(repr(str(value)) for value in values)})"


def object_key(tenant_id: uuid.UUID, file_id: uuid.UUID) -> str:
    """The only object key a stored file may have (also enforced by a CHECK)."""
    return f"tenants/{tenant_id}/files/{file_id}"


class StoredFile(TenantScopedMixin, Base):
    __tablename__ = "stored_files"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_foreign_key(
            "uploaded_by_membership_id", "tenant_memberships", name="fk_stored_files_uploaded_by"
        ),
        CheckConstraint(
            "object_key = 'tenants/' || tenant_id::text || '/files/' || id::text",
            name="object_key",
        ),
        CheckConstraint("btrim(file_name) <> ''", name="file_name"),
        CheckConstraint(_in("content_type", sorted(ALLOWED_TYPES)), name="content_type"),
        CheckConstraint(f"size_bytes > 0 AND size_bytes <= {MAX_FILE_BYTES}", name="size_bytes"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
    )

    object_key: Mapped[str] = mapped_column(String(OBJECT_KEY_MAX_LENGTH), nullable=False)
    file_name: Mapped[str] = mapped_column(String(FILE_NAME_MAX_LENGTH), nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by_membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, sort_order=90
    )


class ApplicationDocument(TenantScopedMixin, TimestampMixin, VersionedMixin, Base):
    __tablename__ = "application_documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "stored_file_id"),
        tenant_foreign_key(
            "application_id", "applications", name="fk_application_documents_application"
        ),
        tenant_foreign_key("stored_file_id", "stored_files", name="fk_application_documents_file"),
        tenant_foreign_key(
            "uploaded_by_membership_id",
            "tenant_memberships",
            name="fk_application_documents_uploaded_by",
        ),
        tenant_foreign_key(
            "reviewed_by_membership_id",
            "tenant_memberships",
            name="fk_application_documents_reviewed_by",
        ),
        tenant_foreign_key(
            "replaces_document_id",
            "application_documents",
            name="fk_application_documents_replaces",
        ),
        CheckConstraint(
            _in("document_type", [t.value for t in DocumentType]), name="document_type"
        ),
        CheckConstraint(_in("status", [s.value for s in DocumentStatus]), name="status"),
        CheckConstraint(
            "(status = 'REJECTED') = (rejection_reason IS NOT NULL)", name="rejection_reason"
        ),
        CheckConstraint(
            "(status IN ('VERIFIED', 'REJECTED')) = (reviewed_at IS NOT NULL)", name="reviewed_at"
        ),
        CheckConstraint(
            "(reviewed_at IS NULL) = (reviewed_by_membership_id IS NULL)", name="reviewed_by"
        ),
        CheckConstraint("replaces_document_id <> id", name="replaces_not_self"),
        Index(None, "tenant_id", "application_id", "document_type"),
        Index(None, "tenant_id", "status", "created_at"),
        Index(
            "uq_application_documents_tenant_id_replaces_document_id",
            "tenant_id",
            "replaces_document_id",
            unique=True,
            postgresql_where=text("replaces_document_id IS NOT NULL"),
        ),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    stored_file_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(REASON_MAX_LENGTH))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_membership_id: Mapped[uuid.UUID | None] = mapped_column()
    uploaded_by_membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    replaces_document_id: Mapped[uuid.UUID | None] = mapped_column()
    replaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
