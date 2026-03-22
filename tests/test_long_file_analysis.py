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
                "extensions": [".ts", ".tsx", ".rs"],
                "extension_max_lines": {
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
