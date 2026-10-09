"""Development seed contract (T01-08, decision D16): the file and the command's guard."""

from types import SimpleNamespace
from typing import Any

import pytest

from app import cli
from app.seed import DEFAULT_SEED_FILE, SeededAccount, SeedError, load_seed, parse_seed


def _document(**member: Any) -> dict[str, Any]:
    return {
        "institutes": [
            {
                "name": "Malabar Seafarers Institute",
                "status": "ACTIVE",
                "campuses": [{"code": "KOC", "name": "Kochi Campus"}],
                "members": [
                    {
                        "email": "owner@malabar-seafarers.example",
                        "display_name": "Capt. Joseph Mathew",
                        "role": "INSTITUTE_OWNER",
                        **member,
                    }
                ],
            }
        ]
    }


def test_the_committed_seed_file_is_valid_and_development_only() -> None:
    institutes = load_seed(DEFAULT_SEED_FILE)
    assert len(institutes) >= 1
    for institute in institutes:
        for member in institute.members:
            assert member.email.rsplit("@", 1)[1].endswith(".example")
    text = DEFAULT_SEED_FILE.read_text(encoding="utf-8").lower()
    assert "password" not in text.replace("passwords are generated", "")


@pytest.mark.parametrize(
    ("member", "message"),
    [
        ({"email": "owner@malabar-seafarers.com"}, ".example"),
        ({"role": "SUPER_ADMIN"}, "unknown role"),
        ({"campus_scope": "SELECTED"}, "at least one campus"),
        ({"campus_scope": "SELECTED", "campuses": ["XYZ"]}, "unknown campus"),
    ],
)
def test_invalid_members_are_refused(member: dict[str, Any], message: str) -> None:
    with pytest.raises(SeedError, match=message):
        parse_seed(_document(**member))


def test_every_institute_needs_an_owner() -> None:
    document = _document(role="ADMIN")
    with pytest.raises(SeedError, match="owner"):
        parse_seed(document)


def test_the_command_refuses_outside_development(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.run_seed(
        DEFAULT_SEED_FILE,
        settings_loader=lambda: SimpleNamespace(app_env="production"),  # type: ignore[arg-type,return-value]
    )
    assert code == cli.EXIT_REFUSED
    assert "APP_ENV=development" in capsys.readouterr().err


def test_the_command_never_prints_passwords(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    accounts = [SeededAccount("owner@malabar-seafarers.example", "Secret-one-time-42")]

    async def fake_seed(*_: Any) -> list[SeededAccount]:
        return accounts

    monkeypatch.setattr(cli, "_seed", fake_seed)
    code = cli.run_seed(
        DEFAULT_SEED_FILE,
        settings_loader=lambda: SimpleNamespace(app_env="development"),  # type: ignore[arg-type,return-value]
    )
    output = capsys.readouterr()
    assert code == cli.EXIT_OK
    assert "owner@malabar-seafarers.example" in output.out
    assert "Secret-one-time-42" not in output.out + output.err


# --- Courses and leads (Phase 02-1) ---------------------------------------------------------


def _with_admissions(courses: list[Any], leads: list[Any]) -> dict[str, Any]:
    document = _document()
    document["institutes"][0]["courses"] = courses
    document["institutes"][0]["leads"] = leads
    return document


GPR = {"code": "GPR", "name": "GP Rating", "category": "PRE_SEA", "status": "ACTIVE"}
OWNER = "owner@malabar-seafarers.example"


def _lead(**fields: Any) -> dict[str, Any]:
    return {
        "key": "L1",
        "full_name": "Arjun Nair",
        "mobile": "+91 90000 10101",
        "source": "WALK_IN",
        "created_by": OWNER,
        **fields,
    }


def test_the_committed_seed_has_the_admissions_demo() -> None:
    konkan = load_seed(DEFAULT_SEED_FILE)[0]
    roles = {member.role.value for member in konkan.members}
    assert {"ADMISSIONS_MANAGER", "COUNSELLOR"} <= roles
    assert {c.status.value for c in konkan.courses} == {"DRAFT", "ACTIVE", "ARCHIVED"}
    statuses = {lead.status.value for lead in konkan.leads}
    assert statuses >= {"NEW", "CONTACTED", "QUALIFIED", "COUNSELLING", "INTERESTED"}
    assert statuses >= {"LOST", "DEFERRED", "DUPLICATE"}
    assert any(lead.campus is None for lead in konkan.leads)  # institute pool
    assert any(lead.owner is None for lead in konkan.leads)  # unassigned
    mobiles = [lead.mobile for lead in konkan.leads if lead.mobile]
    assert len(mobiles) != len(set(mobiles))  # a pair for the duplicate warning
    hours = [f.due_in_hours for lead in konkan.leads for f in lead.follow_ups]
    assert min(hours) < 0 < max(hours)  # overdue and upcoming follow-ups
    assert any(lead.notes for lead in konkan.leads)


def test_the_committed_seed_has_the_applications_demo() -> None:
    """Phase 02-2: every stage a demo needs, documents included."""
    konkan, coromandel = load_seed(DEFAULT_SEED_FILE)[:2]
    statuses = {a.status.value for a in konkan.applications}
    assert statuses >= {"DRAFT", "SUBMITTED", "CORRECTION_REQUIRED", "APPROVED", "ADMITTED"}
    assert any(a.lead is None for a in konkan.applications)  # a walk-in
    documents = {d.status.value for a in konkan.applications for d in a.documents}
    assert documents == {"UPLOADED", "UNDER_REVIEW", "VERIFIED", "REJECTED"}
    assert any(a.status.value == "ADMITTED" for a in coromandel.applications)


def _application(**fields: Any) -> dict[str, Any]:
    return {
        "key": "A1",
        "lead": "L1",
        "course": "GPR",
        "campus": "KOC",
        "created_by": OWNER,
        **fields,
    }


@pytest.mark.parametrize(
    ("application", "message"),
    [
        (_application(course="DNS"), "ACTIVE course"),
        (_application(lead="L9"), "open seed lead"),
        (_application(status="ELIGIBLE"), "reserved"),
        (_application(status="SUBMITTED"), "complete"),
        (_application(status="REJECTED", reviewed_by=OWNER), "status_reason"),
        (_application(status="APPROVED"), "reviewed_by"),
        (
            _application(documents=[{"type": "PASSPORT", "status": "VERIFIED"}]),
            "UPLOADED on drafts",
        ),
        (
            _application(lead=None, full_name="Meera Pillai", mobile="+91 98200 12345"),
            "fictitious",
        ),
        (_application(indos_number="??"), "INDoS"),
    ],
    ids=[
        "course",
        "lead",
        "reserved",
        "incomplete",
        "reason",
        "reviewer",
        "documents",
        "mobile",
        "indos",
    ],
)
def test_invalid_applications_are_refused(application: dict[str, Any], message: str) -> None:
    document = _with_admissions([GPR], [_lead()])
    document["institutes"][0]["applications"] = [application]
    with pytest.raises(SeedError, match=message):
        parse_seed(document)


@pytest.mark.parametrize(
    ("courses", "leads", "message"),
    [
        ([GPR | {"code": "G P R"}], [], "invalid course code"),
        ([GPR | {"duration_value": 6}], [], "duration"),
        ([GPR, GPR], [], "unique"),
        ([GPR], [_lead(mobile=None)], "mobile or an email"),
        ([GPR], [_lead(mobile="+91 98200 12345")], "fictitious"),
        ([GPR], [_lead(mobile=None, email="arjun@gmail.com")], "example.com"),
        ([GPR], [_lead(course="DNS")], "unknown course"),
        ([GPR], [_lead(campus="MUM")], "unknown campus"),
        ([GPR], [_lead(owner="someone@malabar-seafarers.example")], "seed members"),
        ([GPR], [_lead(status="APPLICATION")], "02-2"),
        ([GPR], [_lead(status="LOST")], "status_reason"),
        ([GPR], [_lead(status="DUPLICATE")], "duplicate_of"),
        ([GPR], [_lead(), _lead(status="DUPLICATE", duplicate_of="L9")], "duplicate key"),
    ],
)
def test_invalid_courses_and_leads_are_refused(
    courses: list[Any], leads: list[Any], message: str
) -> None:
    with pytest.raises(SeedError, match=message):
        parse_seed(_with_admissions(courses, leads))
