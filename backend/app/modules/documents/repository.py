"""Document data access (Phase 02-2; ADR-0021 §5, §8).

Statements state the trusted tenant; the ORM tenant filter and Row-Level
Security add it again. Documents are authorized through their application's
campus: lists apply :func:`app.core.authz.campus_visibility` to it.
"""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.authz import campus_visibility
from app.core.context import RequestContext
from app.core.pagination import PageParams
from app.core.search import escape_like
from app.modules.applications.models import Application
from app.modules.courses.models import Course
from app.modules.documents.domain import DocumentStatus, DocumentType
from app.modules.documents.models import ApplicationDocument, StoredFile
from app.modules.identity.models import TenantMembership, User
from app.modules.institute.models import Campus

Uploader = aliased(TenantMembership, name="document_uploader")
UploaderUser = aliased(User, name="document_uploader_user")
Reviewer = aliased(TenantMembership, name="document_reviewer")
ReviewerUser = aliased(User, name="document_reviewer_user")


async def document(
    db: AsyncSession, tenant_id: uuid.UUID, document_id: uuid.UUID, *, lock: bool = False
) -> ApplicationDocument | None:
    statement = select(ApplicationDocument).where(
        ApplicationDocument.tenant_id == tenant_id, ApplicationDocument.id == document_id
    )
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    found: ApplicationDocument | None = await db.scalar(statement)
    return found


async def stored_file(
    db: AsyncSession, tenant_id: uuid.UUID, file_id: uuid.UUID
) -> StoredFile | None:
    found: StoredFile | None = await db.scalar(
        select(StoredFile).where(StoredFile.tenant_id == tenant_id, StoredFile.id == file_id)
    )
    return found


async def promote_uploaded(
    db: AsyncSession, tenant_id: uuid.UUID, application_id: uuid.UUID
) -> int:
    """On submission, the application's current ``UPLOADED`` documents enter review."""
    result = await db.execute(
        update(ApplicationDocument)
        .where(
            ApplicationDocument.tenant_id == tenant_id,
            ApplicationDocument.application_id == application_id,
            ApplicationDocument.replaced_at.is_(None),
            ApplicationDocument.status == DocumentStatus.UPLOADED.value,
        )
        .values(
            status=DocumentStatus.UNDER_REVIEW.value,
            version=ApplicationDocument.version + 1,
            updated_at=func.now(),
        )
        .execution_options(synchronize_session="fetch")
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class DocumentRow:
    id: uuid.UUID
    application_id: uuid.UUID
    document_type: str
    status: str
    rejection_reason: str | None
    file_name: str
    content_type: str
    size_bytes: int
    uploaded_by: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    replaces_document_id: uuid.UUID | None
    replaced_at: datetime | None
    created_at: datetime
    version: int


def _document_columns() -> tuple[Any, ...]:
    return (
        ApplicationDocument.id,
        ApplicationDocument.application_id,
        ApplicationDocument.document_type,
        ApplicationDocument.status,
        ApplicationDocument.rejection_reason,
        StoredFile.file_name,
        StoredFile.content_type,
        StoredFile.size_bytes,
        UploaderUser.display_name.label("uploaded_by"),
        ReviewerUser.display_name.label("reviewed_by"),
        ApplicationDocument.reviewed_at,
        ApplicationDocument.replaces_document_id,
        ApplicationDocument.replaced_at,
        ApplicationDocument.created_at,
        ApplicationDocument.version,
    )


def _with_names(statement: Select[Any]) -> Select[Any]:
    return (
        statement.join(
            StoredFile,
            and_(
                StoredFile.tenant_id == ApplicationDocument.tenant_id,
                StoredFile.id == ApplicationDocument.stored_file_id,
            ),
        )
        .outerjoin(
            Uploader,
            and_(
                Uploader.tenant_id == ApplicationDocument.tenant_id,
                Uploader.id == ApplicationDocument.uploaded_by_membership_id,
            ),
        )
        .outerjoin(UploaderUser, UploaderUser.id == Uploader.user_id)
        .outerjoin(
            Reviewer,
            and_(
                Reviewer.tenant_id == ApplicationDocument.tenant_id,
                Reviewer.id == ApplicationDocument.reviewed_by_membership_id,
            ),
        )
        .outerjoin(ReviewerUser, ReviewerUser.id == Reviewer.user_id)
    )


async def documents_of(
    db: AsyncSession, tenant_id: uuid.UUID, application_id: uuid.UUID
) -> list[DocumentRow]:
    """Every document of the application, replaced ones included (the history)."""
    statement = (
        _with_names(select(*_document_columns()))
        .where(
            ApplicationDocument.tenant_id == tenant_id,
            ApplicationDocument.application_id == application_id,
        )
        .order_by(
            ApplicationDocument.replaced_at.is_not(None),
            ApplicationDocument.document_type,
            ApplicationDocument.created_at.desc(),
        )
    )
    return [DocumentRow(**row._mapping) for row in await db.execute(statement)]


async def document_row(
    db: AsyncSession, tenant_id: uuid.UUID, document_id: uuid.UUID
) -> DocumentRow | None:
    statement = _with_names(select(*_document_columns())).where(
        ApplicationDocument.tenant_id == tenant_id, ApplicationDocument.id == document_id
    )
    row = (await db.execute(statement)).one_or_none()
    return DocumentRow(**row._mapping) if row is not None else None


@dataclass(frozen=True, slots=True)
class QueueRow:
    id: uuid.UUID
    application_id: uuid.UUID
    application_number: str
    applicant_name: str
    application_status: str
    course_code: str
    campus_code: str
    document_type: str
    status: str
    file_name: str
    content_type: str
    size_bytes: int
    uploaded_by: str | None
    created_at: datetime
    version: int


async def queue(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    context: RequestContext,
    *,
    statuses: Collection[DocumentStatus],
    types: Collection[DocumentType],
    campus: uuid.UUID | None,
    search: str | None,
    page: PageParams,
) -> tuple[list[QueueRow], int]:
    """Current documents in the caller's campuses (the ADM-09 verification queue), oldest first."""
    conditions: list[ColumnElement[bool]] = [
        ApplicationDocument.tenant_id == tenant_id,
        ApplicationDocument.replaced_at.is_(None),
        campus_visibility(Application.campus_id, context),
    ]
    if statuses:
        conditions.append(ApplicationDocument.status.in_(sorted(s.value for s in statuses)))
    if types:
        conditions.append(ApplicationDocument.document_type.in_(sorted(t.value for t in types)))
    if campus is not None:
        conditions.append(Application.campus_id == campus)
    if search:
        pattern = f"%{escape_like(search)}%"
        conditions.append(
            or_(
                Application.full_name.ilike(pattern, escape="\\"),
                Application.number.ilike(pattern, escape="\\"),
            )
        )
    joined = and_(
        Application.tenant_id == ApplicationDocument.tenant_id,
        Application.id == ApplicationDocument.application_id,
    )
    total = await db.scalar(
        select(func.count())
        .select_from(ApplicationDocument)
        .join(Application, joined)
        .where(*conditions)
    )
    statement = (
        select(
            ApplicationDocument.id,
            ApplicationDocument.application_id,
            Application.number.label("application_number"),
            Application.full_name.label("applicant_name"),
            Application.status.label("application_status"),
            Course.code.label("course_code"),
            Campus.code.label("campus_code"),
            ApplicationDocument.document_type,
            ApplicationDocument.status,
            StoredFile.file_name,
            StoredFile.content_type,
            StoredFile.size_bytes,
            UploaderUser.display_name.label("uploaded_by"),
            ApplicationDocument.created_at,
            ApplicationDocument.version,
        )
        .join(Application, joined)
        .join(
            Course,
            and_(Course.tenant_id == Application.tenant_id, Course.id == Application.course_id),
        )
        .join(
            Campus,
            and_(Campus.tenant_id == Application.tenant_id, Campus.id == Application.campus_id),
        )
        .join(
            StoredFile,
            and_(
                StoredFile.tenant_id == ApplicationDocument.tenant_id,
                StoredFile.id == ApplicationDocument.stored_file_id,
            ),
        )
        .outerjoin(
            Uploader,
            and_(
                Uploader.tenant_id == ApplicationDocument.tenant_id,
                Uploader.id == ApplicationDocument.uploaded_by_membership_id,
            ),
        )
        .outerjoin(UploaderUser, UploaderUser.id == Uploader.user_id)
        .where(*conditions)
        .order_by(ApplicationDocument.created_at.asc(), ApplicationDocument.id.asc())
        .limit(page.limit)
        .offset(page.offset)
    )
    rows = [QueueRow(**row._mapping) for row in await db.execute(statement)]
    return rows, int(total or 0)
