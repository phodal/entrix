"""Long-file structural analysis based on existing tree-sitter symbols."""

from __future__ import annotations

import argparse
import re
import subprocess
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


_SUPPORTED_EXTENSIONS = {".go", ".java", ".py", ".rs", ".ts", ".tsx", ".js", ".jsx"}
_CONTAINER_KINDS = {"Class", "Struct", "Trait", "Enum", "Interface"}
_COMMENT_REVIEW_COMMIT_THRESHOLD = 5


def analyze_long_files(
    repo_root: Path,
    *,
    files: list[str] | None = None,
    config_path: Path | None = None,
    base: str = "HEAD",
    use_head_ratchet: bool = True,
    comment_review_commit_threshold: int = _COMMENT_REVIEW_COMMIT_THRESHOLD,
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
            comment_review_commit_threshold=comment_review_commit_threshold,
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
    comment_review_commit_threshold: int,
) -> dict[str, Any]:
    parsed = adapter.analyze_file(relative_path)
    if parsed.get("status") != "ok":
        return {
            "filePath": relative_path,
            "status": parsed.get("status", "error"),
            "summary": parsed.get("summary", "Unable to analyze file."),
        }

    line_count = count_lines(repo_root / relative_path)
    source_lines = (repo_root / relative_path).read_text(encoding="utf-8").splitlines()
    budget_limit, budget_reason = _resolve_budget_limit(
        repo_root,
        relative_path,
        config,
        use_head_ratchet=use_head_ratchet,
    )
    classes, functions, warnings = _build_maps(
        repo_root,
        relative_path,
        parsed["symbols"],
        parsed.get("comments", []),
        source_lines,
        comment_review_commit_threshold=comment_review_commit_threshold,
    )
    commit_count = _count_file_commits(repo_root, relative_path)

    return {
        "filePath": relative_path,
        "language": parsed["language"],
        "lineCount": line_count,
        "budgetLimit": budget_limit,
        "budgetReason": budget_reason,
        "overBudget": line_count > budget_limit,
        "commitCount": commit_count,
        "classes": classes,
        "functions": functions,
        "warnings": warnings,
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


def _build_maps(
    repo_root: Path,
    relative_path: str,
    symbols: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    source_lines: list[str],
    *,
    comment_review_commit_threshold: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    containers = [
        symbol for symbol in symbols if symbol["file_path"] == relative_path and symbol["kind"] in _CONTAINER_KINDS
    ]
    methods_by_parent: dict[str, list[dict[str, Any]]] = {}
    globals_out: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    child_spans_by_parent: dict[str, list[tuple[int, int]]] = {}
    symbol_commit_counts: dict[tuple[int, int], int] = {}

    container_names = {symbol["name"] for symbol in containers}
    for symbol in symbols:
        parent_name = symbol.get("parent_name") or None
        if symbol["file_path"] != relative_path or not parent_name:
            continue
        child_spans_by_parent.setdefault(parent_name, []).append(
            (symbol["line_start"], symbol["line_end"])
        )

    for symbol in symbols:
        if symbol["file_path"] != relative_path or symbol.get("is_test"):
            continue
        if symbol["kind"] in _CONTAINER_KINDS:
            continue
        fn_map = _to_function_map(
            repo_root,
            relative_path,
            symbol,
            comments,
            source_lines,
            comment_review_commit_threshold=comment_review_commit_threshold,
            child_symbol_spans=child_spans_by_parent.get(symbol["name"], []),
            symbol_commit_counts=symbol_commit_counts,
        )
        parent_name = symbol.get("parent_name") or None
        if parent_name and parent_name in container_names:
            methods_by_parent.setdefault(parent_name, []).append(fn_map)
            warnings.extend(fn_map["warnings"])
        elif symbol["kind"] == "Function" and not parent_name:
            globals_out.append(fn_map)
            warnings.extend(fn_map["warnings"])

    classes = []
    for container in sorted(containers, key=lambda item: (item["line_start"], item["qualified_name"])):
        methods = sorted(
            methods_by_parent.get(container["name"], []),
            key=lambda item: (item["startLine"], item["qualifiedName"]),
        )
        container_comments = _comments_for_symbol(
            container["line_start"],
            container["line_end"],
            comments,
            source_lines,
            child_symbol_spans=child_spans_by_parent.get(container["name"], []),
            include_inner=False,
        )
        container_commit_count = _symbol_commit_count(
            repo_root,
            relative_path,
            container["line_start"],
            container["line_end"],
            cache=symbol_commit_counts,
        )
        container_warnings = _comment_review_warnings(
            relative_path,
            container["qualified_name"],
            container["name"],
            "class",
            container["line_start"],
            container["line_end"],
            container_commit_count,
            container_comments,
            threshold=comment_review_commit_threshold,
        )
        classes.append(
            {
                "name": container["name"],
                "qualifiedName": container["qualified_name"],
                "filePath": relative_path,
                "startLine": container["line_start"],
                "endLine": container["line_end"],
                "lineCount": container["line_end"] - container["line_start"] + 1,
                "commitCount": container_commit_count,
                "commentCount": len(container_comments),
                "comments": container_comments,
                "methodCount": len(methods),
                "methods": methods,
                "warnings": container_warnings,
            }
        )
        warnings.extend(container_warnings)

    functions = sorted(
        globals_out,
        key=lambda item: (item["startLine"], item["qualifiedName"]),
    )
    warnings = sorted(
        warnings,
        key=lambda item: (item["startLine"], item["name"], item["symbolKind"]),
    )
    return classes, functions, warnings


def _to_function_map(
    repo_root: Path,
    relative_path: str,
    symbol: dict[str, Any],
    comments: list[dict[str, Any]],
    source_lines: list[str],
    *,
    comment_review_commit_threshold: int,
    child_symbol_spans: list[tuple[int, int]],
    symbol_commit_counts: dict[tuple[int, int], int],
) -> dict[str, Any]:
    parent_name = symbol.get("parent_name") or None
    kind = "method" if parent_name else "function"
    symbol_comments = _comments_for_symbol(
        symbol["line_start"],
        symbol["line_end"],
        comments,
        source_lines,
        child_symbol_spans=child_symbol_spans,
    )
    commit_count = _symbol_commit_count(
        repo_root,
        relative_path,
        symbol["line_start"],
        symbol["line_end"],
        cache=symbol_commit_counts,
    )
    warnings = _comment_review_warnings(
        relative_path,
        symbol["qualified_name"],
        symbol["name"],
        kind,
        symbol["line_start"],
        symbol["line_end"],
        commit_count,
        symbol_comments,
        threshold=comment_review_commit_threshold,
    )
    return {
        "name": symbol["name"],
        "qualifiedName": symbol["qualified_name"],
        "filePath": symbol["file_path"],
        "startLine": symbol["line_start"],
        "endLine": symbol["line_end"],
        "lineCount": symbol["line_end"] - symbol["line_start"] + 1,
        "commitCount": commit_count,
        "commentCount": len(symbol_comments),
        "comments": symbol_comments,
        "kind": kind,
        "parentClassName": parent_name,
        "warnings": warnings,
    }


def _comments_for_symbol(
    start_line: int,
    end_line: int,
    comments: list[dict[str, Any]],
    source_lines: list[str],
    *,
    child_symbol_spans: list[tuple[int, int]] | None = None,
    include_inner: bool = True,
) -> list[dict[str, Any]]:
    child_symbol_spans = child_symbol_spans or []
    attached = _leading_comments_for_symbol(start_line, comments, source_lines)
    attached_keys = {(comment["startLine"], comment["endLine"]) for comment in attached}
    if not include_inner:
        return sorted(attached, key=lambda item: (item["startLine"], item["endLine"]))
    for comment in comments:
        if comment["startLine"] < start_line or comment["endLine"] > end_line:
            continue
        if _inside_child_symbol(comment, child_symbol_spans):
            continue
        key = (comment["startLine"], comment["endLine"])
        if key in attached_keys:
            continue
        attached.append(_normalize_comment(comment, placement="inner"))
        attached_keys.add(key)
    return sorted(attached, key=lambda item: (item["startLine"], item["endLine"]))


def _leading_comments_for_symbol(
    start_line: int,
    comments: list[dict[str, Any]],
    source_lines: list[str],
) -> list[dict[str, Any]]:
    comments_by_end: dict[int, list[dict[str, Any]]] = {}
    for comment in comments:
        comments_by_end.setdefault(comment["endLine"], []).append(comment)

    attached: list[dict[str, Any]] = []
    cursor = start_line - 1
    while cursor > 0 and not source_lines[cursor - 1].strip():
        cursor -= 1

    while cursor > 0:
        candidates = comments_by_end.get(cursor, [])
        if not candidates:
            break
        comment = sorted(candidates, key=lambda item: item["startLine"])[-1]
        attached.append(_normalize_comment(comment, placement="leading"))
        cursor = comment["startLine"] - 1
        while cursor > 0 and not source_lines[cursor - 1].strip():
            cursor -= 1
    attached.reverse()
    return attached


def _inside_child_symbol(
    comment: dict[str, Any],
    child_symbol_spans: list[tuple[int, int]],
) -> bool:
    return any(
        child_start <= comment["startLine"] and comment["endLine"] <= child_end
        for child_start, child_end in child_symbol_spans
    )


def _normalize_comment(comment: dict[str, Any], *, placement: str) -> dict[str, Any]:
    text = comment.get("text", "").strip()
    preview = re.sub(r"\s+", " ", text)
    if len(preview) > 120:
        preview = f"{preview[:117]}..."
    return {
        "startLine": comment["startLine"],
        "endLine": comment["endLine"],
        "lineCount": comment["lineCount"],
        "placement": placement,
        "preview": preview,
    }


def _symbol_commit_count(
    repo_root: Path,
    relative_path: str,
    start_line: int,
    end_line: int,
    *,
    cache: dict[tuple[int, int], int],
) -> int:
    key = (start_line, end_line)
    if key not in cache:
        cache[key] = _count_symbol_commits(repo_root, relative_path, start_line, end_line)
    return cache[key]


def _comment_review_warnings(
    relative_path: str,
    qualified_name: str,
    name: str,
    symbol_kind: str,
    start_line: int,
    end_line: int,
    commit_count: int,
    comments: list[dict[str, Any]],
    *,
    threshold: int,
) -> list[dict[str, Any]]:
    if commit_count < threshold or not comments:
        return []
    return [
        {
            "code": "comment_review_required",
            "summary": (
                f"{symbol_kind} '{name}' changed in {commit_count} commit(s) and still has "
                f"{len(comments)} comment(s); review comments for stale guidance."
            ),
            "filePath": relative_path,
            "qualifiedName": qualified_name,
            "name": name,
            "symbolKind": symbol_kind,
            "startLine": start_line,
            "endLine": end_line,
            "lineCount": end_line - start_line + 1,
            "commitCount": commit_count,
            "commentCount": len(comments),
            "commentSpans": [
                {
                    "startLine": comment["startLine"],
                    "endLine": comment["endLine"],
                    "placement": comment["placement"],
                }
                for comment in comments
            ],
        }
    ]


def _count_file_commits(repo_root: Path, relative_path: str) -> int:
    result = subprocess.run(
        ["git", "log", "--follow", "--format=%H", "--", relative_path],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return 0
    return sum(1 for line in result.stdout.splitlines() if line.strip())


def _count_symbol_commits(
    repo_root: Path,
    relative_path: str,
    start_line: int,
    end_line: int,
) -> int:
    result = subprocess.run(
        [
            "git",
            "log",
            "-L",
            f"{start_line},{end_line}:{relative_path}",
            "--format=%H",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return 0
    return sum(
        1
        for line in result.stdout.splitlines()
        if re.fullmatch(r"[0-9a-f]{40}", line.strip())
    )
