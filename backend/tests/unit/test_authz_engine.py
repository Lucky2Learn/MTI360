"""``authorize`` decision order and outcomes (T01-05; D-B1, ADR-0011 §4).

Pure unit tests: the context is built directly, as the realm guard would.
"""

import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

import pytest

from app.core.authz import (
    STEP_UP_WINDOW,
    Permission,
    PermissionScope,
    authorize,
    require_fresh_mfa,
)
from app.core.context import Realm, RequestContext
from app.core.errors import (
    AuthenticationRequiredError,
    NotFoundError,
    PermissionDeniedError,
    StepUpRequiredError,
)

TENANT = uuid.uuid7()
OTHER_TENANT = uuid.uuid7()
MUMBAI, PUNE, GOA = uuid.uuid7(), uuid.uuid7(), uuid.uuid7()
USER = uuid.uuid7()

CAMPUS_READ = Permission("campus.read", Realm.TENANT, PermissionScope.CAMPUS, "x", "test")
MEMBER_READ = Permission("member.read", Realm.TENANT, PermissionScope.TENANT, "x", "test")
TENANT_READ = Permission("tenant.read", Realm.PLATFORM, None, "x", "test")
STEP_UP = Permission(
    "member.revoke", Realm.TENANT, PermissionScope.TENANT, "x", "test", requires_step_up=True
)


@dataclass(frozen=True)
class Resource:
    tenant_id: uuid.UUID
    campus_id: uuid.UUID | None = None


def context(
    *,
    realm: Realm = Realm.TENANT,
    principal: uuid.UUID | None = USER,
    tenant: uuid.UUID | None = TENANT,
    permissions: tuple[str, ...] = ("campus.read", "member.read", "member.revoke"),
    all_campuses: bool = True,
    campuses: tuple[uuid.UUID, ...] = (MUMBAI, PUNE),
) -> RequestContext:
    return RequestContext(
        realm=realm,
        request_id=uuid.uuid7(),
        principal_id=principal,
        tenant_id=tenant,
        permissions=frozenset(permissions),
        all_campuses=all_campuses,
        campus_ids=frozenset(campuses),
    )


def test_an_unauthenticated_request_is_401_before_anything_else() -> None:
    with pytest.raises(AuthenticationRequiredError):
        authorize(context(principal=None, realm=Realm.PLATFORM, tenant=None), MEMBER_READ)


def test_a_permission_of_another_realm_is_denied() -> None:
    with pytest.raises(PermissionDeniedError):
        authorize(context(permissions=("tenant.read",)), TENANT_READ)
    with pytest.raises(PermissionDeniedError):
        authorize(context(realm=Realm.PLATFORM, tenant=None), MEMBER_READ)
    with pytest.raises(PermissionDeniedError):
        authorize(context(realm=Realm.STUDENT), CAMPUS_READ)


def test_a_tenant_permission_needs_an_active_tenant() -> None:
    with pytest.raises(PermissionDeniedError):
        authorize(context(tenant=None), MEMBER_READ)


def test_step_up_permissions_need_a_fresh_mfa_verification() -> None:
    now = datetime.now(UTC)
    # Never verified, verified 11 minutes ago, or a timestamp in the future: stale.
    for verified in (None, now - timedelta(minutes=11), now + timedelta(minutes=1)):
        with pytest.raises(StepUpRequiredError):
            authorize(replace(context(), mfa_verified_at=verified), STEP_UP)
    authorize(replace(context(), mfa_verified_at=now - timedelta(minutes=9)), STEP_UP)
    # A caller without the permission is refused (403), never asked to step up.
    with pytest.raises(PermissionDeniedError):
        authorize(replace(context(permissions=()), mfa_verified_at=None), STEP_UP)
    # Permissions without the flag ignore MFA freshness.
    authorize(replace(context(), mfa_verified_at=None), MEMBER_READ)


def test_the_step_up_window_is_ten_minutes() -> None:
    assert timedelta(minutes=10) == STEP_UP_WINDOW
    moment = datetime.now(UTC)
    edge = replace(context(), mfa_verified_at=moment - STEP_UP_WINDOW)
    require_fresh_mfa(edge, now=moment)
    with pytest.raises(StepUpRequiredError):
        require_fresh_mfa(edge, now=moment + timedelta(seconds=1))


def test_a_missing_permission_is_403() -> None:
    with pytest.raises(PermissionDeniedError):
        authorize(context(permissions=("campus.read",)), MEMBER_READ)


def test_a_held_permission_is_allowed() -> None:
    authorize(context(), MEMBER_READ)
    authorize(context(), CAMPUS_READ)
    authorize(context(realm=Realm.PLATFORM, tenant=None, permissions=("tenant.read",)), TENANT_READ)


def test_tenant_wide_permissions_need_all_campus_access() -> None:
    restricted = context(all_campuses=False)
    with pytest.raises(PermissionDeniedError):
        authorize(restricted, MEMBER_READ)
    authorize(restricted, CAMPUS_READ)


def test_another_tenants_resource_is_not_found() -> None:
    for permission in (MEMBER_READ, CAMPUS_READ):
        with pytest.raises(NotFoundError):
            authorize(context(), permission, Resource(OTHER_TENANT))
        with pytest.raises(NotFoundError):
            authorize(context(all_campuses=False), CAMPUS_READ, Resource(OTHER_TENANT, MUMBAI))


def test_campus_resources_follow_the_permitted_campuses_not_the_active_one() -> None:
    restricted = context(all_campuses=False, campuses=(MUMBAI, PUNE))
    # Any permitted campus is allowed, whichever campus is active (D-B1).
    authorize(restricted, CAMPUS_READ, Resource(TENANT, MUMBAI))
    authorize(restricted, CAMPUS_READ, Resource(TENANT, PUNE))
    # A campus outside the permitted set is not found.
    with pytest.raises(NotFoundError):
        authorize(restricted, CAMPUS_READ, Resource(TENANT, GOA))
    # All-campus members reach every campus of their tenant.
    authorize(context(all_campuses=True, campuses=()), CAMPUS_READ, Resource(TENANT, GOA))
    # A tenant-level resource has no campus to check.
    authorize(restricted, CAMPUS_READ, Resource(TENANT, None))


def test_the_missing_permission_is_checked_before_the_resource() -> None:
    # A caller without the permission learns nothing about the resource (403, not 404).
    with pytest.raises(PermissionDeniedError):
        authorize(context(permissions=()), CAMPUS_READ, Resource(OTHER_TENANT, GOA))


def test_denials_carry_no_authorization_details() -> None:
    with pytest.raises(PermissionDeniedError) as denied:
        authorize(context(permissions=()), MEMBER_READ)
    assert "member" not in str(denied.value).lower()
    with pytest.raises(NotFoundError) as missing:
        authorize(context(), CAMPUS_READ, Resource(OTHER_TENANT, GOA))
    assert str(OTHER_TENANT) not in str(missing.value)
