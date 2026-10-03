"""Tenant roles and effective permissions (T01-05; ADR-0011, ADR-0016).

* :func:`membership_access` — the effective permissions of a membership: the
  **union** of its roles' permissions, restricted to permissions declared in
  code (unknown codes are dropped: fail closed) and, for a campus-restricted
  member, to campus-scoped permissions (D-B1). Plus the role names for the
  session.
* :func:`clone_system_roles` — gives a tenant its system roles from the code
  templates (system realm only; the database refuses otherwise).
* Custom roles and role assignment — the service foundation for tenant
  administration (its API arrives in T01-08). Each operation authorizes the
  caller, applies the **no-escalation** rule (a caller grants, or takes away,
  only permissions it holds; ADR-0011 §5), refuses system roles (D-B2) and
  writes an audit event in the same transaction.

All operations use the trusted request context: the tenant is never a
parameter, and another tenant's role or membership is not found.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditTarget, record_security_event, write_audit_event
from app.core.authz import REGISTRY, Permission, PermissionScope, authorize
from app.core.context import Realm, RequestContext, current_context
from app.core.errors import (
    ConflictError,
    ErrorDetail,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from app.modules.access import events
from app.modules.access import repository as repo
from app.modules.access.catalog import tenant_permissions
from app.modules.access.models import ROLE_DESCRIPTION_MAX_LENGTH, ROLE_NAME_MAX_LENGTH
from app.modules.access.permissions import (
    ROLE_ASSIGN,
    ROLE_CREATE,
    ROLE_DELETE,
    ROLE_READ,
    ROLE_UPDATE,
)
from app.modules.access.templates import OWNER_TEMPLATE, system_role_templates


@dataclass(frozen=True, slots=True)
class RoleSummary:
    """A role as the session shows it (UI contract: name and ``is_system`` only)."""

    name: str
    is_system: bool


@dataclass(frozen=True, slots=True)
class MembershipAccess:
    permissions: frozenset[str]
    roles: tuple[RoleSummary, ...]

    @property
    def sorted_permissions(self) -> tuple[str, ...]:
        return tuple(sorted(self.permissions))


NO_ACCESS = MembershipAccess(frozenset(), ())


def effective_permissions(codes: Iterable[str], *, all_campuses: bool) -> frozenset[str]:
    """Registered tenant permissions among ``codes``; tenant-wide ones only with all campuses."""
    result: set[str] = set()
    for code in codes:
        permission = REGISTRY.get(Realm.TENANT, code)
        if permission is None:
            continue
        if permission.scope is PermissionScope.TENANT and not all_campuses:
            continue
        result.add(code)
    return frozenset(result)


async def membership_access(
    db: AsyncSession, *, tenant_id: uuid.UUID, membership_id: uuid.UUID, all_campuses: bool
) -> MembershipAccess:
    """Effective permissions (union of roles, D-B1 filtered) and roles of a membership."""
    rows = await repo.assigned_roles(db, tenant_id, membership_id)
    roles = {RoleSummary(row.name, row.is_system) for row in rows}
    codes = {row.permission_code for row in rows if row.permission_code is not None}
    return MembershipAccess(
        effective_permissions(codes, all_campuses=all_campuses),
        tuple(sorted(roles, key=lambda r: (not r.is_system, r.name.lower(), r.name))),
    )


async def clone_system_roles(db: AsyncSession, tenant_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """Create the tenant's system roles from the templates (system realm; T01-07 provisioning)."""
    created: dict[str, uuid.UUID] = {}
    for template in system_role_templates():
        role_id = await repo.insert_role(
            db,
            tenant_id,
            name=template.name,
            description=template.description,
            template_code=template.code.value,
        )
        await repo.add_role_permissions(db, tenant_id, role_id, template.permissions)
        created[template.code.value] = role_id
    return created


# --- custom roles and assignments (service foundation; API in T01-08) ---------------------


async def list_roles(db: AsyncSession) -> list[repo.RoleDetail]:
    """The institute's roles with their permissions and member counts (T01-08)."""
    context = current_context()
    authorize(context, ROLE_READ)
    return await repo.roles_of_tenant(db, _tenant(context))


async def get_role(db: AsyncSession, role_id: uuid.UUID) -> repo.RoleDetail:
    context = current_context()
    authorize(context, ROLE_READ)
    found = await repo.roles_of_tenant(db, _tenant(context), role_id=role_id)
    if not found:
        raise NotFoundError()
    return found[0]


def permission_catalogue() -> list[Permission]:
    """The tenant permissions a custom role may hold (``role.read``; T01-08)."""
    authorize(current_context(), ROLE_READ)
    return sorted(tenant_permissions(), key=lambda permission: permission.code)


def _tenant(context: RequestContext) -> uuid.UUID:
    if context.tenant_id is None:  # authorize() already refused; keeps types honest
        raise PermissionDeniedError()
    return context.tenant_id


def _invalid(field: str, code: str, message: str) -> ValidationFailedError:
    return ValidationFailedError(details=[ErrorDetail(field=field, code=code, message=message)])


def _clean_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned or len(cleaned) > ROLE_NAME_MAX_LENGTH:
        raise _invalid("name", "invalid", "Enter a role name of up to 100 characters.")
    return cleaned


def _clean_description(description: str | None) -> str | None:
    if description is None:
        return None
    cleaned = description.strip()
    if len(cleaned) > ROLE_DESCRIPTION_MAX_LENGTH:
        raise _invalid("description", "too_long", "Use at most 500 characters.")
    return cleaned or None


def _tenant_codes(permissions: Iterable[str]) -> frozenset[str]:
    codes = frozenset(permissions)
    if any(REGISTRY.get(Realm.TENANT, code) is None for code in codes):
        raise _invalid("permissions", "unknown", "Choose permissions from the list.")
    return codes


def _no_escalation(context: RequestContext, codes: Iterable[str]) -> None:
    """ADR-0011 §5: a caller grants or takes away only permissions it holds."""
    if not frozenset(codes) <= context.permissions:
        raise PermissionDeniedError()


def _reject_system_role(role: repo.RoleRow, action: str) -> None:
    if role.is_system:
        record_security_event(
            events.SYSTEM_ROLE_CHANGE_REJECTED,
            target=AuditTarget("role", role.id),
            metadata={"action": action},
        )
        raise PermissionDeniedError()


async def _role(db: AsyncSession, context: RequestContext, role_id: uuid.UUID) -> repo.RoleRow:
    role = await repo.role(db, _tenant(context), role_id)
    if role is None:
        raise NotFoundError()
    return role


async def create_role(
    db: AsyncSession, *, name: str, description: str | None, permissions: Iterable[str]
) -> uuid.UUID:
    context = current_context()
    authorize(context, ROLE_CREATE)
    tenant_id = _tenant(context)
    clean_name, clean_description = _clean_name(name), _clean_description(description)
    codes = _tenant_codes(permissions)
    _no_escalation(context, codes)
    if await repo.role_name_taken(db, tenant_id, clean_name):
        raise ConflictError("A role with this name already exists.")
    role_id = await repo.insert_role(db, tenant_id, name=clean_name, description=clean_description)
    await repo.add_role_permissions(db, tenant_id, role_id, codes)
    await write_audit_event(
        db,
        events.ROLE_CREATED,
        target=AuditTarget("role", role_id),
        metadata={"name": clean_name, "permission_count": len(codes)},
    )
    return role_id


async def update_role(
    db: AsyncSession,
    role_id: uuid.UUID,
    *,
    expected_version: int,
    name: str | None = None,
    description: str | None = None,
    permissions: Iterable[str] | None = None,
) -> None:
    """Rename, re-describe or change the permissions of a custom role (optimistic)."""
    context = current_context()
    authorize(context, ROLE_UPDATE)
    tenant_id = _tenant(context)
    role = await _role(db, context, role_id)
    authorize(context, ROLE_UPDATE, role)
    _reject_system_role(role, "update")
    new_name = role.name if name is None else _clean_name(name)
    new_description = role.description if description is None else _clean_description(description)
    current = await repo.role_permission_codes(db, tenant_id, role_id)
    target = current if permissions is None else _tenant_codes(permissions)
    added, removed = target - current, current - target
    _no_escalation(context, added | removed)
    if new_name != role.name and await repo.role_name_taken(
        db, tenant_id, new_name, excluding=role_id
    ):
        raise ConflictError("A role with this name already exists.")
    if not await repo.update_role(
        db,
        tenant_id,
        role_id,
        expected_version=expected_version,
        name=new_name,
        description=new_description,
    ):
        raise ConflictError()
    await repo.remove_role_permissions(db, tenant_id, role_id, removed)
    await repo.add_role_permissions(db, tenant_id, role_id, added)
    target_ref = AuditTarget("role", role_id)
    if new_name != role.name or new_description != role.description:
        await write_audit_event(
            db,
            events.ROLE_UPDATED,
            target=target_ref,
            metadata={
                "name": new_name,
                "previous_name": role.name,
                "description_changed": new_description != role.description,
            },
        )
    if added or removed:
        await write_audit_event(
            db,
            events.ROLE_PERMISSIONS_CHANGED,
            target=target_ref,
            metadata={
                "added": sorted(added)[:16],
                "removed": sorted(removed)[:16],
                "added_count": len(added),
                "removed_count": len(removed),
            },
        )


async def delete_role(db: AsyncSession, role_id: uuid.UUID, *, expected_version: int) -> None:
    """Delete an unassigned custom role (409 while members hold it)."""
    context = current_context()
    authorize(context, ROLE_DELETE)
    tenant_id = _tenant(context)
    role = await _role(db, context, role_id)
    authorize(context, ROLE_DELETE, role)
    _reject_system_role(role, "delete")
    _no_escalation(context, await repo.role_permission_codes(db, tenant_id, role_id))
    if await repo.role_assigned(db, tenant_id, role_id):
        raise ConflictError("Remove this role from its members before deleting it.")
    if not await repo.delete_role(db, tenant_id, role_id, expected_version=expected_version):
        raise ConflictError()
    await write_audit_event(
        db, events.ROLE_DELETED, target=AuditTarget("role", role_id), metadata={"name": role.name}
    )


async def _assignment(
    db: AsyncSession, context: RequestContext, membership_id: uuid.UUID, role_id: uuid.UUID
) -> tuple[repo.MembershipRow, repo.RoleRow]:
    authorize(context, ROLE_ASSIGN)
    tenant_id = _tenant(context)
    membership = await repo.membership(db, tenant_id, membership_id)
    if membership is None:
        raise NotFoundError()
    authorize(context, ROLE_ASSIGN, membership)
    role = await _role(db, context, role_id)
    authorize(context, ROLE_ASSIGN, role)
    _no_escalation(context, await repo.role_permission_codes(db, tenant_id, role_id))
    return membership, role


async def assign_role(db: AsyncSession, membership_id: uuid.UUID, role_id: uuid.UUID) -> None:
    """Give a member a role (409 if it already has it)."""
    context = current_context()
    membership, role = await _assignment(db, context, membership_id, role_id)
    if await repo.membership_has_role(db, membership.tenant_id, membership.id, role.id):
        raise ConflictError("The member already has this role.")
    await repo.assign(db, membership.tenant_id, membership.id, role.id)
    await write_audit_event(
        db,
        events.ROLE_ASSIGNED,
        target=AuditTarget("tenant_membership", membership.id),
        metadata={"role_id": role.id, "role_name": role.name, "is_system": role.is_system},
    )


# --- self-protection and owner protection (T01-08, D8-4) --------------------------------------


def refuse_self(
    context: RequestContext, member_user_id: uuid.UUID | None, membership_id: uuid.UUID, action: str
) -> None:
    """403 for a member administration action on the caller's own membership (D8-4)."""
    if member_user_id is not None and member_user_id == context.principal_id:
        record_security_event(
            events.SELF_ACTION_REFUSED,
            target=AuditTarget("tenant_membership", membership_id),
            metadata={"action": action},
        )
        raise PermissionDeniedError()


async def keep_an_owner(db: AsyncSession, membership_id: uuid.UUID) -> None:
    """409 if ``membership_id`` is the institute's last ACTIVE owner (D8-4).

    Call it before a change that ends the membership's ownership (suspension,
    revocation, removal of the owner role), in the same transaction. A
    per-tenant advisory lock serialises the check, so two concurrent changes
    cannot both remove an owner.
    """
    tenant_id = _tenant(current_context())
    owner = OWNER_TEMPLATE.value
    if not await repo.is_active_owner(db, tenant_id, membership_id, owner):
        return
    await repo.lock_owners(db, tenant_id)
    if await repo.active_owner_count(db, tenant_id, owner, excluding=membership_id) == 0:
        raise ConflictError("The institute must keep at least one active owner.")


async def remove_role(db: AsyncSession, membership_id: uuid.UUID, role_id: uuid.UUID) -> None:
    """Take a role away from a member (404 if the member does not have it).

    Never from one's own membership (403), never the last active owner's owner role (409).
    """
    context = current_context()
    membership, role = await _assignment(db, context, membership_id, role_id)
    refuse_self(context, membership.user_id, membership.id, "remove_role")
    if role.is_system and role.template_code == OWNER_TEMPLATE.value:
        await keep_an_owner(db, membership.id)
    if not await repo.unassign(db, membership.tenant_id, membership.id, role.id):
        raise NotFoundError()
    await write_audit_event(
        db,
        events.ROLE_REMOVED,
        target=AuditTarget("tenant_membership", membership.id),
        metadata={"role_id": role.id, "role_name": role.name, "is_system": role.is_system},
    )
