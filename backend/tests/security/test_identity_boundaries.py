"""Static security boundaries of T01-04: lookup keys, routes, access levels, secrets in code."""

import re
from pathlib import Path

from fastapi.routing import iter_route_contexts

from app.api.realms import Access, route_realm
from app.core.context import Realm
from app.main import create_app

APP_DIR = Path(__file__).resolve().parents[2] / "app"
LOOKUP_MODULE = APP_DIR / "modules" / "identity" / "lookup.py"
LOOKUP_SETTINGS = ("app.auth_email", "app.auth_token_hash", "app.session_token_hash")


def _python_files() -> list[Path]:
    return sorted(APP_DIR.rglob("*.py"))


def test_only_the_lookup_module_publishes_pre_authentication_keys() -> None:
    offenders = [
        str(path.relative_to(APP_DIR))
        for path in _python_files()
        if path != LOOKUP_MODULE
        and any(setting in path.read_text(encoding="utf-8") for setting in LOOKUP_SETTINGS)
    ]

    assert offenders == []


def test_authentication_routes_have_the_expected_realm_and_access(test_settings: object) -> None:
    app = create_app(test_settings)  # type: ignore[arg-type]
    routes = {
        (method, context.path): route_realm(context)
        for context in iter_route_contexts(app.routes)
        for method in getattr(context, "methods", ()) or ()
        if (context.path or "").startswith(("/api/v1/auth", "/api/v1/session"))
    }

    anonymous = (Realm.TENANT, Access.ANONYMOUS)
    session = (Realm.TENANT, Access.SESSION)
    pending = (Realm.TENANT, Access.MFA_PENDING)
    assert routes == {
        # Optional tenant MFA (T01-06).
        ("POST", "/api/v1/auth/mfa/verify"): pending,
        ("POST", "/api/v1/auth/mfa/recovery"): pending,
        ("POST", "/api/v1/session/mfa/enrolment"): session,
        ("POST", "/api/v1/session/mfa/enrolment/confirm"): session,
        ("POST", "/api/v1/session/mfa/remove"): session,
        ("POST", "/api/v1/auth/login"): anonymous,
        ("POST", "/api/v1/auth/logout"): anonymous,
        ("POST", "/api/v1/auth/password-reset"): anonymous,
        ("POST", "/api/v1/auth/password-reset/confirm"): anonymous,
        ("POST", "/api/v1/auth/invitations/preview"): anonymous,
        ("POST", "/api/v1/auth/invitations/accept"): anonymous,
        ("GET", "/api/v1/session"): session,
        ("PUT", "/api/v1/session/tenant"): session,
        ("PUT", "/api/v1/session/campus"): session,
    }


def test_no_route_takes_a_token_in_its_path_or_query(test_settings: object) -> None:
    app = create_app(test_settings)  # type: ignore[arg-type]

    for context in iter_route_contexts(app.routes):
        assert "token" not in (context.path or "").lower(), context.path
        dependant = getattr(context, "dependant", None)
        if dependant is not None:
            names = [param.name for param in (*dependant.query_params, *dependant.path_params)]
            assert not any("token" in name or "password" in name for name in names), context.path


def test_identity_code_never_logs_secret_fields() -> None:
    identity = APP_DIR / "modules" / "identity"
    pattern = re.compile(r"logger\.\w+\((.*?)\)", re.S)
    for path in identity.rglob("*.py"):
        for call in pattern.findall(path.read_text(encoding="utf-8")):
            for forbidden in ("password", "token", "message.body", "message.to", "raw_email"):
                assert forbidden not in call, f"{path.name}: logger call mentions {forbidden}"
