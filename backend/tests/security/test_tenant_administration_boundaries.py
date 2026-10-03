"""Static boundaries of T01-08 tenant administration (D8-1, D8-3, T01-04 D16).

* Only ``app.modules.identity.members`` publishes the invitee key
  (``app.tenant_invitee_user_id``, D8-1).
* Application code never deletes identity rows (T01-04 D16): campus-scope
  changes mark ``membership_campuses.removed_at`` instead.
* Member administration never revokes sessions (D8-3): access ends through the
  per-request membership re-check.
"""

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
MEMBERS = APP / "modules" / "identity" / "members.py"
INVITEE_KEY = "app.tenant_invitee_user_id"
IDENTITY_TABLES = (
    "USERS",
    "CREDENTIALS",
    "MEMBERSHIPS",
    "MEMBERSHIP_CAMPUSES",
    "SESSIONS",
    "RESET_TOKENS",
    "INVITATIONS",
)
DELETE = re.compile(rf"delete\(\s*({'|'.join(IDENTITY_TABLES)})\b")


def _sources() -> list[Path]:
    return sorted(APP.rglob("*.py"))


def test_only_the_member_module_publishes_the_invitee_key() -> None:
    offenders = [
        str(path.relative_to(APP))
        for path in _sources()
        if path != MEMBERS and INVITEE_KEY in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_identity_rows_are_never_deleted() -> None:
    offenders = [
        str(path.relative_to(APP))
        for path in (APP / "modules" / "identity").rglob("*.py")
        if DELETE.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_member_administration_never_revokes_sessions() -> None:
    for name in ("members.py", "members_repository.py"):
        source = (APP / "modules" / "identity" / name).read_text(encoding="utf-8")
        assert "revoke_user_sessions" not in source
        assert "SESSIONS" not in source
