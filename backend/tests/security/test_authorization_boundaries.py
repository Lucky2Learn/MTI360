"""Static authorization boundaries of the code base (T01-05 security rules).

* Authorization never depends on role names or role codes: they appear only
  where roles are defined (the templates and the platform role map).
* Permission codes are written only in the modules' ``permissions.py``;
  everything else references the declared constants.
* No module registers permissions at runtime or writes the catalogue.
"""

import re
from pathlib import Path

from app.modules.access.catalog import all_permissions

APP = Path(__file__).resolve().parents[2] / "app"
# Where roles are defined, or assigned by the D6-1 bootstrap (never authorization decisions).
ROLE_DEFINITIONS = {
    APP / "modules" / "access" / "templates.py",
    APP / "modules" / "platform_identity" / "roles.py",
    APP / "modules" / "platform_identity" / "bootstrap.py",
    APP / "cli.py",
}
ROLE_WORDS = re.compile(
    r"INSTITUTE_OWNER|SUPER_ADMIN|SECURITY_AUDIT_ADMIN|PLATFORM_OPERATIONS_ADMIN|"
    r"CUSTOMER_SUCCESS_ADMIN|BILLING_ADMIN|SUPPORT_ADMIN|AI_PLATFORM_ADMIN|"
    r"[\"']ADMIN[\"']|Institute owner|Administrator"
)
DECLARATION = re.compile(r"=\s*permission\(")
CATALOGUE_WRITE = re.compile(r"(insert|update|delete)\(\s*PermissionRecord\b")
CODE_LITERAL = re.compile(r"[\"']([a-z_]+(?:\.[a-z_]+)+)[\"']")


def _sources() -> list[Path]:
    return sorted(APP.rglob("*.py"))


def _code_lines(path: Path) -> list[str]:
    """Source lines outside docstrings and comments (good enough for literals)."""
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'"""[\s\S]*?"""', "", text)
    return [line.split("#", 1)[0] for line in text.splitlines()]


def test_role_names_are_not_authorization_logic() -> None:
    offenders = [
        f"{path.relative_to(APP)}: {line.strip()}"
        for path in _sources()
        if path not in ROLE_DEFINITIONS
        for line in _code_lines(path)
        if ROLE_WORDS.search(line)
    ]
    assert offenders == []


def test_permission_codes_are_written_only_in_permissions_modules() -> None:
    codes = {p.code for p in all_permissions()}
    offenders = [
        f"{path.relative_to(APP)}: {match}"
        for path in _sources()
        if path.name != "permissions.py"
        for line in _code_lines(path)
        for match in CODE_LITERAL.findall(line)
        if match in codes
    ]
    assert offenders == []


def test_permissions_are_declared_only_in_permissions_modules_and_never_written() -> None:
    for path in _sources():
        text = "\n".join(_code_lines(path))
        if path.name != "permissions.py":
            assert not DECLARATION.search(text), path
        assert not CATALOGUE_WRITE.search(text), path
