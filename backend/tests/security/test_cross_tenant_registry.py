"""Every business route has an explicit cross-tenant test (Phase 02-1; INC-46).

Static meta-test over the real application: a route served by a business
module (``BUSINESS_MODULES``) must be in ``BUSINESS_ROUTES`` and its test
must exist in one of the cross-tenant suites; registry entries must match real
routes; every other authenticated tenant route must belong to a module whose
existing isolation suite is recorded in ``T01_SUITES``.
"""

import ast
from pathlib import Path

from cross_tenant_registry import (
    BUSINESS_MODULES,
    BUSINESS_ROUTES,
    CROSS_TENANT_SUITES,
    T01_SUITES,
)
from fastapi import FastAPI
from fastapi.routing import iter_route_contexts

from app.api.realms import API_PREFIX, Access, route_realm
from app.core.context import Realm

BACKEND = Path(__file__).resolve().parents[2]


def _tenant_routes(app: FastAPI) -> dict[tuple[str, str], str]:
    """``(method, path) → endpoint module`` of the authenticated tenant routes."""
    found: dict[tuple[str, str], str] = {}
    for route in iter_route_contexts(app.routes):
        path = route.path or ""
        endpoint = getattr(route, "endpoint", None)
        if not path.startswith(API_PREFIX) or endpoint is None:
            continue
        if route_realm(route) != (Realm.TENANT, Access.AUTHENTICATED):
            continue
        for method in getattr(route, "methods", None) or ():
            found[(method, path)] = endpoint.__module__
    return found


def _suite_tests() -> set[str]:
    names: set[str] = set()
    for suite in CROSS_TENANT_SUITES:
        tree = ast.parse((BACKEND / suite).read_text(encoding="utf-8"))
        names |= {
            node.name
            for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
            and node.name.startswith("test_")
        }
    return names


def _business(module: str) -> bool:
    return any(module == name or module.startswith(f"{name}.") for name in BUSINESS_MODULES)


def registry_problems(routes: dict[tuple[str, str], str], tests: set[str]) -> list[str]:
    business = {key for key, module in routes.items() if _business(module)}
    problems = [
        f"{m} {p}: no cross-tenant test" for m, p in sorted(business - set(BUSINESS_ROUTES))
    ]
    problems += [f"{m} {p}: stale entry" for m, p in sorted(set(BUSINESS_ROUTES) - business)]
    problems += [
        f"{m} {p}: {name} is not in the suite"
        for (m, p), name in sorted(BUSINESS_ROUTES.items())
        if (m, p) in business and name not in tests
    ]
    return problems


def test_every_business_route_has_a_cross_tenant_test(app: FastAPI) -> None:
    routes = _tenant_routes(app)
    assert sum(_business(module) for module in routes.values()) == len(BUSINESS_ROUTES)
    assert registry_problems(routes, _suite_tests()) == []


def test_every_other_tenant_route_has_a_recorded_isolation_suite(app: FastAPI) -> None:
    for (method, path), module in _tenant_routes(app).items():
        if _business(module):
            continue
        owner = next((name for name in T01_SUITES if module.startswith(name)), None)
        assert owner is not None, f"{method} {path} ({module}) has no recorded isolation suite"
    for suite in T01_SUITES.values():
        assert (BACKEND / suite).is_file(), suite


def test_the_registry_check_is_not_vacuous(app: FastAPI) -> None:
    routes = _tenant_routes(app) | {("GET", "/api/v1/leads/{lead_id}/probe"): "app.modules.leads.x"}
    tests = _suite_tests() - {"test_other_tenant_follow_ups_are_not_found"}
    problems = registry_problems(routes, tests)
    assert "GET /api/v1/leads/{lead_id}/probe: no cross-tenant test" in problems
    assert any("test_other_tenant_follow_ups_are_not_found" in p for p in problems)
    without_route = {k: v for k, v in routes.items() if k != ("GET", "/api/v1/courses")}
    assert "GET /api/v1/courses: stale entry" in registry_problems(without_route, _suite_tests())
