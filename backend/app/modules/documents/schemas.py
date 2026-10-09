"""Document API contracts (Phase 02-2; ADR-0021 §5, §8).

Uploads are ``multipart/form-data`` (``file``, ``document_type``, optional
``replaces_document_id``), read by the router with a streaming size cap;
these models describe the JSON requests and responses. Responses never carry
an object key, bucket, checksum or URL.
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints

from app.core.schemas import RequestModel, ResponseModel
from app.modules.applications.domain import ApplicationStatus
from app.modules.documents.domain import REASON_MAX_LENGTH, DocumentStatus, DocumentType

Version = Annotated[int, Field(ge=1)]


class VerifyRequest(RequestModel):
    version: Version


class RejectRequest(RequestModel):
    reason: Annotated[str, StringConstraints(min_length=1, max_length=REASON_MAX_LENGTH)]
    version: Version


class DocumentOut(ResponseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    document_type: DocumentType
    status: DocumentStatus
    rejection_reason: str | None
    file_name: str
    content_type: str
    size_bytes: int
    uploaded_by: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    replaces_document_id: uuid.UUID | None
    current: bool
    replaced_at: datetime | None
    created_at: datetime
    version: int


class DocumentsOut(ResponseModel):
    items: list[DocumentOut]


class QueueItem(ResponseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    application_number: str
    applicant_name: str
    application_status: ApplicationStatus
    course_code: str
    campus_code: str
    document_type: DocumentType
    status: DocumentStatus
    file_name: str
    content_type: str
    size_bytes: int
    uploaded_by: str | None
    created_at: datetime
    version: int
