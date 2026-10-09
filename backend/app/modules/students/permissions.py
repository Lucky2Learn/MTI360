"""Admission and student permissions (Phase 02-2; ADR-0021 §11). Tenant realm, campus-scoped.

``admission.approve`` is explicitly permission-gated (UI-SCREENS ADM-10) and
needs no step-up (L7). A student is visible to members of its home campus.
"""

from app.core.authz import PermissionScope, permission
from app.core.context import Realm

_M = "students"
_C = PermissionScope.CAMPUS

ADMISSION_APPROVE = permission(
    "admission.approve",
    Realm.TENANT,
    _C,
    "Approve admissions and create student records",
    module=_M,
)
STUDENT_READ = permission("student.read", Realm.TENANT, _C, "View students", module=_M)
