"""Document routes (Phase 02-2; ADR-0021 §5, §8). Mounted by ``app.api.tenant``.

``/api/v1/applications/{id}/documents`` and ``/api/v1/documents*``, one
permission per route, in the request transaction.

* **Upload** reads the multipart body itself, in chunks, and stops with 413 as
  soon as it exceeds :data:`MAX_REQUEST_BYTES` (a ``Content-Length`` above it
  is refused before reading). Exactly one file and at most three fields.
* **Download** streams the bytes as an attachment with ``nosniff`` (added to
  every API response by the middleware), a sandbox CSP and ``no-store``; the
  file name is sanitised at upload and encoded per RFC 6266/5987 here.
"""

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, Response, status
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app.core.authz import require_permission
from app.core.db.session import DbSession
from app.core.errors import ErrorDetail, PayloadTooLargeError, ValidationFailedError
from app.core.pagination import Pagination
from app.core.ratelimit import RateLimiter
from app.core.schemas import Envelope, ListEnvelope
from app.integrations.storage import ObjectStorage
from app.modules.documents import repository as repo
from app.modules.documents import service
from app.modules.documents.domain import DocumentStatus, DocumentType
from app.modules.documents.permissions import DOCUMENT_READ, DOCUMENT_UPLOAD, DOCUMENT_VERIFY
from app.modules.documents.schemas import (
    DocumentOut,
    DocumentsOut,
    QueueItem,
    RejectRequest,
    VerifyRequest,
)
from app.modules.documents.validation import MAX_REQUEST_BYTES

document_routes = APIRouter(tags=["tenant-documents"])
DOWNLOAD_CSP = "default-src 'none'; sandbox"


def object_storage(request: Request) -> ObjectStorage:
    storage: ObjectStorage = request.app.state.storage
    return storage


def upload_limiter(request: Request) -> RateLimiter:
    limiter: RateLimiter = request.app.state.upload_limiter
    return limiter


Storage = Annotated[ObjectStorage, Depends(object_storage)]
UploadLimiter = Annotated[RateLimiter, Depends(upload_limiter)]


def _invalid(field: str, code: str, message: str) -> ValidationFailedError:
    return ValidationFailedError(details=[ErrorDetail(field=field, code=code, message=message)])


def document_out(row: repo.DocumentRow) -> DocumentOut:
    return DocumentOut(
        id=row.id,
        application_id=row.application_id,
        document_type=DocumentType(row.document_type),
        status=DocumentStatus(row.status),
        rejection_reason=row.rejection_reason,
        file_name=row.file_name,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        uploaded_by=row.uploaded_by,
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        replaces_document_id=row.replaces_document_id,
        current=row.replaced_at is None,
        replaced_at=row.replaced_at,
        created_at=row.created_at,
        version=row.version,
    )


async def read_body(request: Request, limit: int = MAX_REQUEST_BYTES) -> bytes:
    """The request body, refused with 413 as soon as it exceeds ``limit`` bytes."""
    declared = request.headers.get("content-length")
    if declared is not None and (not declared.isdigit() or int(declared) > limit):
        raise PayloadTooLargeError()
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise PayloadTooLargeError()
    return bytes(body)


async def _replay(body: bytes) -> AsyncGenerator[bytes]:
    yield body


async def read_upload(
    request: Request,
) -> tuple[service.Upload, DocumentType, uuid.UUID | None]:
    """Parse the capped body: ``file`` (one), ``document_type``, ``replaces_document_id``."""
    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        raise _invalid("file", "multipart_required", "Upload the file as a form.")
    body = await read_body(request)
    parser = MultiPartParser(
        request.headers, _replay(body), max_files=1, max_fields=3, max_part_size=1024
    )
    try:
        form = await parser.parse()
    except MultiPartException:
        raise _invalid("file", "invalid_form", "Upload one file with its document type.") from None
    try:
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise _invalid("file", "file_empty", "Choose a file to upload.")
        raw_type = form.get("document_type")
        try:
            document_type = DocumentType(raw_type if isinstance(raw_type, str) else "")
        except ValueError:
            raise _invalid("document_type", "invalid", "Choose the document type.") from None
        raw_replaces = form.get("replaces_document_id")
        replaces: uuid.UUID | None = None
        if isinstance(raw_replaces, str) and raw_replaces:
            try:
                replaces = uuid.UUID(raw_replaces)
            except ValueError:
                raise _invalid("replaces_document_id", "invalid", "Choose a document.") from None
        data = await upload.read()
        return (
            service.Upload(upload.filename, upload.content_type, data),
            document_type,
            replaces,
        )
    finally:
        await form.close()


def attachment(file_name: str) -> str:
    """``Content-Disposition`` for a sanitised name: an ASCII fallback plus RFC 5987 UTF-8."""
    fallback = "".join(
        c if c.isascii() and c.isprintable() and c not in '"\\' else "_" for c in file_name
    )
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(file_name, safe='')}"


# --- Routes --------------------------------------------------------------------------------


@document_routes.get(
    "/applications/{application_id}/documents", dependencies=[require_permission(DOCUMENT_READ)]
)
async def list_documents(application_id: uuid.UUID, db: DbSession) -> Envelope[DocumentsOut]:
    rows = await service.list_documents(db, application_id)
    return Envelope(data=DocumentsOut(items=[document_out(row) for row in rows]))


@document_routes.post(
    "/applications/{application_id}/documents",
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(DOCUMENT_UPLOAD)],
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file", "document_type"],
                        "properties": {
                            "file": {"type": "string", "format": "binary"},
                            "document_type": {"type": "string"},
                            "replaces_document_id": {"type": "string", "format": "uuid"},
                        },
                    }
                }
            },
        }
    },
)
async def upload_document(
    application_id: uuid.UUID,
    request: Request,
    db: DbSession,
    storage: Storage,
    limiter: UploadLimiter,
) -> Envelope[DocumentOut]:
    who = await service.upload_caller(db, limiter)
    received, document_type, replaces = await read_upload(request)
    row = await service.upload(
        db,
        storage,
        who,
        application_id,
        document_type=document_type,
        replaces=replaces,
        received=received,
    )
    return Envelope(data=document_out(row))


@document_routes.get("/documents", dependencies=[require_permission(DOCUMENT_READ)])
async def verification_queue(
    db: DbSession,
    pagination: Pagination,
    q: Annotated[str | None, Query(max_length=200)] = None,
    document_status: Annotated[list[DocumentStatus] | None, Query(alias="status")] = None,
    document_type: Annotated[list[DocumentType] | None, Query(alias="type")] = None,
    campus: uuid.UUID | None = None,
) -> ListEnvelope[QueueItem]:
    """The verification queue: current documents, ``UNDER_REVIEW`` unless ``status`` says
    otherwise, oldest first."""
    rows, total = await service.verification_queue(
        db,
        statuses=tuple(document_status or (DocumentStatus.UNDER_REVIEW,)),
        types=tuple(document_type or ()),
        campus=campus,
        search=q.strip() if q and q.strip() else None,
        page=pagination,
    )
    return ListEnvelope.build(
        [QueueItem.model_validate(row, from_attributes=True) for row in rows],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@document_routes.get(
    "/documents/{document_id}/download", dependencies=[require_permission(DOCUMENT_READ)]
)
async def download_document(document_id: uuid.UUID, db: DbSession, storage: Storage) -> Response:
    found = await service.download(db, storage, document_id)
    return Response(
        content=found.data,
        media_type=found.content_type,
        headers={
            "Content-Disposition": attachment(found.file_name),
            "Content-Security-Policy": DOWNLOAD_CSP,
            "Cache-Control": "no-store",
        },
    )


@document_routes.post(
    "/documents/{document_id}/verify", dependencies=[require_permission(DOCUMENT_VERIFY)]
)
async def verify_document(
    document_id: uuid.UUID, body: VerifyRequest, db: DbSession
) -> Envelope[DocumentOut]:
    row = await service.decide(
        db, document_id, target=DocumentStatus.VERIFIED, reason=None, version=body.version
    )
    return Envelope(data=document_out(row))


@document_routes.post(
    "/documents/{document_id}/reject", dependencies=[require_permission(DOCUMENT_VERIFY)]
)
async def reject_document(
    document_id: uuid.UUID, body: RejectRequest, db: DbSession
) -> Envelope[DocumentOut]:
    row = await service.decide(
        db, document_id, target=DocumentStatus.REJECTED, reason=body.reason, version=body.version
    )
    return Envelope(data=document_out(row))
