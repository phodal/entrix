"""Tests for long-file structural analysis."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from entrix.analysis.long_file import analyze_long_files


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("tree_sitter_language_pack") is None,
    reason="tree-sitter-language-pack is not installed",
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_budget_config(path: Path, *, max_ts: int = 1000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "default_max_lines": 1000,
                "include_roots": ["src", "apps", "crates"],
                "extensions": [".go", ".java", ".py", ".rs", ".ts", ".tsx"],
                "extension_max_lines": {
                    ".go": 1000,
                    ".java": 1000,
                    ".py": 1000,
                    ".ts": max_ts,
                    ".tsx": 1000,
                    ".rs": 800,
                },
                "excluded_parts": ["/node_modules/", "/target/", "/.next/", "/_next/", "/bundled/"],
                "overrides": [],
            }
        ),
        encoding="utf-8",
    )


def test_analyze_long_file_explicit_typescript_file(tmp_path: Path):
    _write_budget_config(tmp_path / "tools" / "entrix" / "file_budgets.json")
    _write(
        tmp_path / "src" / "runner.ts",
        "class Runner {\n"
        "  run() {\n"
        "    return helper();\n"
        "  }\n"
        "}\n"
        "\n"
        "function helper() {\n"
        "  return 1;\n"
        "}\n",
    )

    result = analyze_long_files(tmp_path, files=["src/runner.ts"])

    assert result["status"] == "ok"
    assert len(result["files"]) == 1
    analysis = result["files"][0]
    assert analysis["filePath"] == "src/runner.ts"
    assert analysis["language"] == "typescript"
    assert analysis["lineCount"] == 9
    assert analysis["budgetLimit"] == 1000
    assert analysis["overBudget"] is False
    assert analysis["commitCount"] == 0
    assert analysis["classes"][0]["name"] == "Runner"
    assert analysis["classes"][0]["methodCount"] == 1
    assert analysis["classes"][0]["methods"][0]["name"] == "run"
    assert analysis["classes"][0]["methods"][0]["kind"] == "method"
    assert analysis["functions"][0]["name"] == "helper"
    assert analysis["functions"][0]["kind"] == "function"


def test_analyze_long_file_explicit_python_file(tmp_path: Path):
    _write_budget_config(tmp_path / "tools" / "entrix" / "file_budgets.json")
    _write(
        tmp_path / "src" / "service.py",
        "class Service:\n"
        "    def run(self):\n"
        "        return helper()\n"
        "\n"
        "\n"
        "def helper():\n"
        "    return 1\n",
    )

    result = analyze_long_files(tmp_path, files=["src/service.py"])

    analysis = result["files"][0]
    assert analysis["language"] == "python"
    assert analysis["classes"][0]["name"] == "Service"
    assert analysis["classes"][0]["methods"][0]["name"] == "run"
    assert analysis["functions"][0]["name"] == "helper"


def test_analyze_long_file_defaults_to_oversized_files(tmp_path: Path):
    _write_budget_config(tmp_path / "tools" / "entrix" / "file_budgets.json", max_ts=3)
    _write(
        tmp_path / "src" / "large.ts",
        "function a() {\n"
        "  return 1;\n"
        "}\n"
        "function b() {\n"
        "  return 2;\n"
        "}\n",
    )
    _write(
        tmp_path / "src" / "small.ts",
        "function ok() {\n"
        "  return 1;\n"
        "}\n",
    )

    result = analyze_long_files(tmp_path)

    assert [item["filePath"] for item in result["files"]] == ["src/large.ts"]
    assert result["files"][0]["overBudget"] is True
    assert [fn["name"] for fn in result["files"][0]["functions"]] == ["a", "b"]


def test_analyze_long_file_includes_commit_count(monkeypatch, tmp_path: Path):
    _write_budget_config(tmp_path / "tools" / "entrix" / "file_budgets.json")
    _write(
        tmp_path / "src" / "runner.ts",
        "function helper() {\n"
        "  return 1;\n"
        "}\n",
    )

    monkeypatch.setattr(
        "entrix.analysis.long_file._count_file_commits",
        lambda repo_root, relative_path: 7,
    )

    result = analyze_long_files(tmp_path, files=["src/runner.ts"])

    assert result["files"][0]["commitCount"] == 7


@pytest.mark.parametrize(
    ("relative_path", "content", "selector"),
    [
        (
            "src/service.ts",
            "class Service {\n"
            "  // review this behavior carefully\n"
            "  run() {\n"
            "    return helper();\n"
            "  }\n"
            "}\n"
            "\n"
            "function helper() {\n"
            "  return 1;\n"
            "}\n",
            lambda analysis: analysis["classes"][0]["methods"][0],
        ),
        (
            "src/lib.rs",
            "// helper comment\n"
            "fn helper() -> i32 {\n"
            "    1\n"
            "}\n",
            lambda analysis: analysis["functions"][0],
        ),
        (
            "src/main.go",
            "package demo\n"
            "\n"
            "// helper comment\n"
            "func Helper() int {\n"
            "    return 1\n"
            "}\n",
            lambda analysis: analysis["functions"][0],
        ),
        (
            "src/Runner.java",
            "class Runner {\n"
            "  // helper comment\n"
            "  int run() {\n"
            "    return helper();\n"
            "  }\n"
            "\n"
            "  int helper() {\n"
            "    return 1;\n"
            "  }\n"
            "}\n",
            lambda analysis: analysis["classes"][0]["methods"][0],
        ),
        (
            "src/service.py",
            "# helper comment\n"
            "def helper():\n"
            "    return 1\n",
            lambda analysis: analysis["functions"][0],
        ),
    ],
)
def test_analyze_long_file_warns_on_commented_high_churn_symbols(
    monkeypatch,
    tmp_path: Path,
    relative_path: str,
    content: str,
    selector,
):
    _write_budget_config(tmp_path / "tools" / "entrix" / "file_budgets.json")
    _write(tmp_path / relative_path, content)

    monkeypatch.setattr(
        "entrix.analysis.long_file._count_file_commits",
        lambda repo_root, file_path: 3,
    )
    monkeypatch.setattr(
        "entrix.analysis.long_file._count_symbol_commits",
        lambda repo_root, file_path, start_line, end_line: 8,
    )

    result = analyze_long_files(tmp_path, files=[relative_path])

    analysis = result["files"][0]
    symbol = selector(analysis)
    assert symbol["commentCount"] >= 1
    assert symbol["commitCount"] == 8
    assert symbol["warnings"][0]["code"] == "comment_review_required"
    assert analysis["warnings"]


def test_analyze_long_file_does_not_warn_below_threshold(monkeypatch, tmp_path: Path):
    _write_budget_config(tmp_path / "tools" / "entrix" / "file_budgets.json")
    _write(
        tmp_path / "src" / "runner.ts",
        "// helper comment\n"
        "function helper() {\n"
        "  return 1;\n"
        "}\n",
    )

    monkeypatch.setattr(
        "entrix.analysis.long_file._count_file_commits",
        lambda repo_root, relative_path: 1,
    )
    monkeypatch.setattr(
        "entrix.analysis.long_file._count_symbol_commits",
        lambda repo_root, relative_path, start_line, end_line: 2,
    )

    result = analyze_long_files(tmp_path, files=["src/runner.ts"])

    analysis = result["files"][0]
    assert analysis["functions"][0]["commentCount"] == 1
    assert analysis["functions"][0]["warnings"] == []
    assert analysis["warnings"] == []
