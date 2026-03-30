"""Regression coverage for bundled Entrix skill fixtures."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from shutil import copytree

import pytest


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "skill_regression"
ENTRIX_CMD = [sys.executable, "-m", "entrix"]


def run_entrix(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*ENTRIX_CMD, *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )


def materialize_fixture(tmp_path: Path, fixture_name: str) -> Path:
    source_root = FIXTURE_ROOT / fixture_name
    fixture_root = tmp_path / fixture_name
    copytree(source_root, fixture_root)
    subprocess.run(["git", "init", "-q"], cwd=fixture_root, check=True)
    return fixture_root


@pytest.mark.parametrize(
    ("fixture_name", "expects_agents", "expects_claude"),
    [
        ("dual-entry-local-green", True, True),
        ("claude-only-ci-boundary", False, True),
    ],
)
def test_fixture_entrypoint_topology(
    fixture_name: str, expects_agents: bool, expects_claude: bool
) -> None:
    fixture_root = FIXTURE_ROOT / fixture_name
    assert (fixture_root / "AGENTS.md").exists() is expects_agents
    assert (fixture_root / "CLAUDE.md").exists() is expects_claude


@pytest.mark.parametrize(
    "fixture_name",
    [
        "dual-entry-local-green",
        "claude-only-ci-boundary",
    ],
)
def test_fixture_repositories_validate_and_run_locally(
    tmp_path: Path, fixture_name: str
) -> None:
    fixture_root = materialize_fixture(tmp_path, fixture_name)

    for args in (
        ("validate",),
        ("run", "--dry-run"),
        ("run", "--tier", "fast"),
        ("run",),
    ):
        completed = run_entrix(fixture_root, *args)
        assert completed.returncode == 0, (
            f"{fixture_name} failed for {' '.join(args)}\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )


def test_claude_only_fixture_ci_scope_is_executable(tmp_path: Path) -> None:
    fixture_root = materialize_fixture(tmp_path, "claude-only-ci-boundary")
    completed = run_entrix(fixture_root, "run", "--scope", "ci", "--min-score", "0")
    assert completed.returncode == 0, (
        f"claude-only-ci-boundary failed for ci scope\n"
        f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
    )
