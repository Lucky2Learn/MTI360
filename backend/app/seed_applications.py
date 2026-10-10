"""Development seed: applications, documents, admissions and students (Phase 02-2; ADR-0021).

Part of ``app.seed``: development only, realistic maritime fixtures,
fictitious people (``.example`` emails, the ``90000 10xxx`` mobile range).
Rows go through the same tables, keys and CHECKs as the API, with the
timelines the API would have written, and the leads they start from move to
``APPLICATION`` / ``ADMITTED`` as ``mark_application_started`` /
``mark_admitted`` do. Document files are generated placeholder PDFs (no
personal data) that pass the upload validation pipeline and are stored in
the configured object storage under generated tenant-prefixed keys.

Applications reference a lead by ``key`` (optional: a walk-in has none), a
course and campus by code and members by their seed email.
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Final, cast

from sqlalchemy import Table, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.activity import record_activity
from app.integrations.storage import ObjectStorage, StorageError
from app.modules.applications.domain import (
    REASON_REQUIRED,
    ActivityKind,
    ApplicationStatus,
    clean_indos,
    missing_for_submit,
)
from app.modules.applications.models import Application, ApplicationActivity
from app.modules.documents.domain import DocumentStatus, DocumentType
from app.modules.documents.models import ApplicationDocument, StoredFile, object_key
from app.modules.documents.validation import validate_upload
from app.modules.leads.domain import ActivityKind as LeadActivityKind
from app.modules.leads.domain import LeadStatus, clean_email, clean_mobile, mobile_key
from app.modules.leads.models import Lead, LeadActivity
from app.modules.students.domain import SequenceName
from app.modules.students.models import Admission, Student
from app.modules.students.sequences import next_number
from app.seed_admissions import (
    FICTITIOUS_MOBILE_PREFIX,
    AdmissionsSeedError,
    SeedLead,
    is_development_email,
)

APPLICATIONS = cast(Table, Application.__table__)
APPLICATION_ACTIVITIES = cast(Table, ApplicationActivity.__table__)
DOCUMENTS = cast(Table, ApplicationDocument.__table__)
FILES = cast(Table, StoredFile.__table__)
STUDENTS = cast(Table, Student.__table__)
ADMISSIONS = cast(Table, Admission.__table__)
LEADS = cast(Table, Lead.__table__)
LEAD_ACTIVITIES = cast(Table, LeadActivity.__table__)

SEEDABLE: Final = frozenset(
    {
        ApplicationStatus.DRAFT,
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.UNDER_REVIEW,
        ApplicationStatus.CORRECTION_REQUIRED,
        ApplicationStatus.APPROVED,
        ApplicationStatus.ADMITTED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.NOT_ELIGIBLE,
    }
)
DECIDED: Final = SEEDABLE - {
    ApplicationStatus.DRAFT,
    ApplicationStatus.SUBMITTED,
    ApplicationStatus.UNDER_REVIEW,
}
OPEN_LEADS: Final = frozenset({"NEW", "CONTACTED", "QUALIFIED", "COUNSELLING", "INTERESTED"})


@dataclass(frozen=True, slots=True)
class SeedDocument:
    document_type: DocumentType
    status: DocumentStatus
    reason: str | None


@dataclass(frozen=True, slots=True)
class SeedApplication:
    key: str
    lead: str | None
    course: str
    campus: str
    created_by: str
    reviewed_by: str | None
    status: ApplicationStatus
    status_reason: str | None
    full_name: str | None
    mobile: str | None
    email: str | None
    date_of_birth: date | None
    city: str | None
    highest_qualification: str | None
    indos_number: str | None
    declared: bool
    documents: tuple[SeedDocument, ...]


def _str(item: Mapping[str, Any], key: str) -> str | None:
    value = item.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AdmissionsSeedError(f"{key}: a non-empty string is required")
    return " ".join(value.split())


def _documents(
    raw: Sequence[Mapping[str, Any]], status: ApplicationStatus, at: str
) -> tuple[SeedDocument, ...]:
    documents: list[SeedDocument] = []
    for item in raw:
        try:
            document = SeedDocument(
                DocumentType(str(item.get("type"))),
                DocumentStatus(str(item.get("status", "UPLOADED"))),
                _str(item, "reason"),
            )
        except ValueError:
            raise AdmissionsSeedError(f"{at}.documents: unknown type or status") from None
        if (document.status is DocumentStatus.REJECTED) != (document.reason is not None):
            raise AdmissionsSeedError(f"{at}.documents: a reason for rejected documents only")
        uploaded_only = status is ApplicationStatus.DRAFT
        if uploaded_only != (document.status is DocumentStatus.UPLOADED):
            raise AdmissionsSeedError(f"{at}.documents: UPLOADED on drafts only")
        if status in {ApplicationStatus.APPROVED, ApplicationStatus.ADMITTED} and (
            document.status is not DocumentStatus.VERIFIED
        ):
            raise AdmissionsSeedError(f"{at}.documents: approved applications are verified")
        documents.append(document)
    return tuple(documents)


def parse_applications(
    raw: Sequence[Mapping[str, Any]],
    where: str,
    *,
    leads: Sequence[SeedLead],
    active_courses: set[str],
    campuses: set[str],
    members: set[str],
) -> tuple[SeedApplication, ...]:
    """Validate an institute's ``applications`` (the rules the API would apply)."""
    by_key = {lead.key: lead for lead in leads}
    seen: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    applications: list[SeedApplication] = []
    for index, item in enumerate(raw):
        at = f"{where}.applications[{index}]"
        try:
            key = _str(item, "key") or ""
            lead_key, course, campus = (
                _str(item, "lead"),
                _str(item, "course"),
                _str(item, "campus"),
            )
            created_by, reviewed_by = _str(item, "created_by"), _str(item, "reviewed_by")
            status = ApplicationStatus(item.get("status", "DRAFT"))
        except (AdmissionsSeedError, ValueError) as error:
            raise AdmissionsSeedError(f"{at}: {error}") from None
        if not key or key in seen:
            raise AdmissionsSeedError(f"{at}.key: a unique key is required")
        seen.add(key)
        if status not in SEEDABLE:
            raise AdmissionsSeedError(f"{at}.status: reserved status")
        if course not in active_courses or campus not in campuses:
            raise AdmissionsSeedError(f"{at}: an ACTIVE course and a known campus are required")
        if created_by not in members or (reviewed_by is not None and reviewed_by not in members):
            raise AdmissionsSeedError(f"{at}: created_by and reviewed_by must be seed members")
        if (status in DECIDED) != (reviewed_by is not None):
            raise AdmissionsSeedError(f"{at}.reviewed_by: required for decided applications only")
        reason = _str(item, "status_reason")
        if (status in REASON_REQUIRED) != (reason is not None):
            raise AdmissionsSeedError(f"{at}.status_reason: required for this status only")
        lead = by_key.get(lead_key) if lead_key else None
        if lead_key is not None and (lead is None or lead.status.value not in OPEN_LEADS):
            raise AdmissionsSeedError(f"{at}.lead: an open seed lead")
        if lead_key is not None:
            if (lead_key, course) in pairs:
                raise AdmissionsSeedError(f"{at}: one application per lead and course")
            pairs.add((lead_key, course))
        try:
            mobile = clean_mobile(item.get("mobile")) or (lead.mobile if lead else None)
            email_raw = item.get("email") or (lead.email if lead else None)
            email = clean_email(email_raw)
            indos = clean_indos(item.get("indos_number"))
        except ValueError:
            raise AdmissionsSeedError(f"{at}: invalid mobile, email or INDoS number") from None
        if mobile and not (mobile_key(mobile) or "").startswith(FICTITIOUS_MOBILE_PREFIX):
            raise AdmissionsSeedError(f"{at}.mobile: use the fictitious 90000 10xxx range")
        if email and not is_development_email(email[1]):
            raise AdmissionsSeedError(f"{at}.email: development emails must use example.com")
        birth = item.get("date_of_birth")
        full_name = _str(item, "full_name") or (lead.full_name if lead else None)
        birth_date = date.fromisoformat(birth) if birth else (lead.date_of_birth if lead else None)
        qualification = _str(item, "highest_qualification") or (
            lead.qualification if lead else None
        )
        entered = email[0] if email else None
        values: dict[str, object] = {
            "full_name": full_name,
            "date_of_birth": birth_date,
            "highest_qualification": qualification,
            "mobile": mobile,
            "email": entered,
        }
        declared = bool(item.get("declared", False))
        if not full_name or (not mobile and not email):
            raise AdmissionsSeedError(f"{at}: a name and a contact are required")
        if status is not ApplicationStatus.DRAFT and missing_for_submit(values, declared=declared):
            raise AdmissionsSeedError(f"{at}: a submitted application must be complete")
        applications.append(
            SeedApplication(
                key=key,
                lead=lead_key,
                course=course or "",
                campus=campus or "",
                created_by=created_by or "",
                reviewed_by=reviewed_by,
                status=status,
                status_reason=reason,
                full_name=full_name,
                mobile=mobile,
                email=entered,
                date_of_birth=birth_date,
                city=_str(item, "city") or (lead.city if lead else None),
                highest_qualification=qualification,
                indos_number=indos,
                declared=declared,
                documents=_documents(item.get("documents", ()), status, at),
            )
        )
    return tuple(applications)


def placeholder_pdf(document_type: DocumentType) -> bytes:
    """A tiny, valid PDF without personal data (development only)."""
    text = f"MTI 360 development seed - {document_type.value} - placeholder".encode()
    return (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>\nendobj\n"
        b"% " + text + b"\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
    )


async def _activity(
    db: AsyncSession,
    application_id: uuid.UUID,
    kind: ActivityKind,
    actor: uuid.UUID,
    **details: object,
) -> None:
    await record_activity(
        db,
        APPLICATION_ACTIVITIES,
        subject_column="application_id",
        subject_id=application_id,
        kind=kind.value,
        actor_membership_id=actor,
        details=details,
    )


async def _lead_activity(
    db: AsyncSession,
    lead_id: uuid.UUID,
    kind: LeadActivityKind,
    actor: uuid.UUID,
    **details: object,
) -> None:
    await record_activity(
        db,
        LEAD_ACTIVITIES,
        subject_column="lead_id",
        subject_id=lead_id,
        kind=kind.value,
        actor_membership_id=actor,
        details=details,
    )


async def _store_document(
    db: AsyncSession,
    storage: ObjectStorage,
    tenant_id: uuid.UUID,
    application_id: uuid.UUID,
    document: SeedDocument,
    *,
    uploader: uuid.UUID,
    reviewer: uuid.UUID | None,
) -> uuid.UUID:
    data = placeholder_pdf(document.document_type)
    checked = validate_upload(
        f"{document.document_type.value.lower()}.pdf", "application/pdf", data
    )
    file_id = uuid.uuid7()
    key = object_key(tenant_id, file_id)
    try:
        await storage.put(key, data, content_type=checked.content_type)
    except StorageError:
        raise AdmissionsSeedError(
            "object storage is unavailable: start it (pnpm infra:up) before seeding"
        ) from None
    await db.execute(
        insert(FILES).values(
            id=file_id,
            tenant_id=tenant_id,
            object_key=key,
            file_name=checked.file_name,
            content_type=checked.content_type,
            size_bytes=checked.size,
            sha256=checked.sha256,
            uploaded_by_membership_id=uploader,
        )
    )
    decided = document.status in {DocumentStatus.VERIFIED, DocumentStatus.REJECTED}
    document_id = uuid.uuid7()
    await db.execute(
        insert(DOCUMENTS).values(
            id=document_id,
            tenant_id=tenant_id,
            application_id=application_id,
            stored_file_id=file_id,
            document_type=document.document_type.value,
            status=document.status.value,
            rejection_reason=document.reason,
            reviewed_at=func.now() if decided else None,
            reviewed_by_membership_id=reviewer if decided else None,
            uploaded_by_membership_id=uploader,
            version=1,
        )
    )
    return document_id


async def seed_applications(
    db: AsyncSession,
    storage: ObjectStorage,
    tenant_id: uuid.UUID,
    *,
    applications: Sequence[SeedApplication],
    lead_ids: Mapping[str, uuid.UUID],
    course_ids: Mapping[str, uuid.UUID],
    campus_ids: Mapping[str, uuid.UUID],
    memberships: Mapping[str, uuid.UUID],
) -> None:
    """Insert one institute's applications, documents, admissions and students."""
    for item in applications:
        creator = memberships[item.created_by]
        reviewer = memberships[item.reviewed_by] if item.reviewed_by else None
        lead_id = lead_ids[item.lead] if item.lead else None
        owner = creator
        if lead_id is not None:
            lead_owner = await db.scalar(
                select(LEADS.c.owner_membership_id).where(LEADS.c.id == lead_id)
            )
            owner = lead_owner or creator
        email = clean_email(item.email)
        application_id = uuid.uuid7()
        number = await next_number(db, SequenceName.APPLICATION)
        submitted = item.status is not ApplicationStatus.DRAFT
        await db.execute(
            insert(APPLICATIONS).values(
                id=application_id,
                tenant_id=tenant_id,
                number=number,
                lead_id=lead_id,
                course_id=course_ids[item.course],
                campus_id=campus_ids[item.campus],
                owner_membership_id=owner,
                created_by_membership_id=creator,
                status=item.status.value,
                status_reason=item.status_reason,
                submitted_at=func.now() if submitted else None,
                reviewed_at=func.now() if reviewer else None,
                reviewed_by_membership_id=reviewer,
                declared_at=func.now() if item.declared else None,
                declared_by_membership_id=creator if item.declared else None,
                full_name=item.full_name,
                date_of_birth=item.date_of_birth,
                mobile=item.mobile,
                mobile_key=mobile_key(item.mobile),
                email=item.email,
                email_normalized=email[1] if email else None,
                city=item.city,
                highest_qualification=item.highest_qualification,
                indos_number=item.indos_number,
                version=1,
            )
        )
        await _activity(
            db,
            application_id,
            ActivityKind.CREATED,
            creator,
            from_lead=lead_id is not None,
            course_id=course_ids[item.course],
            campus_id=campus_ids[item.campus],
        )
        for document in item.documents:
            document_id = await _store_document(
                db,
                storage,
                tenant_id,
                application_id,
                document,
                uploader=creator,
                reviewer=reviewer,
            )
            await _activity(
                db,
                application_id,
                ActivityKind.DOCUMENT_UPLOADED,
                creator,
                document_id=document_id,
                document_type=document.document_type.value,
                replaced=False,
            )
            if document.status is DocumentStatus.VERIFIED and reviewer:
                await _activity(
                    db,
                    application_id,
                    ActivityKind.DOCUMENT_VERIFIED,
                    reviewer,
                    document_id=document_id,
                    document_type=document.document_type.value,
                )
            elif document.status is DocumentStatus.REJECTED and reviewer:
                await _activity(
                    db,
                    application_id,
                    ActivityKind.DOCUMENT_REJECTED,
                    reviewer,
                    document_id=document_id,
                    document_type=document.document_type.value,
                    reason=document.reason,
                )
        if submitted:
            await _activity(
                db,
                application_id,
                ActivityKind.SUBMITTED,
                creator,
                documents_for_review=len(item.documents),
            )
            final = (
                ApplicationStatus.APPROVED
                if item.status is ApplicationStatus.ADMITTED
                else item.status
            )
            if item.status in DECIDED and reviewer is not None:
                details: dict[str, object] = {"from": "SUBMITTED", "to": final.value}
                if item.status_reason:
                    details["reason"] = item.status_reason
                await _activity(
                    db, application_id, ActivityKind.STATUS_CHANGED, reviewer, **details
                )
        if lead_id is not None:
            await _lead_activity(
                db,
                lead_id,
                LeadActivityKind.APPLICATION_STARTED,
                creator,
                application_id=application_id,
                application_number=number,
            )
            previous = await db.scalar(select(LEADS.c.status).where(LEADS.c.id == lead_id))
            target = (
                LeadStatus.ADMITTED
                if item.status is ApplicationStatus.ADMITTED
                else LeadStatus.APPLICATION
            )
            for source, to in ((previous, LeadStatus.APPLICATION), ("APPLICATION", target)):
                if source in OPEN_LEADS | {"APPLICATION"} and source != to.value:
                    await db.execute(
                        update(LEADS)
                        .where(LEADS.c.id == lead_id)
                        .values(
                            status=to.value,
                            status_reason=None,
                            status_changed_at=func.now(),
                            version=LEADS.c.version + 1,
                        )
                    )
                    await _lead_activity(
                        db,
                        lead_id,
                        LeadActivityKind.STATUS_CHANGED,
                        creator,
                        **{"from": source, "to": to.value},
                    )
                    previous = to.value
        if item.status is ApplicationStatus.ADMITTED and reviewer is not None:
            student_id = uuid.uuid7()
            student_number = await next_number(db, SequenceName.STUDENT)
            await db.execute(
                insert(STUDENTS).values(
                    id=student_id,
                    tenant_id=tenant_id,
                    student_number=student_number,
                    home_campus_id=campus_ids[item.campus],
                    full_name=item.full_name,
                    date_of_birth=item.date_of_birth,
                    mobile=item.mobile,
                    mobile_key=mobile_key(item.mobile),
                    email=item.email,
                    email_normalized=email[1] if email else None,
                    city=item.city,
                    created_by_membership_id=reviewer,
                    version=1,
                )
            )
            admission_number = await next_number(db, SequenceName.ADMISSION)
            await db.execute(
                insert(ADMISSIONS).values(
                    id=uuid.uuid7(),
                    tenant_id=tenant_id,
                    admission_number=admission_number,
                    application_id=application_id,
                    student_id=student_id,
                    course_id=course_ids[item.course],
                    campus_id=campus_ids[item.campus],
                    approved_by_membership_id=reviewer,
                    version=1,
                )
            )
            await _activity(
                db,
                application_id,
                ActivityKind.ADMITTED,
                reviewer,
                admission_number=admission_number,
                student_number=student_number,
                student_created=True,
            )
