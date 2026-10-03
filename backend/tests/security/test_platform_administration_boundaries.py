"""Static boundaries of T01-07 platform administration (D7-1, D7-2, D7-6, D7-8, D7-10).

* Only ``app.modules.tenants.scopes`` publishes the provisioning, suspension
  and owner keys, and only it builds a platform context with a tenant.
* Only ``app.modules.platform_identity.lookup`` publishes the administration
  target key.
* There is no general tenant-data escape hatch (``unscoped``), INC-38 stays open.
"""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
SCOPES = APP / "modules" / "tenants" / "scopes.py"
LOOKUP = APP / "modules" / "platform_identity" / "lookup.py"
TENANT_SCOPE_KEYS = (
    "app.provisioning_tenant_id",
    "app.platform_target_tenant_id",
    "app.platform_owner_membership_id",
)
ADMIN_KEY = "app.platform_admin_target_user_id"


def _sources() -> list[Path]:
    return sorted(APP.rglob("*.py"))


def test_only_the_tenant_scopes_publish_their_keys() -> None:
    offenders = [
        str(path.relative_to(APP))
        for path in _sources()
        if path != SCOPES
        and any(key in path.read_text(encoding="utf-8") for key in TENANT_SCOPE_KEYS)
    ]
    assert offenders == []


def test_only_the_platform_lookup_publishes_the_administration_key() -> None:
    offenders = [
        str(path.relative_to(APP))
        for path in _sources()
        if path != LOOKUP and ADMIN_KEY in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def _platform_context_with_tenant(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
    keywords = {keyword.arg: keyword.value for keyword in node.keywords}
    if name == "replace" and "tenant_id" in keywords:
        return True  # dataclasses.replace(context, tenant_id=...)
    if name != "RequestContext" or "tenant_id" not in keywords:
        return False
    realm = keywords.get("realm")
    return isinstance(realm, ast.Attribute) and realm.attr == "PLATFORM"


def test_only_the_provisioning_scope_gives_a_platform_context_a_tenant() -> None:
    offenders = [
        f"{path.relative_to(APP)}:{node.lineno}"
        for path in _sources()
        if path != SCOPES
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call) and _platform_context_with_tenant(node)
    ]
    assert offenders == []


def test_there_is_no_unscoped_escape_hatch() -> None:
    offenders = [
        str(path.relative_to(APP))
        for path in _sources()
        if "def unscoped" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
