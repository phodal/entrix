"""Tests for routa_fitness.file_budgets."""

from __future__ import annotations

import argparse
import json

from routa_fitness.file_budgets import (
    _resolve_paths,
    BudgetOverride,
    FileBudgetConfig,
    count_head_lines,
    evaluate_paths,
    is_tracked_source_file,
    load_config,
    resolve_budget,
)


def make_config() -> FileBudgetConfig:
    return FileBudgetConfig(
        default_max_lines=1000,
        include_roots=("src", "apps", "crates"),
        extensions=(".ts", ".tsx", ".rs"),
        extension_max_lines={".rs": 800, ".ts": 1000, ".tsx": 1000},
        excluded_parts=("/node_modules/", "/target/", "/.next/", "/_next/", "/bundled/"),
        overrides=(
            BudgetOverride(
                path="crates/routa-server/src/application/tasks.rs",
                max_lines=1200,
                reason="legacy hotspot",
            ),
        ),
    )


def test_load_config(tmp_path):
    config_path = tmp_path / "file_budgets.json"
    config_path.write_text(
        json.dumps(
            {
                "default_max_lines": 1000,
                "include_roots": ["src", "apps", "crates"],
                "extensions": [".ts", ".tsx", ".rs"],
                "extension_max_lines": {".rs": 800, ".ts": 1000, ".tsx": 1000},
                "excluded_parts": ["/target/"],
                "overrides": [
                    {
                        "path": "crates/routa-server/src/application/tasks.rs",
                        "max_lines": 1200,
                        "reason": "legacy hotspot",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.default_max_lines == 1000
    assert config.include_roots == ("src", "apps", "crates")
    assert config.extension_max_lines[".rs"] == 800
    assert config.overrides[0].path == "crates/routa-server/src/application/tasks.rs"
    assert config.overrides[0].max_lines == 1200


def test_is_tracked_source_file():
    config = make_config()

    assert is_tracked_source_file("crates/foo/src/lib.rs", config) is True
    assert is_tracked_source_file("docs/fitness/code-quality.md", config) is False
    assert is_tracked_source_file("crates/foo/target/generated.rs", config) is False


def test_resolve_budget_prefers_override():
    config = make_config()

    assert resolve_budget("src/app/page.tsx", config) == (1000, "")
    assert resolve_budget("crates/routa-server/src/application/tasks.rs", config) == (
        1200,
        "legacy hotspot",
    )
    assert resolve_budget("crates/routa-cli/src/commands/review/security.rs", config) == (
        800,
        "",
    )


def test_evaluate_paths_applies_default_budget(tmp_path):
    repo_root = tmp_path
    target = repo_root / "src" / "app.ts"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("line\n" * 1001, encoding="utf-8")

    violations = evaluate_paths(repo_root, ["src/app.ts"], make_config())

    assert len(violations) == 1
    assert violations[0].path == "src/app.ts"
    assert violations[0].max_lines == 1000


def test_evaluate_paths_allows_legacy_hotspot_within_override(tmp_path):
    repo_root = tmp_path
    target = repo_root / "crates" / "routa-server" / "src" / "application" / "tasks.rs"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("line\n" * 1200, encoding="utf-8")

    violations = evaluate_paths(
        repo_root,
        ["crates/routa-server/src/application/tasks.rs"],
        make_config(),
    )

    assert violations == []


def test_evaluate_paths_blocks_legacy_hotspot_growth(tmp_path):
    repo_root = tmp_path
    target = repo_root / "crates" / "routa-server" / "src" / "application" / "tasks.rs"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("line\n" * 1201, encoding="utf-8")

    violations = evaluate_paths(
        repo_root,
        ["crates/routa-server/src/application/tasks.rs"],
        make_config(),
    )

    assert len(violations) == 1
    assert violations[0].reason == "legacy hotspot"


def test_count_head_lines_returns_none_for_untracked_file(tmp_path):
    repo_root = tmp_path
    (repo_root / "src").mkdir(parents=True, exist_ok=True)
    (repo_root / "src" / "app.ts").write_text("line\n", encoding="utf-8")

    assert count_head_lines(repo_root, "src/app.ts") is None


def test_evaluate_paths_uses_head_baseline_ratchet(tmp_path, monkeypatch):
    repo_root = tmp_path
    target = repo_root / "crates" / "routa-server" / "src" / "api" / "tasks.rs"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("line\n" * 1201, encoding="utf-8")

    monkeypatch.setattr(
        "routa_fitness.file_budgets.count_head_lines",
        lambda *_args, **_kwargs: 1200,
    )
    violations = evaluate_paths(
        repo_root,
        ["crates/routa-server/src/api/tasks.rs"],
        make_config(),
    )

    assert len(violations) == 1
    assert violations[0].max_lines == 1200
    assert "HEAD baseline" in violations[0].reason


def test_evaluate_paths_allows_changes_within_head_baseline(tmp_path, monkeypatch):
    repo_root = tmp_path
    target = repo_root / "crates" / "routa-server" / "src" / "api" / "tasks.rs"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("line\n" * 1199, encoding="utf-8")

    monkeypatch.setattr(
        "routa_fitness.file_budgets.count_head_lines",
        lambda *_args, **_kwargs: 1200,
    )
    violations = evaluate_paths(
        repo_root,
        ["crates/routa-server/src/api/tasks.rs"],
        make_config(),
    )

    assert violations == []


def test_resolve_paths_filters_to_overrides_when_requested(tmp_path, monkeypatch):
    repo_root = tmp_path
    args = argparse.Namespace(
        config="unused",
        repo_root=".",
        changed_only=True,
        base="HEAD~2",
        overrides_only=True,
        paths=[],
    )
    monkeypatch.setattr(
        "routa_fitness.file_budgets.list_changed_files",
        lambda *_args, **_kwargs: [
            "crates/routa-server/src/application/tasks.rs",
            "src/app.ts",
        ],
    )

    resolved = _resolve_paths(args, repo_root, make_config())

    assert resolved == ["crates/routa-server/src/application/tasks.rs"]


def test_resolve_paths_passes_base_to_list_changed_files(tmp_path, monkeypatch):
    repo_root = tmp_path
    captured = {"base": None}
    args = argparse.Namespace(
        config="unused",
        repo_root=".",
        changed_only=True,
        base="HEAD~5",
        overrides_only=False,
        paths=[],
    )

    def _mock_list_changed_files(_repo_root, base):
        captured["base"] = base
        return ["src/app.ts"]

    monkeypatch.setattr("routa_fitness.file_budgets.list_changed_files", _mock_list_changed_files)

    resolved = _resolve_paths(args, repo_root, make_config())

    assert resolved == ["src/app.ts"]
    assert captured["base"] == "HEAD~5"
