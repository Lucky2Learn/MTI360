"""Permission registry, catalogue and role templates (T01-05; D-B2, D-B3, ADR-0011)."""

import importlib
import pkgutil

import pytest

import app.modules
from app.core.authz import (
    REGISTRY,
    DuplicatePermissionError,
    Permission,
    PermissionRegistry,
    PermissionScope,
)
from app.core.authz.registry import CODE_MAX_LENGTH
from app.core.context import Realm
from app.modules.access import models as access_models
from app.modules.access.catalog import PERMISSION_MODULES, all_permissions, tenant_permissions
from app.modules.access.service import effective_permissions
from app.modules.access.templates import SystemRole, system_role_templates
from app.modules.platform_identity.roles import (
    PLATFORM_ROLE_PERMISSIONS,
    PlatformRole,
    platform_permissions,
)

TENANT_BASELINE = {
    "campus.read": PermissionScope.CAMPUS,
    "campus.create": PermissionScope.TENANT,
    "campus.update": PermissionScope.CAMPUS,
    "member.read": PermissionScope.TENANT,
    "member.invite": PermissionScope.TENANT,
    "member.update": PermissionScope.TENANT,
    "member.suspend": PermissionScope.TENANT,
    "member.revoke": PermissionScope.TENANT,
    "role.read": PermissionScope.TENANT,
    "role.create": PermissionScope.TENANT,
    "role.update": PermissionScope.TENANT,
    "role.delete": PermissionScope.TENANT,
    "role.assign": PermissionScope.TENANT,
    "tenant.profile.read": PermissionScope.TENANT,
    "audit.read": PermissionScope.TENANT,
}
PHASE_02_1 = {
    "course.read": PermissionScope.CAMPUS,
    "course.manage": PermissionScope.TENANT,
    "lead.read": PermissionScope.CAMPUS,
    "lead.create": PermissionScope.CAMPUS,
    "lead.update": PermissionScope.CAMPUS,
    "lead.assign": PermissionScope.CAMPUS,
}
PHASE_02_2 = {
    "application.read": PermissionScope.CAMPUS,
    "application.create": PermissionScope.CAMPUS,
    "application.update": PermissionScope.CAMPUS,
    "application.review": PermissionScope.CAMPUS,
    "document.read": PermissionScope.CAMPUS,
    "document.upload": PermissionScope.CAMPUS,
    "document.verify": PermissionScope.CAMPUS,
    "admission.approve": PermissionScope.CAMPUS,
    "student.read": PermissionScope.CAMPUS,
}
PLATFORM_BASELINE = {
    "tenant.read",
    "tenant.create",
    "tenant.suspend",
    "tenant.reactivate",
    "platform_user.read",
    "platform_user.create",
    "platform_user.update",
    "platform_user.suspend",
    "platform_user.reactivate",
    "audit.read",
}


# --- Permission identity (D-B3) -------------------------------------------------------------


@pytest.mark.parametrize(
    "code",
    ["*", "campus.*", "campus", "Campus.read", "campus.read.", ".read", "campus read", "a." * 60],
)
def test_invalid_and_wildcard_codes_are_rejected(code: str) -> None:
    with pytest.raises(ValueError, match="invalid permission code"):
        Permission(code, Realm.TENANT, PermissionScope.TENANT, "x", "test")


@pytest.mark.parametrize("realm", [Realm.STUDENT, Realm.PUBLIC, Realm.WEBHOOK, Realm.SYSTEM])
def test_permissions_exist_only_in_the_platform_and_tenant_realms(realm: Realm) -> None:
    with pytest.raises(ValueError, match="realms"):
        Permission("campus.read", realm, None, "x", "test")


def test_tenant_permissions_need_a_scope_and_platform_ones_none() -> None:
    with pytest.raises(ValueError, match="scope"):
        Permission("campus.read", Realm.TENANT, None, "x", "test")
    with pytest.raises(ValueError, match="scope"):
        Permission("tenant.read", Realm.PLATFORM, PermissionScope.TENANT, "x", "test")


def test_identity_is_realm_and_code() -> None:
    registry = PermissionRegistry()
    tenant = registry.register(
        Permission("audit.read", Realm.TENANT, PermissionScope.TENANT, "x", "audit")
    )
    platform = registry.register(Permission("audit.read", Realm.PLATFORM, None, "y", "audit"))
    assert registry.get(Realm.TENANT, "audit.read") is tenant
    assert registry.get(Realm.PLATFORM, "audit.read") is platform
    assert registry.codes(Realm.TENANT) == {"audit.read"}
    # Re-registering the same declaration is harmless; a different one is an error.
    registry.register(Permission("audit.read", Realm.PLATFORM, None, "y", "audit"))
    with pytest.raises(DuplicatePermissionError):
        registry.register(Permission("audit.read", Realm.PLATFORM, None, "other", "audit"))


# --- The T01 catalogue ----------------------------------------------------------------------


def test_the_catalogue_is_exactly_the_t01_baseline_and_phase_02_1() -> None:
    tenant = {p.code: p.scope for p in all_permissions() if p.realm is Realm.TENANT}
    platform = {p.code for p in all_permissions() if p.realm is Realm.PLATFORM}
    assert tenant == TENANT_BASELINE | PHASE_02_1 | PHASE_02_2
    assert platform == PLATFORM_BASELINE
    assert len(all_permissions()) == len({p.key for p in all_permissions()})
    # D6-5 (T01-06) extended by D7-4 (T01-07): exactly these permissions require step-up.
    assert {p.code for p in all_permissions() if p.requires_step_up} == {
        "tenant.suspend",
        "tenant.reactivate",
        "platform_user.create",
        "platform_user.update",
        "platform_user.suspend",
        "platform_user.reactivate",
    }


def test_every_module_permissions_file_is_in_the_catalogue() -> None:
    declared = set()
    for module in pkgutil.iter_modules(app.modules.__path__, prefix="app.modules."):
        name = f"{module.name}.permissions"
        try:
            importlib.import_module(name)
        except ModuleNotFoundError as error:
            if error.name != name:
                raise
            continue
        declared.add(name)
    assert declared == set(PERMISSION_MODULES)
    assert {p.module for p in all_permissions()} <= {n.split(".")[2] for n in declared}


def test_the_model_column_length_matches_the_registry() -> None:
    assert access_models.CODE_MAX_LENGTH == CODE_MAX_LENGTH


def test_the_registry_is_the_one_used_by_the_catalogue() -> None:
    assert set(all_permissions()) == set(REGISTRY.all())


# --- Tenant system role templates (D-B2) ----------------------------------------------------


def test_system_role_templates() -> None:
    templates = {t.code: t for t in system_role_templates()}
    everything = {p.code for p in tenant_permissions()}
    assert set(templates) == set(SystemRole)
    assert set(SystemRole) == {
        SystemRole.INSTITUTE_OWNER,
        SystemRole.ADMIN,
        SystemRole.ADMISSIONS_MANAGER,
        SystemRole.COUNSELLOR,
    }
    assert templates[SystemRole.INSTITUTE_OWNER].permissions == everything
    assert templates[SystemRole.ADMIN].permissions == everything - {"role.delete"}
    assert "role.delete" not in templates[SystemRole.ADMIN].permissions
    # Phase 02-1 (L7) and 02-2 (ADR-0021 §11): the admissions team's roles hold business
    # permissions only; counsellors do not assign, manage courses, review, verify or admit.
    assert templates[SystemRole.ADMISSIONS_MANAGER].permissions == set(PHASE_02_1) | set(PHASE_02_2)
    assert templates[SystemRole.COUNSELLOR].permissions == {
        "course.read",
        "lead.read",
        "lead.create",
        "lead.update",
        "application.read",
        "application.create",
        "application.update",
        "document.read",
        "document.upload",
        "student.read",
    }
    for template in templates.values():
        assert template.permissions <= set(TENANT_BASELINE) | set(PHASE_02_1) | set(PHASE_02_2)
        assert not any("*" in code for code in template.permissions)


# --- Platform roles (ADR-0011 §3, D7) -------------------------------------------------------


def test_platform_roles_are_the_seven_fixed_codes() -> None:
    assert {role.value for role in PlatformRole} == {
        "SUPER_ADMIN",
        "PLATFORM_OPERATIONS_ADMIN",
        "CUSTOMER_SUCCESS_ADMIN",
        "BILLING_ADMIN",
        "SUPPORT_ADMIN",
        "SECURITY_AUDIT_ADMIN",
        "AI_PLATFORM_ADMIN",
    }
    assert set(PLATFORM_ROLE_PERMISSIONS) == set(PlatformRole)


def test_platform_role_permissions() -> None:
    for permissions in PLATFORM_ROLE_PERMISSIONS.values():
        assert all(p.realm is Realm.PLATFORM for p in permissions)
    assert platform_permissions(frozenset({PlatformRole.SUPER_ADMIN})) == PLATFORM_BASELINE
    assert platform_permissions(frozenset({PlatformRole.SECURITY_AUDIT_ADMIN})) == {"audit.read"}
    others = set(PlatformRole) - {PlatformRole.SUPER_ADMIN, PlatformRole.SECURITY_AUDIT_ADMIN}
    for role in others:
        assert platform_permissions(frozenset({role})) == frozenset(), role
    # Union of several roles.
    assert platform_permissions(frozenset(PlatformRole)) == PLATFORM_BASELINE


# --- Effective permissions (D-B1 filter) ----------------------------------------------------


def test_effective_permissions_keep_campus_permissions_for_restricted_members() -> None:
    codes = {"campus.read", "campus.update", "member.read", "tenant.profile.read"}
    assert effective_permissions(codes, all_campuses=True) == codes
    assert effective_permissions(codes, all_campuses=False) == {"campus.read", "campus.update"}


def test_effective_permissions_drop_unknown_and_platform_codes() -> None:
    codes = {"campus.read", "tenant.read", "campus.*", "campus.archive"}
    assert effective_permissions(codes, all_campuses=True) == {"campus.read"}
