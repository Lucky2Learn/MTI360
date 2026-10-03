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
