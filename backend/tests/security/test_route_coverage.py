"""Route authorization coverage (T01-05; ADR-0011 §4).

Every API route of the real application requires exactly one permission or
has a reviewed exemption that matches its access level. The checker is
proven not to pass vacuously: it finds an accidentally unprotected route and
every kind of misuse.
"""

from types import MappingProxyType
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import iter_route_contexts

from app.api.coverage import REVIEWED_EXEMPTIONS, Exemption, ReviewedExemption, coverage_violations
from app.api.realms import REALM_PREFIXES, Access, realm_router
from app.core.authz import Permission, PermissionScope, require_permission, route_permissions
from app.core.config import Settings
from app.core.context import Realm
from app.main import create_app

CAMPUS_READ = Permission("campus.read", Realm.TENANT, PermissionScope.CAMPUS, "x", "test")
MEMBER_READ = Permission("member.read", Realm.TENANT, PermissionScope.TENANT, "x", "test")
TENANT_READ = Permission("tenant.read", Realm.PLATFORM, None, "x", "test")

T01_04_ROUTES = {
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/logout"),
    ("POST", "/api/v1/auth/password-reset"),
    ("POST", "/api/v1/auth/password-reset/confirm"),
    ("POST", "/api/v1/auth/invitations/preview"),
    ("POST", "/api/v1/auth/invitations/accept"),
    ("GET", "/api/v1/session"),
    ("PUT", "/api/v1/session/tenant"),
    ("PUT", "/api/v1/session/campus"),
}
T01_06_TENANT_MFA_PENDING = {
    ("POST", "/api/v1/auth/mfa/verify"),
    ("POST", "/api/v1/auth/mfa/recovery"),
}
T01_06_TENANT_MFA_SESSION = {
    ("POST", "/api/v1/session/mfa/enrolment"),
    ("POST", "/api/v1/session/mfa/enrolment/confirm"),
    ("POST", "/api/v1/session/mfa/remove"),
}
T01_06_PLATFORM_PUBLIC = {
    ("POST", "/api/v1/platform/auth/login"),
    ("POST", "/api/v1/platform/auth/logout"),
    ("POST", "/api/v1/platform/auth/password-reset"),
    ("POST", "/api/v1/platform/auth/password-reset/confirm"),
}
T01_07_PLATFORM_PUBLIC = {
    ("POST", "/api/v1/platform/auth/invitations/preview"),
    ("POST", "/api/v1/platform/auth/invitations/accept"),
}
T01_06_PLATFORM_MFA_PENDING = {
    ("POST", "/api/v1/platform/auth/mfa/enrolment"),
    ("POST", "/api/v1/platform/auth/mfa/enrolment/confirm"),
    ("POST", "/api/v1/platform/auth/mfa/verify"),
    ("POST", "/api/v1/platform/auth/mfa/recovery"),
}
T01_06_PLATFORM_SESSION = {
    ("GET", "/api/v1/platform/session"),
    ("POST", "/api/v1/platform/session/step-up"),
    ("POST", "/api/v1/platform/session/mfa/recovery-codes"),
}


@pytest.fixture
def app(test_settings: Settings) -> FastAPI:
    return create_app(test_settings)


def _mount(app: FastAPI, access: Access, *dependencies: Any, path: str = "/probe") -> None:
    router = realm_router(Realm.TENANT, access=access)

    @router.get(path, dependencies=list(dependencies))
    async def probe() -> None:  # pragma: no cover - never called
        return None

    app.include_router(router, prefix=REALM_PREFIXES[Realm.TENANT])


def test_every_route_of_the_application_is_covered(app: FastAPI) -> None:
    assert coverage_violations(app) == []


def test_the_reviewed_exemptions_are_the_authentication_routes_with_reasons() -> None:
    assert set(REVIEWED_EXEMPTIONS) == (
        T01_04_ROUTES
        | T01_06_TENANT_MFA_PENDING
        | T01_06_TENANT_MFA_SESSION
        | T01_06_PLATFORM_PUBLIC
        | T01_07_PLATFORM_PUBLIC
        | T01_06_PLATFORM_MFA_PENDING
        | T01_06_PLATFORM_SESSION
    )
    for exemption in REVIEWED_EXEMPTIONS.values():
        assert len(exemption.reason) >= 20

    def kind(kind: Exemption) -> set[tuple[str, str]]:
        return {key for key, value in REVIEWED_EXEMPTIONS.items() if value.kind is kind}

    assert (
        kind(Exemption.AUTHENTICATED_ONLY)
        == {
            ("GET", "/api/v1/session"),
            ("PUT", "/api/v1/session/tenant"),
            ("PUT", "/api/v1/session/campus"),
        }
        | T01_06_PLATFORM_SESSION
        | T01_06_TENANT_MFA_SESSION
    )
    assert kind(Exemption.MFA_PENDING) == (T01_06_PLATFORM_MFA_PENDING | T01_06_TENANT_MFA_PENDING)


def test_mfa_pending_exemptions_need_an_mfa_pending_route(app: FastAPI) -> None:
    _mount(app, Access.AUTHENTICATED, path="/probe/pending")
    exemptions = MappingProxyType(
        {
            **REVIEWED_EXEMPTIONS,
            ("GET", "/api/v1/probe/pending"): ReviewedExemption(Exemption.MFA_PENDING, "test"),
        }
    )
    assert coverage_violations(app, exemptions) == [
        "GET /api/v1/probe/pending: mfa_pending on a authenticated route"
    ]


def test_an_accidentally_unprotected_route_fails(app: FastAPI) -> None:
    _mount(app, Access.AUTHENTICATED)
    assert coverage_violations(app) == [
        "GET /api/v1/probe: no require_permission and no reviewed exemption"
    ]


def test_a_route_with_one_permission_passes(app: FastAPI) -> None:
    _mount(app, Access.AUTHENTICATED, require_permission(CAMPUS_READ))
    assert coverage_violations(app) == []


def test_the_permission_is_found_through_nested_routers(app: FastAPI) -> None:
    _mount(app, Access.AUTHENTICATED, require_permission(MEMBER_READ))
    found = [
        route_permissions(getattr(route, "dependant", None))
        for route in iter_route_contexts(app.routes)
        if route.path == "/api/v1/probe"
    ]
    assert found == [[MEMBER_READ]]


@pytest.mark.parametrize(
    ("access", "dependencies", "problem"),
    [
        (
            Access.AUTHENTICATED,
            (require_permission(CAMPUS_READ), require_permission(MEMBER_READ)),
            "more than one require_permission",
        ),
        (Access.AUTHENTICATED, (require_permission(TENANT_READ),), "permission of another realm"),
        (
            Access.ANONYMOUS,
            (require_permission(CAMPUS_READ),),
            "a permission on an anonymous route",
        ),
    ],
)
def test_misused_permissions_fail(
    app: FastAPI, access: Access, dependencies: tuple[Any, ...], problem: str
) -> None:
    _mount(app, access, *dependencies)
    assert [f"GET /api/v1/probe: {problem}"] == coverage_violations(app)


def test_exemptions_must_match_the_access_level_and_not_be_stale(app: FastAPI) -> None:
    _mount(app, Access.AUTHENTICATED, path="/probe/public")
    _mount(app, Access.ANONYMOUS, path="/probe/own")
    _mount(app, Access.AUTHENTICATED, require_permission(CAMPUS_READ), path="/probe/both")
    exemptions = MappingProxyType(
        {
            **REVIEWED_EXEMPTIONS,
            ("GET", "/api/v1/probe/public"): ReviewedExemption(Exemption.PUBLIC_ROUTE, "test"),
            ("GET", "/api/v1/probe/own"): ReviewedExemption(Exemption.AUTHENTICATED_ONLY, "test"),
            ("GET", "/api/v1/probe/both"): ReviewedExemption(Exemption.AUTHENTICATED_ONLY, "test"),
            ("GET", "/api/v1/removed"): ReviewedExemption(Exemption.PUBLIC_ROUTE, "test"),
        }
    )
    assert coverage_violations(app, exemptions) == [
        "GET /api/v1/probe/public: public_route on a authenticated route",
        "GET /api/v1/probe/own: authenticated_only on a anonymous route",
        "GET /api/v1/probe/both: both a permission and an exemption",
        "GET /api/v1/removed: stale exemption",
    ]


def test_an_authenticated_only_exemption_is_accepted_on_an_authenticated_route(
    app: FastAPI,
) -> None:
    _mount(app, Access.AUTHENTICATED, path="/probe/me")
    exemptions = MappingProxyType(
        {
            **REVIEWED_EXEMPTIONS,
            ("GET", "/api/v1/probe/me"): ReviewedExemption(
                Exemption.AUTHENTICATED_ONLY, "The caller's own profile."
            ),
        }
    )
    assert coverage_violations(app, exemptions) == []
