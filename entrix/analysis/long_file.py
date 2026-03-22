"""Long-file structural analysis based on existing tree-sitter symbols."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from entrix.file_budgets import (
    _resolve_paths,
    count_head_lines,
    count_lines,
    is_tracked_source_file,
    load_config,
    normalize_repo_path,
    resolve_budget,
)
from entrix.structure.builtin import BuiltinGraphAdapter


_SUPPORTED_EXTENSIONS = {".py", ".rs", ".ts", ".tsx", ".js", ".jsx"}
_CONTAINER_KINDS = {"Class", "Struct", "Trait", "Enum", "Interface"}


def analyze_long_files(
    repo_root: Path,
    *,
    files: list[str] | None = None,
    config_path: Path | None = None,
    base: str = "HEAD",
    use_head_ratchet: bool = True,
) -> dict[str, Any]:
    """Return ClassMap/FunctionMap payloads for oversized or explicit files."""
    repo_root = repo_root.resolve()
    config_path = (config_path or repo_root / "tools" / "entrix" / "file_budgets.json").resolve()
    config = load_config(config_path)
    target_files = _resolve_target_files(repo_root, config, files=files, base=base)

    try:
        adapter = BuiltinGraphAdapter(repo_root)
    except ImportError:
        return {
            "status": "unavailable",
            "summary": "long-file analysis requires tree-sitter-language-pack",
            "files": [],
        }
    analyses = [
        _analyze_single_file(
            adapter,
            repo_root,
            relative_path,
            config,
            use_head_ratchet=use_head_ratchet,
        )
        for relative_path in target_files
    ]

    return {
        "status": "ok",
        "base": base,
        "files": analyses,
    }


def _resolve_target_files(
    repo_root: Path,
    config,
    *,
    files: list[str] | None,
    base: str,
) -> list[str]:
    if files:
        normalized = []
        for raw_path in files:
            path = Path(raw_path)
            if not path.is_absolute():
                path = repo_root / path
            if not path.exists() or not path.is_file():
                continue
            if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
                continue
            normalized.append(normalize_repo_path(path, repo_root))
        return sorted(set(normalized))

    file_budget_args = argparse.Namespace(
        changed_only=False,
        staged_only=False,
        base=base,
        overrides_only=False,
        paths=[],
    )
    relative_paths = _resolve_paths(file_budget_args, repo_root, config)
    oversized = []
    for relative_path in sorted(set(relative_paths)):
        if not is_tracked_source_file(relative_path, config):
            continue
        file_path = repo_root / relative_path
        if not file_path.is_file():
            continue
        budget_limit, _ = _resolve_budget_limit(
            repo_root,
            relative_path,
            config,
            use_head_ratchet=True,
        )
        line_count = count_lines(file_path)
        if line_count > budget_limit:
            oversized.append(relative_path)
    return oversized


def _analyze_single_file(
    adapter: BuiltinGraphAdapter,
    repo_root: Path,
    relative_path: str,
    config,
    *,
    use_head_ratchet: bool,
) -> dict[str, Any]:
    parsed = adapter.analyze_file(relative_path)
    if parsed.get("status") != "ok":
        return {
            "filePath": relative_path,
            "status": parsed.get("status", "error"),
            "summary": parsed.get("summary", "Unable to analyze file."),
        }

    line_count = count_lines(repo_root / relative_path)
    budget_limit, budget_reason = _resolve_budget_limit(
        repo_root,
        relative_path,
        config,
        use_head_ratchet=use_head_ratchet,
    )
    classes, functions = _build_maps(relative_path, parsed["symbols"])

    return {
        "filePath": relative_path,
        "language": parsed["language"],
        "lineCount": line_count,
        "budgetLimit": budget_limit,
        "budgetReason": budget_reason,
        "overBudget": line_count > budget_limit,
        "classes": classes,
        "functions": functions,
    }


def _resolve_budget_limit(
    repo_root: Path,
    relative_path: str,
    config,
    *,
    use_head_ratchet: bool,
) -> tuple[int, str]:
    configured_limit, reason = resolve_budget(relative_path, config)
    max_lines = configured_limit
    if use_head_ratchet:
        baseline_lines = count_head_lines(repo_root, relative_path)
        if baseline_lines is not None:
            max_lines = max(max_lines, baseline_lines)
            if baseline_lines > configured_limit and not reason:
                reason = f"legacy hotspot frozen at HEAD baseline ({baseline_lines} lines)"
    return max_lines, reason


def _build_maps(relative_path: str, symbols: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    containers = [
        symbol for symbol in symbols if symbol["file_path"] == relative_path and symbol["kind"] in _CONTAINER_KINDS
    ]
    methods_by_parent: dict[str, list[dict[str, Any]]] = {}
    globals_out: list[dict[str, Any]] = []

    container_names = {symbol["name"] for symbol in containers}
    for symbol in symbols:
        if symbol["file_path"] != relative_path or symbol.get("is_test"):
            continue
        if symbol["kind"] in _CONTAINER_KINDS:
            continue
        fn_map = _to_function_map(symbol)
        parent_name = symbol.get("parent_name") or None
        if parent_name and parent_name in container_names:
            methods_by_parent.setdefault(parent_name, []).append(fn_map)
        elif symbol["kind"] == "Function" and not parent_name:
            globals_out.append(fn_map)

    classes = []
    for container in sorted(containers, key=lambda item: (item["line_start"], item["qualified_name"])):
        methods = sorted(
            methods_by_parent.get(container["name"], []),
            key=lambda item: (item["startLine"], item["qualifiedName"]),
        )
        classes.append(
            {
                "name": container["name"],
                "qualifiedName": container["qualified_name"],
                "filePath": relative_path,
                "startLine": container["line_start"],
                "endLine": container["line_end"],
                "lineCount": container["line_end"] - container["line_start"] + 1,
                "methodCount": len(methods),
                "methods": methods,
            }
        )

    functions = sorted(
        globals_out,
        key=lambda item: (item["startLine"], item["qualifiedName"]),
    )
    return classes, functions


def _to_function_map(symbol: dict[str, Any]) -> dict[str, Any]:
    parent_name = symbol.get("parent_name") or None
    kind = "method" if parent_name else "function"
    return {
        "name": symbol["name"],
        "qualifiedName": symbol["qualified_name"],
        "filePath": symbol["file_path"],
        "startLine": symbol["line_start"],
        "endLine": symbol["line_end"],
        "lineCount": symbol["line_end"] - symbol["line_start"] + 1,
        "kind": kind,
        "parentClassName": parent_name,
    }
