"""Static security boundaries of T01-06: platform lookup keys, MFA secrets, logging."""

import re
from pathlib import Path

from app.modules.identity import schemas as identity_schemas
from app.modules.platform_identity import schemas as platform_schemas

APP_DIR = Path(__file__).resolve().parents[2] / "app"
PLATFORM_LOOKUP = APP_DIR / "modules" / "platform_identity" / "lookup.py"
PLATFORM_KEYS = (
    "app.platform_auth_email",
    "app.platform_auth_token_hash",
    "app.platform_session_token_hash",
    "app.platform_mfa_reset_user_id",
    "app.platform_admin_target_user_id",  # T01-07, D7-2
)
SETTINGS_MODULE = APP_DIR / "core" / "db" / "settings.py"
# The setting as a string literal (documentation mentions it in ``double backticks``).
PRINCIPAL_LITERAL = re.compile(r"[\"']app\.platform_user_id[\"']")


def _python_files() -> list[Path]:
    return sorted(APP_DIR.rglob("*.py"))


def test_only_the_platform_lookup_module_publishes_platform_keys() -> None:
    offenders = [
        str(path.relative_to(APP_DIR))
        for path in _python_files()
        if path != PLATFORM_LOOKUP
        and any(key in path.read_text(encoding="utf-8") for key in PLATFORM_KEYS)
    ]
    assert offenders == []


def test_only_the_transaction_settings_publish_the_platform_principal() -> None:
    offenders = [
        str(path.relative_to(APP_DIR))
        for path in _python_files()
        if path != SETTINGS_MODULE and PRINCIPAL_LITERAL.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_secrets_appear_only_in_the_responses_that_create_them() -> None:
    """``secret`` and ``recovery_codes`` fields exist only in the enrolment/regeneration schemas."""
    allowed = {"MfaEnrolmentOut", "RecoveryCodesOut", "MfaEnrolmentConfirmedOut"}
    for module in (identity_schemas, platform_schemas):
        for name in dir(module):
            model = getattr(module, name)
            fields = getattr(model, "model_fields", None)
            if not isinstance(fields, dict) or name.endswith("Request"):
                continue
            exposed = {"secret", "recovery_codes", "password", "password_hash", "token_hash"}
            if exposed & set(fields):
                assert name in allowed, name


def test_security_code_never_logs_secret_fields() -> None:
    pattern = re.compile(r"logger\.\w+\((.*?)\)", re.S)
    folders = (APP_DIR / "modules" / "platform_identity", APP_DIR / "core" / "security")
    for folder in folders:
        for path in folder.rglob("*.py"):
            for call in pattern.findall(path.read_text(encoding="utf-8")):
                for forbidden in ("password", "token", "secret", "code", "plaintext", "key"):
                    assert forbidden not in call.replace("factor_id", ""), (
                        f"{path.name}: logger call mentions {forbidden}"
                    )
