"""Regression test for scripts/ci/start-test-database.sh (T01-01 CI fix).

PR #14 failed because the ``::add-mask::`` workflow commands were written into
the generated ``.env`` instead of the runner output: sourcing ``.env`` then
executed them ("command not found", exit 127), the passwords were never masked,
and the error line printed a generated password. The script is run here in a
temporary directory with a stub ``docker`` that only records its arguments, so
no container, volume or local configuration is touched.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "start-test-database.sh"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(
    BASH is None or "system32" in (BASH or "").lower(),
    reason="needs a POSIX bash (Git Bash on Windows)",
)


def _run(workdir: Path, *, github_actions: str = "true") -> subprocess.CompletedProcess[str]:
    stub_dir = workdir / "stub"
    stub_dir.mkdir(exist_ok=True)
    stub = stub_dir / "docker"
    stub.write_text('#!/bin/sh\necho "$*" >> "$STUB_LOG"\n', newline="\n")
    stub.chmod(0o755)
    env = {
        **os.environ,
        "GITHUB_ACTIONS": github_actions,
        "GITHUB_ENV": "github_env",
        "STUB_LOG": "docker_calls",
        "PATH": f"{stub_dir}{os.pathsep}{os.environ.get('PATH', '')}",
    }
    return subprocess.run(  # noqa: S603 - fixed arguments, test-only
        [str(BASH), "start-test-database.sh"],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    shutil.copy(SCRIPT, tmp_path / "start-test-database.sh")
    shutil.copy(REPO_ROOT / ".env.example", tmp_path / ".env.example")
    return tmp_path


def test_generates_masked_passwords_and_exports_test_urls(workdir: Path) -> None:
    result = _run(workdir)

    assert result.returncode == 0, result.stderr
    dotenv = (workdir / ".env").read_text()
    # No workflow command and no placeholder value may end up in the sourced file.
    assert not re.search(r"^::", dotenv, re.M)
    assert not re.search(r"^[A-Z0-9_]+=change-me$", dotenv, re.M)

    placeholders = re.findall(
        r"^([A-Z0-9_]+)=change-me$", (workdir / ".env.example").read_text(), re.M
    )
    values = dict(re.findall(r"^([A-Z0-9_]+)=(.*)$", dotenv, re.M))
    masked = set(re.findall(r"^::add-mask::(\S+)$", result.stdout, re.M))
    assert placeholders
    for name in placeholders:
        assert re.fullmatch(r"[0-9a-f]{48}", values[name]), name
        assert values[name] in masked, f"{name} is not masked"
    # Generated secrets never appear in error output.
    for name in placeholders:
        assert values[name] not in result.stderr

    exported = (workdir / "github_env").read_text()
    for variable, role, password in (
        ("TEST_DATABASE_URL", "mti_app", "MTI_APP_PASSWORD"),
        ("TEST_MIGRATIONS_DATABASE_URL", "mti_owner", "MTI_OWNER_PASSWORD"),
        ("TEST_READONLY_DATABASE_URL", "mti_readonly", "MTI_READONLY_PASSWORD"),
    ):
        assert (
            f"{variable}=postgresql+asyncpg://{role}:{values[password]}@127.0.0.1:5432/mti360_test"
            in exported
        )
    assert "REQUIRE_DATABASE_TESTS=1" in exported
    assert (workdir / "docker_calls").read_text().split("\n")[0] == (
        "compose --profile infra up --detach --wait postgres"
    )


def test_refuses_to_run_outside_ci(workdir: Path) -> None:
    result = _run(workdir, github_actions="")

    assert result.returncode == 2
    assert not (workdir / ".env").exists()
    assert not (workdir / "docker_calls").exists()


def test_refuses_to_overwrite_an_existing_env_file(workdir: Path) -> None:
    (workdir / ".env").write_text("POSTGRES_PASSWORD=keep-me\n")

    result = _run(workdir)

    assert result.returncode == 2
    assert (workdir / ".env").read_text() == "POSTGRES_PASSWORD=keep-me\n"
    assert not (workdir / "docker_calls").exists()
