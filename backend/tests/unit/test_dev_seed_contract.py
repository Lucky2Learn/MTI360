"""Development seed contract (T01-08, decision D16): the file and the command's guard."""

import dataclasses
from types import SimpleNamespace
from typing import Any

import pytest

from app import cli
from app.seed import (
    DEFAULT_SEED_FILE,
    SeededAccount,
    SeedError,
    SeedInstitute,
    load_seed,
    parse_seed,
    tag_seed,
)
from app.seed_admissions import is_development_email


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
        # ADR-0023: an owner keeps all-campus access.
        ({"campus_scope": "SELECTED", "campuses": ["KOC"]}, "all-campus access"),
    ],
)
def test_invalid_members_are_refused(member: dict[str, Any], message: str) -> None:
    with pytest.raises(SeedError, match=message):
        parse_seed(_document(**member))


def test_a_campus_limited_administrator_is_still_accepted() -> None:
    document = _document()
    document["institutes"][0]["members"].append(
        {
            "email": "admissions@malabar-seafarers.example",
            "display_name": "Anita Kurian",
            "role": "ADMIN",
            "campus_scope": "SELECTED",
            "campuses": ["KOC"],
        }
    )
    (institute,) = parse_seed(document)
    assert [m.campus_scope.value for m in institute.members] == ["ALL", "SELECTED"]


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
        (
            _application(lead=None, full_name="Meera Pillai", email="meera@notexample.com"),
            "example.com",
        ),
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
        "email-lookalike",
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
        ([GPR], [_lead(mobile=None, email="arjun@notexample.com")], "example.com"),
        ([GPR], [_lead(mobile=None, email="arjun@example.com.in")], "example.com"),
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


@pytest.mark.parametrize(
    ("email", "development"),
    [
        ("arjun@example.com", True),
        ("arjun@mail.example.com", True),
        ("arjun@notexample.com", False),  # CodeQL py/incomplete-url-substring-sanitization
        ("arjun@example.com.in", False),
        ("arjun@example.co", False),
        ("example.com@gmail.com", False),
    ],
)
def test_only_the_reserved_example_domain_is_a_development_email(
    email: str, development: bool
) -> None:
    assert is_development_email(email) is development


# --- The §21 demo and repeatable demo copies (Phase 02-3) -----------------------------------


def test_the_committed_seed_supports_the_demo_storyline() -> None:
    """PHASE-02-MASTER-READINESS §21, step by step (docs/runbooks/demo.md)."""
    konkan, coromandel = load_seed(DEFAULT_SEED_FILE)[:2]
    campuses = {code for code, _ in konkan.campuses}
    assert len(campuses) == 2
    by_role: dict[str, list[Any]] = {}
    for member in konkan.members:
        by_role.setdefault(member.role.value, []).append(member)
    # An owner and an admissions manager on every campus, and one counsellor per campus.
    assert all(m.campus_scope.value == "ALL" for m in by_role["INSTITUTE_OWNER"])
    assert any(m.campus_scope.value == "ALL" for m in by_role["ADMISSIONS_MANAGER"])
    assert {m.campuses for m in by_role["COUNSELLOR"]} == {(code,) for code in campuses}
    # 1. The three demo courses are open for admission.
    active = {c.code for c in konkan.courses if c.status.value == "ACTIVE"}
    assert {"GPR", "DNS", "STCW-BST"} <= active
    # 2. A known mobile number fires the duplicate warning.
    assert any(lead.status.value == "DUPLICATE" and lead.duplicate_of for lead in konkan.leads)
    # 4. A qualified lead is ready to convert (no application yet).
    applied = {a.lead for a in konkan.applications}
    assert any(
        lead.status.value == "QUALIFIED" and lead.key not in applied for lead in konkan.leads
    )
    # 5. A submitted application has a medical certificate waiting for the verifier.
    assert any(
        a.status.value == "SUBMITTED"
        and any(
            d.document_type.value == "MEDICAL_CERTIFICATE" and d.status.value == "UNDER_REVIEW"
            for d in a.documents
        )
        for a in konkan.applications
    )
    # 6. An approved application waits for the manager's admission approval.
    assert any(a.status.value == "APPROVED" for a in konkan.applications)
    # 8. Each campus has its own leads, and a second institute shows isolation.
    assert {lead.campus for lead in konkan.leads} >= campuses
    assert coromandel.name != konkan.name
    assert coromandel.leads


def _strings(value: object) -> set[str]:
    """Every string anywhere in a seed value (dataclasses, tuples)."""
    if isinstance(value, str):
        return {value}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return set().union(*(_strings(getattr(value, f.name)) for f in dataclasses.fields(value)))
    if isinstance(value, tuple):
        return set().union(*(_strings(item) for item in value))
    return set()


def test_a_tag_moves_every_member_reference_to_the_tagged_accounts() -> None:
    institutes = load_seed(DEFAULT_SEED_FILE)
    tagged = tag_seed(institutes, "demo2")
    original = {m.email for i in institutes for m in i.members}
    accounts = {m.email for i in tagged for m in i.members}
    assert len(accounts) == len(original)
    assert all(email.endswith(".example") and ".demo2@" in email for email in accounts)
    # No reference to an original account is left anywhere (leads, applications, finance).
    assert not _strings(tagged) & original
    references = {s for s in _strings(tagged) if "@" in s and s.endswith(".example")}
    assert references == accounts
    for before, after in zip(institutes, tagged, strict=True):
        assert after.name == f"{before.name} (demo2)"
        assert after.tag == "demo2"
        assert after.campuses == before.campuses
        assert after.courses == before.courses
        assert [lead.key for lead in after.leads] == [lead.key for lead in before.leads]
        assert [lead.mobile for lead in after.leads] == [lead.mobile for lead in before.leads]


@pytest.mark.parametrize("tag", ["", "Demo2", "demo-2", "demo 2", "../x", "x" * 17, "démo"])
def test_invalid_tags_are_refused(tag: str) -> None:
    with pytest.raises(SeedError, match="tag"):
        tag_seed(load_seed(DEFAULT_SEED_FILE), tag)


def _seed_command(
    monkeypatch: pytest.MonkeyPatch, tag: str | None
) -> tuple[int, list[tuple[SeedInstitute, ...]]]:
    received: list[tuple[SeedInstitute, ...]] = []

    async def fake_seed(_: Any, institutes: tuple[SeedInstitute, ...]) -> list[SeededAccount]:
        received.append(institutes)
        return [SeededAccount(m.email, "Secret-one-time-42") for m in institutes[0].members]

    monkeypatch.setattr(cli, "_seed", fake_seed)
    code = cli.run_seed(
        DEFAULT_SEED_FILE,
        tag=tag,
        settings_loader=lambda: SimpleNamespace(app_env="development"),  # type: ignore[arg-type,return-value]
    )
    return code, received


def test_the_command_loads_a_tagged_copy(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, received = _seed_command(monkeypatch, "demo2")
    output = capsys.readouterr()
    assert code == cli.EXIT_OK
    assert received == [tag_seed(load_seed(DEFAULT_SEED_FILE), "demo2")]
    assert "Konkan Maritime Training Institute (demo2)" in output.out
    assert "principal.demo2@konkan-maritime.example" in output.out
    assert "Secret-one-time-42" not in output.out + output.err


def test_the_command_refuses_an_invalid_tag_before_seeding(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, received = _seed_command(monkeypatch, "Demo-2")
    assert code == cli.EXIT_REFUSED
    assert received == []
    assert "tag" in capsys.readouterr().err


def test_the_command_line_accepts_a_tag() -> None:
    args = cli.parser().parse_args(["seed", "--tag", "demo2"])
    assert (args.command, args.tag) == ("seed", "demo2")
    assert cli.parser().parse_args(["seed"]).tag is None
