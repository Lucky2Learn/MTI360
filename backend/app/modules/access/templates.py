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

Migration ``0009`` added the last two to every existing tenant; migration
``0010`` extended them (and the Owner/Admin clones) with the 02-2 permissions.

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
from app.modules.leads.permissions import LEAD_ASSIGN, LEAD_CREATE, LEAD_READ, LEAD_UPDATE
from app.modules.students.permissions import ADMISSION_APPROVE, STUDENT_READ


class SystemRole(StrEnum):
    INSTITUTE_OWNER = "INSTITUTE_OWNER"
    ADMIN = "ADMIN"
    ADMISSIONS_MANAGER = "ADMISSIONS_MANAGER"
    COUNSELLOR = "COUNSELLOR"


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
            ),
        ),
    )
