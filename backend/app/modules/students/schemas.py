"""Student API contracts (Phase 02-2; ADR-0021 §2, §6, §11). Read-only in the MVP."""

import uuid
from datetime import date, datetime
from typing import Any, Literal

from app.core.schemas import ResponseModel
from app.modules.courses.domain import CourseCategory
from app.modules.documents.domain import DocumentStatus, DocumentType
from app.modules.leads.schemas import CampusRef, PersonRef
from app.modules.students.domain import AdmissionStatus, StudentStatus


class StudentListItem(ResponseModel):
    id: uuid.UUID
    student_number: str
    full_name: str
    mobile: str | None
    email: str | None
    status: StudentStatus
    campus_id: uuid.UUID
    campus_code: str
    admissions: int
    latest_course: str | None
    created_at: datetime


class AdmissionOut(ResponseModel):
    id: uuid.UUID
    admission_number: str
    status: AdmissionStatus
    application_id: uuid.UUID
    application_number: str
    course_id: uuid.UUID
    course_code: str
    course_name: str
    course_category: CourseCategory
    campus: CampusRef
    approved_at: datetime
    approved_by: PersonRef | None


class StudentOut(ResponseModel):
    id: uuid.UUID
    student_number: str
    status: StudentStatus
    full_name: str
    date_of_birth: date | None
    mobile: str | None
    email: str | None
    city: str | None
    home_campus: CampusRef
    created_by: PersonRef | None
    admissions: list[AdmissionOut]
    created_at: datetime
    updated_at: datetime
    version: int


class StudentDocument(ResponseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    application_number: str
    document_type: DocumentType
    status: DocumentStatus
    file_name: str
    content_type: str
    size_bytes: int
    created_at: datetime


class StudentDocumentsOut(ResponseModel):
    items: list[StudentDocument]


class TimelineEntry(ResponseModel):
    id: uuid.UUID
    source: Literal["lead", "application"]
    kind: str
    actor: PersonRef | None
    details: dict[str, Any]
    body: str | None
    created_at: datetime
