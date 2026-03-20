"""File size budget enforcement with legacy hotspot ratcheting."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BudgetOverride:
    """Path-specific file line budget."""

    path: str
    max_lines: int
    reason: str = ""


@dataclass(frozen=True)
class FileBudgetConfig:
    """Configuration for file line budgets."""

    default_max_lines: int
    include_roots: tuple[str, ...]
    extensions: tuple[str, ...]
    extension_max_lines: dict[str, int]
    excluded_parts: tuple[str, ...]
    overrides: tuple[BudgetOverride, ...]


@dataclass(frozen=True)
class FileBudgetViolation:
    """A file that exceeded its configured size budget."""

    path: str
    line_count: int
    max_lines: int
    reason: str = ""


def load_config(config_path: Path) -> FileBudgetConfig:
    """Load file budget configuration from JSON."""
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    overrides = tuple(
        BudgetOverride(
            path=entry["path"],
            max_lines=int(entry["max_lines"]),
            reason=entry.get("reason", ""),
        )
        for entry in raw.get("overrides", [])
    )
    return FileBudgetConfig(
        default_max_lines=int(raw["default_max_lines"]),
        include_roots=tuple(raw.get("include_roots", [])),
        extensions=tuple(raw.get("extensions", [])),
        extension_max_lines={
            str(ext): int(limit)
            for ext, limit in raw.get("extension_max_lines", {}).items()
        },
        excluded_parts=tuple(raw.get("excluded_parts", [])),
        overrides=overrides,
    )


def normalize_repo_path(path: Path, repo_root: Path) -> str:
    """Return a stable POSIX-style relative path."""
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def is_tracked_source_file(relative_path: str, config: FileBudgetConfig) -> bool:
    """Check whether a path is subject to file budget enforcement."""
    if not any(
        relative_path == root or relative_path.startswith(f"{root}/")
        for root in config.include_roots
    ):
        return False
    if not any(relative_path.endswith(ext) for ext in config.extensions):
        return False
    return not any(part in relative_path for part in config.excluded_parts)


def resolve_budget(relative_path: str, config: FileBudgetConfig) -> tuple[int, str]:
    """Resolve the budget for a file path."""
    for override in config.overrides:
        if relative_path == override.path:
            return override.max_lines, override.reason
    extension = Path(relative_path).suffix
    if extension in config.extension_max_lines:
        return config.extension_max_lines[extension], ""
    return config.default_max_lines, ""


def count_lines(file_path: Path) -> int:
    """Count lines in a UTF-8 text file."""
    with file_path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def count_head_lines(repo_root: Path, relative_path: str) -> int | None:
    """Count lines for a file as stored in HEAD, or return None if it is untracked there."""
    result = subprocess.run(
        ["git", "show", f"HEAD:{relative_path}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return len(result.stdout.splitlines())


def list_changed_files(repo_root: Path, base: str = "HEAD") -> list[str]:
    """List changed files from git."""
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMR",
            base,
            "--",
            "src",
            "apps",
            "crates",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff failed")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def evaluate_paths(
    repo_root: Path,
    relative_paths: list[str],
    config: FileBudgetConfig,
) -> list[FileBudgetViolation]:
    """Evaluate file size budgets for the given relative paths."""
    violations: list[FileBudgetViolation] = []
    for relative_path in sorted(set(relative_paths)):
        if not is_tracked_source_file(relative_path, config):
            continue

        file_path = repo_root / relative_path
        if not file_path.is_file():
            continue

        configured_max_lines, reason = resolve_budget(relative_path, config)
        baseline_lines = count_head_lines(repo_root, relative_path)
        max_lines = configured_max_lines
        if baseline_lines is not None:
            max_lines = max(max_lines, baseline_lines)
            if baseline_lines > configured_max_lines and not reason:
                reason = f"legacy hotspot frozen at HEAD baseline ({baseline_lines} lines)"
        line_count = count_lines(file_path)
        if line_count > max_lines:
            violations.append(
                FileBudgetViolation(
                    path=relative_path,
                    line_count=line_count,
                    max_lines=max_lines,
                    reason=reason,
                )
            )

    return violations


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check file size budgets.")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to a JSON file with file size budget configuration.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root to evaluate against.",
    )
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="Only evaluate files changed against HEAD.",
    )
    parser.add_argument(
        "--base",
        default="HEAD",
        help="Git base ref used by --changed-only.",
    )
    parser.add_argument(
        "--overrides-only",
        action="store_true",
        help="Only evaluate paths declared in config overrides.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Explicit relative paths to evaluate when not using --changed-only.",
    )
    return parser.parse_args(argv)


def _resolve_paths(args: argparse.Namespace, repo_root: Path, config: FileBudgetConfig) -> list[str]:
    if args.changed_only:
        paths = list_changed_files(repo_root, args.base)
        if args.overrides_only:
            override_paths = {override.path for override in config.overrides}
            return [path for path in paths if path in override_paths]
        return paths
    if args.overrides_only:
        return [override.path for override in config.overrides]
    if args.paths:
        return args.paths

    collected: list[str] = []
    for root in config.include_roots:
        base = repo_root / root
        if not base.exists():
            continue
        for file_path in base.rglob("*"):
            if file_path.is_file():
                collected.append(normalize_repo_path(file_path, repo_root))
    return collected


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = _parse_args(argv or sys.argv[1:])
    repo_root = Path(args.repo_root).resolve()
    config = load_config(Path(args.config))
    relative_paths = _resolve_paths(args, repo_root, config)
    violations = evaluate_paths(repo_root, relative_paths, config)

    checked_count = sum(1 for path in set(relative_paths) if is_tracked_source_file(path, config))
    print(f"file_budget_checked: {checked_count}")
    print(f"file_budget_violations: {len(violations)}")
    for violation in violations:
        reason = f" | {violation.reason}" if violation.reason else ""
        print(
            f"{violation.path}: {violation.line_count} lines > "
            f"budget {violation.max_lines}{reason}"
        )

    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
