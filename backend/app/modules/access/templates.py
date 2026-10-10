"""System role templates (T01-05; D-B2).

Every tenant receives a clone of each template as a *system* role (when the
tenant is created, and for existing tenants in migration ``0005``). System
roles are immutable (D-B2): their permissions change only through a migration
that updates both this file and every tenant's clone (a test compares them).

* ``INSTITUTE_OWNER`` — every tenant permission.
* ``ADMIN`` — every tenant permission except ``role.delete``.
* ``ADMISSIONS_MANAGER`` (Phase 02-1, L7) — the course catalogue and every lead
  permission, assignment included. ``course.manage`` is tenant-wide, so it is
  effective only with all-campus access (D-B1). Phase 02-2 adds every
  application, document, admission and student permission (ADR-0021 §11).
* ``COUNSELLOR`` (Phase 02-1, L7) — reads the catalogue; reads, adds and works
  leads; does not assign leads or manage courses. Phase 02-2 adds starting,
  editing and submitting applications, reading and uploading documents and
  reading students; not reviewing, verifying or admitting.

* ``FINANCE_MANAGER`` (Phase 02-5, ADR-0022) — every finance permission:
  fee structures, fee invoices and their cancellation, payments and
  reversals; reads courses and students.
* ``FINANCE_OFFICER`` (Phase 02-5) — reads fee structures, issues fee
  invoices and records payments (confirming or failing cheques and demand
  drafts); does not manage structures, cancel invoices or reverse payments.

Migration ``0009`` added the admissions templates to every existing tenant;
migration ``0010`` extended them (and the Owner/Admin clones) with the 02-2
permissions. Migration ``0011`` added the finance templates, gave the
Owner/Admin clones every finance permission, the Admissions manager
``fee_structure.read`` and ``invoice.read``, and the Counsellor
``fee_structure.read``.

Templates are expanded here to explicit permission codes, never stored as
wildcards (D-B3).
"""

from dataclasses import dataclass
from enum import StrEnum

from app.core.authz import Permission
from app.modules.access.catalog import tenant_permissions
from app.modules.access.permissions import ROLE_DELETE
from app.modules.applications.permissions import (
    APPLICATION_CREATE,
    APPLICATION_READ,
    APPLICATION_REVIEW,
    APPLICATION_UPDATE,
)
from app.modules.courses.permissions import COURSE_MANAGE, COURSE_READ
from app.modules.documents.permissions import DOCUMENT_READ, DOCUMENT_UPLOAD, DOCUMENT_VERIFY
from app.modules.finance.permissions import (
    FEE_STRUCTURE_MANAGE,
    FEE_STRUCTURE_READ,
    INVOICE_CANCEL,
    INVOICE_ISSUE,
    INVOICE_READ,
    PAYMENT_RECORD,
    PAYMENT_REVERSE,
)
from app.modules.leads.permissions import LEAD_ASSIGN, LEAD_CREATE, LEAD_READ, LEAD_UPDATE
from app.modules.students.permissions import ADMISSION_APPROVE, STUDENT_READ


class SystemRole(StrEnum):
    INSTITUTE_OWNER = "INSTITUTE_OWNER"
    ADMIN = "ADMIN"
    ADMISSIONS_MANAGER = "ADMISSIONS_MANAGER"
    COUNSELLOR = "COUNSELLOR"
    FINANCE_MANAGER = "FINANCE_MANAGER"
    FINANCE_OFFICER = "FINANCE_OFFICER"


@dataclass(frozen=True, slots=True)
class RoleTemplate:
    code: SystemRole
    name: str
    description: str
    permissions: frozenset[str]


OWNER_TEMPLATE = SystemRole.INSTITUTE_OWNER
ADMISSIONS_MANAGER_DESCRIPTION = (
    "Runs admissions: the course catalogue, leads and their assignment, applications, "
    "document verification, review and admission approval."
)
COUNSELLOR_DESCRIPTION = (
    "Works enquiries and applications: leads, notes and follow-ups, application drafts "
    "and document uploads; reads the catalogue and students."
)
"""The system role given to the primary administrator at provisioning (T01-07, D7-1)."""
FINANCE_MANAGER_DESCRIPTION = (
    "Runs student fees: fee structures, fee invoices and their cancellation, payments, "
    "receipts and reversals; reads courses and students."
)
FINANCE_OFFICER_DESCRIPTION = (
    "Collects student fees: issues fee invoices, records payments and confirms or fails "
    "cheques and demand drafts; reads fee structures, courses and students."
)


def _codes(*permissions: Permission) -> frozenset[str]:
    return frozenset(permission.code for permission in permissions)


def system_role_templates() -> tuple[RoleTemplate, ...]:
    everything = frozenset(p.code for p in tenant_permissions())
    return (
        RoleTemplate(
            SystemRole.INSTITUTE_OWNER,
            "Institute owner",
            "Full access to the institute, including deleting roles.",
            everything,
        ),
        RoleTemplate(
            SystemRole.ADMIN,
            "Administrator",
            "Full access to the institute except deleting roles.",
            everything - {ROLE_DELETE.code},
        ),
        RoleTemplate(
            SystemRole.ADMISSIONS_MANAGER,
            "Admissions manager",
            ADMISSIONS_MANAGER_DESCRIPTION,
            _codes(
                COURSE_READ,
                COURSE_MANAGE,
                LEAD_READ,
                LEAD_CREATE,
                LEAD_UPDATE,
                LEAD_ASSIGN,
                APPLICATION_READ,
                APPLICATION_CREATE,
                APPLICATION_UPDATE,
                APPLICATION_REVIEW,
                DOCUMENT_READ,
                DOCUMENT_UPLOAD,
                DOCUMENT_VERIFY,
                ADMISSION_APPROVE,
                STUDENT_READ,
                FEE_STRUCTURE_READ,
                INVOICE_READ,
            ),
        ),
        RoleTemplate(
            SystemRole.COUNSELLOR,
            "Counsellor",
            COUNSELLOR_DESCRIPTION,
            _codes(
                COURSE_READ,
                LEAD_READ,
                LEAD_CREATE,
                LEAD_UPDATE,
                APPLICATION_READ,
                APPLICATION_CREATE,
                APPLICATION_UPDATE,
                DOCUMENT_READ,
                DOCUMENT_UPLOAD,
                STUDENT_READ,
                FEE_STRUCTURE_READ,
            ),
        ),
        RoleTemplate(
            SystemRole.FINANCE_MANAGER,
            "Finance manager",
            FINANCE_MANAGER_DESCRIPTION,
            _codes(
                FEE_STRUCTURE_READ,
                FEE_STRUCTURE_MANAGE,
                INVOICE_READ,
                INVOICE_ISSUE,
                INVOICE_CANCEL,
                PAYMENT_RECORD,
                PAYMENT_REVERSE,
                COURSE_READ,
                STUDENT_READ,
            ),
        ),
        RoleTemplate(
            SystemRole.FINANCE_OFFICER,
            "Finance officer",
            FINANCE_OFFICER_DESCRIPTION,
            _codes(
                FEE_STRUCTURE_READ,
                INVOICE_READ,
                INVOICE_ISSUE,
                PAYMENT_RECORD,
                COURSE_READ,
                STUDENT_READ,
            ),
        ),
    )
