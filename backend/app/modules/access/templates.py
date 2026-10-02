"""System role templates (T01-05; D-B2).

Every tenant receives a clone of each template as a *system* role (when the
tenant is created, and for existing tenants in migration ``0005``). System
roles are immutable (D-B2): their permissions change only through a migration
that updates both this file and every tenant's clone (a test compares them).

* ``INSTITUTE_OWNER`` — every tenant permission.
* ``ADMIN`` — every tenant permission except ``role.delete``.

Templates are expanded here to explicit permission codes, never stored as
wildcards (D-B3).
"""

from dataclasses import dataclass
from enum import StrEnum

from app.modules.access.catalog import tenant_permissions
from app.modules.access.permissions import ROLE_DELETE


class SystemRole(StrEnum):
    INSTITUTE_OWNER = "INSTITUTE_OWNER"
    ADMIN = "ADMIN"


@dataclass(frozen=True, slots=True)
class RoleTemplate:
    code: SystemRole
    name: str
    description: str
    permissions: frozenset[str]


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
    )
