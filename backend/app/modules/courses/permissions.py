"""Course catalogue permissions (Phase 02-1; ADR-0020 §2, §10). Tenant realm.

Courses have no campus. ``course.read`` is campus-scoped, so campus-restricted
staff read the whole institute catalogue (``authorize()`` admits a campus
permission on a resource without a campus); ``course.manage`` is tenant-wide,
so only all-campus members change it.
"""

from app.core.authz import PermissionScope, permission
from app.core.context import Realm

_M = "courses"

COURSE_READ = permission(
    "course.read", Realm.TENANT, PermissionScope.CAMPUS, "View the course catalogue", module=_M
)
COURSE_MANAGE = permission(
    "course.manage",
    Realm.TENANT,
    PermissionScope.TENANT,
    "Create, edit, activate and archive courses",
    module=_M,
)
