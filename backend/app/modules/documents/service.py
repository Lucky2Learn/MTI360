"""Application documents: upload, queue, download, verify, reject (Phase 02-2; ADR-0021 §5, §8).

* Authorization goes through the parent application (campus rule; 404
  outside it). A document of another tenant or campus is not found.
* Upload order: authorize and validate (nothing stored yet) → store the bytes
  under a generated, tenant-prefixed key → write ``stored_files`` and the
  document. A storage failure writes nothing (503); a database failure after
  the bytes were stored deletes them (best effort). Commit failures can leave
  a private, unreferenced object (a recorded risk, ADR-0021 §8).
* Downloads re-authorize every time and return the bytes for the API to
  stream as an attachment; there are no public or presigned URLs.
* File content, names and checksums never reach audit metadata or logs.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import cast

from sqlalchemy import Table, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.activity import record_activity
from app.core.audit import AuditTarget, write_audit_event
from app.core.authz import Permission
from app.core.errors import (
    ConflictError,
    ErrorDetail,
    NotFoundError,
    RateLimitedError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.core.ids import new_id
from app.core.pagination import PageParams
from app.core.ratelimit import (
    Limit,
    RateLimiter,
    RateLimiterUnavailableError,
    RateLimitExceededError,
)
from app.integrations.storage import ObjectStorage, StorageError
from app.modules.applications.domain import (
    DOCUMENTS_OPEN,
    EDITABLE,
    FINAL,
    ActivityKind,
    ApplicationStatus,
)
from app.modules.applications.models import Application, ApplicationActivity
from app.modules.applications.service import authorized_application
from app.modules.documents import events
from app.modules.documents import repository as repo
from app.modules.documents.domain import (
    REASON_MAX_LENGTH,
    REPLACEABLE,
    VERIFICATION,
    DocumentStatus,
    DocumentType,
)
from app.modules.documents.models import ApplicationDocument, StoredFile, object_key
from app.modules.documents.permissions import DOCUMENT_READ, DOCUMENT_UPLOAD, DOCUMENT_VERIFY
from app.modules.documents.validation import MESSAGES, UploadRejectedError, validate_upload
from app.modules.leads.domain import clean_text
from app.modules.leads.service import Caller, caller

logger = logging.getLogger("app.documents")
ACTIVITIES = cast(Table, ApplicationActivity.__table__)
STALE = "This document was changed by someone else. Reload and try again."
UPLOAD_LIMIT = Limit(attempts=30, window_seconds=600)


def _invalid(field: str, code: str, message: str) -> ValidationFailedError:
    return ValidationFailedError(details=[ErrorDetail(field=field, code=code, message=message)])


@dataclass(frozen=True, slots=True)
class Upload:
    """A received multipart file: the client's name and declared type are untrusted."""

    file_name: str | None
    declared_type: str | None
    data: bytes


async def _activity(
    db: AsyncSession, who: Caller, application_id: uuid.UUID, kind: ActivityKind, **details: object
) -> None:
    await record_activity(
        db,
        ACTIVITIES,
        subject_column="application_id",
        subject_id=application_id,
        kind=kind.value,
        actor_membership_id=who.membership_id,
        details=details,
    )


async def _authorized_document(
    db: AsyncSession,
    who: Caller,
    document_id: uuid.UUID,
    permission: Permission,
    *,
    lock: bool = False,
) -> tuple[ApplicationDocument, Application]:
    """The document and its application, authorized through the application's campus (404)."""
    found = await repo.document(db, who.tenant_id, document_id, lock=lock)
    if found is None:
        raise NotFoundError()
    application = await authorized_application(db, who, found.application_id, permission)
    return found, application


async def _row(db: AsyncSession, who: Caller, document_id: uuid.UUID) -> repo.DocumentRow:
    row = await repo.document_row(db, who.tenant_id, document_id)
    if row is None:  # pragma: no cover - read in this transaction
        raise NotFoundError()
    return row


# --- Reads ---------------------------------------------------------------------------------


async def list_documents(db: AsyncSession, application_id: uuid.UUID) -> list[repo.DocumentRow]:
    who = await caller(db, DOCUMENT_READ)
    await authorized_application(db, who, application_id, DOCUMENT_READ)
    return await repo.documents_of(db, who.tenant_id, application_id)


async def verification_queue(
    db: AsyncSession,
    *,
    statuses: tuple[DocumentStatus, ...],
    types: tuple[DocumentType, ...],
    campus: uuid.UUID | None,
    search: str | None,
    page: PageParams,
) -> tuple[list[repo.QueueRow], int]:
    who = await caller(db, DOCUMENT_READ)
    return await repo.queue(
        db,
        who.tenant_id,
        who.context,
        statuses=statuses,
        types=types,
        campus=campus,
        search=search,
        page=page,
    )


@dataclass(frozen=True, slots=True)
class Download:
    file_name: str
    content_type: str
    data: bytes


async def download(db: AsyncSession, storage: ObjectStorage, document_id: uuid.UUID) -> Download:
    """Authorize, then read the bytes from private storage (``document.read``)."""
    who = await caller(db, DOCUMENT_READ)
    found, _ = await _authorized_document(db, who, document_id, DOCUMENT_READ)
    stored = await repo.stored_file(db, who.tenant_id, found.stored_file_id)
    if stored is None:  # pragma: no cover - composite foreign key
        raise NotFoundError()
    try:
        data = await storage.get(stored.object_key)
    except StorageError as error:
        logger.error("documents.download_failed", extra={"error_type": type(error).__name__})
        raise ServiceUnavailableError() from None
    return Download(stored.file_name, stored.content_type, data)


# --- Upload --------------------------------------------------------------------------------


async def upload_caller(db: AsyncSession, limiter: RateLimiter) -> Caller:
    """Authorize ``document.upload`` and count one upload (30 per member per 10 minutes)
    before the request body is read. The rate-limit store failing refuses the upload."""
    who = await caller(db, DOCUMENT_UPLOAD)
    try:
        await limiter.hit("membership", "document_upload", str(who.membership_id), UPLOAD_LIMIT)
    except RateLimitExceededError as error:
        raise RateLimitedError(retry_after=error.retry_after) from None
    except RateLimiterUnavailableError:
        raise ServiceUnavailableError() from None
    return who


async def upload(
    db: AsyncSession,
    storage: ObjectStorage,
    who: Caller,
    application_id: uuid.UUID,
    *,
    document_type: DocumentType,
    replaces: uuid.UUID | None,
    received: Upload,
) -> repo.DocumentRow:
    application = await authorized_application(db, who, application_id, DOCUMENT_UPLOAD, lock=True)
    status = ApplicationStatus(application.status)
    if status not in DOCUMENTS_OPEN:
        raise _invalid(
            "application", "documents_closed", "This application no longer takes documents."
        )
    replaced: ApplicationDocument | None = None
    if replaces is not None:
        replaced = await repo.document(db, who.tenant_id, replaces, lock=True)
        if (
            replaced is None
            or replaced.application_id != application.id
            or replaced.replaced_at is not None
            or DocumentStatus(replaced.status) not in REPLACEABLE
        ):
            raise _invalid(
                "replaces_document_id", "not_replaceable", "Choose a current document to replace."
            )
        if replaced.document_type != document_type.value:
            raise _invalid(
                "document_type", "type_mismatch", "A replacement keeps the document's type."
            )
    try:
        checked = validate_upload(received.file_name, received.declared_type, received.data)
    except UploadRejectedError as error:
        raise _invalid("file", error.problem.value, MESSAGES[error.problem]) from None

    file_id = new_id()
    key = object_key(who.tenant_id, file_id)
    try:
        await storage.put(key, received.data, content_type=checked.content_type)
    except StorageError as error:
        logger.error("documents.store_failed", extra={"error_type": type(error).__name__})
        raise ServiceUnavailableError() from None
    try:
        db.add(
            StoredFile(
                id=file_id,
                tenant_id=who.tenant_id,
                object_key=key,
                file_name=checked.file_name,
                content_type=checked.content_type,
                size_bytes=checked.size,
                sha256=checked.sha256,
                uploaded_by_membership_id=who.membership_id,
            )
        )
        await db.flush()  # no ORM relationships: the file row must exist before the document
        document = ApplicationDocument(
            tenant_id=who.tenant_id,
            application_id=application.id,
            stored_file_id=file_id,
            document_type=document_type.value,
            status=(
                DocumentStatus.UPLOADED if status in EDITABLE else DocumentStatus.UNDER_REVIEW
            ).value,
            uploaded_by_membership_id=who.membership_id,
            replaces_document_id=replaced.id if replaced else None,
        )
        db.add(document)
        if replaced is not None:
            replaced.replaced_at = func.now()
        await db.flush()
        await _activity(
            db,
            who,
            application.id,
            ActivityKind.DOCUMENT_UPLOADED,
            document_id=document.id,
            document_type=document_type.value,
            replaced=replaced is not None,
        )
        await write_audit_event(
            db,
            events.DOCUMENT_UPLOADED,
            target=AuditTarget("application_document", document.id),
            metadata={
                "document_type": document_type.value,
                "content_type": checked.content_type,
                "size_bytes": checked.size,
                "replacement": replaced is not None,
            },
        )
    except BaseException as error:
        await _discard(storage, key)
        if isinstance(error, IntegrityError):
            constraint = getattr(getattr(error.orig, "__cause__", None), "constraint_name", None)
            logger.warning("documents.upload_conflict", extra={"constraint": constraint})
            raise ConflictError(STALE) from None
        raise
    return await _row(db, who, document.id)


async def _discard(storage: ObjectStorage, key: str) -> None:
    try:
        await storage.delete(key)
    except StorageError as error:
        logger.error("documents.cleanup_failed", extra={"error_type": type(error).__name__})


# --- Verification --------------------------------------------------------------------------


async def decide(
    db: AsyncSession,
    document_id: uuid.UUID,
    *,
    target: DocumentStatus,
    reason: str | None,
    version: int,
) -> repo.DocumentRow:
    """Verify or reject a document under review (``document.verify``; reason to reject)."""
    who = await caller(db, DOCUMENT_VERIFY)
    found, application = await _authorized_document(
        db, who, document_id, DOCUMENT_VERIFY, lock=True
    )
    if found.version != version:
        raise ConflictError(STALE)
    try:
        clean_reason = clean_text(reason, REASON_MAX_LENGTH)
    except ValueError:
        raise _invalid("reason", "too_long", "Use at most 500 characters.") from None
    current = DocumentStatus(found.status)
    if (
        found.replaced_at is not None
        or ApplicationStatus(application.status) in FINAL
        or not VERIFICATION.allows(current, target)
    ):
        raise _invalid("status", "invalid_transition", "Only a document under review is decided.")
    if target is DocumentStatus.REJECTED and not clean_reason:
        raise _invalid("reason", "reason_required", "Enter why the document is rejected.")
    found.status = target.value
    found.rejection_reason = clean_reason if target is DocumentStatus.REJECTED else None
    found.reviewed_at = func.now()
    found.reviewed_by_membership_id = who.membership_id
    await db.flush()
    rejected = target is DocumentStatus.REJECTED
    activity: dict[str, object] = {"document_id": found.id, "document_type": found.document_type}
    if rejected:
        activity["reason"] = clean_reason
    await _activity(
        db,
        who,
        application.id,
        ActivityKind.DOCUMENT_REJECTED if rejected else ActivityKind.DOCUMENT_VERIFIED,
        **activity,
    )
    await write_audit_event(
        db,
        events.DOCUMENT_REJECTED if rejected else events.DOCUMENT_VERIFIED,
        target=AuditTarget("application_document", found.id),
        metadata={"document_type": found.document_type, "has_reason": rejected},
    )
    return await _row(db, who, found.id)
