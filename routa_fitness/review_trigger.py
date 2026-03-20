"""Review-trigger rules for human escalation on risky changes."""

from __future__ import annotations

import fnmatch
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class DiffStats:
    """Aggregate diff statistics for review-trigger evaluation."""

    file_count: int = 0
    added_lines: int = 0
    deleted_lines: int = 0


@dataclass(frozen=True)
class ReviewTriggerRule:
    """A single review-trigger rule."""

    name: str
    type: str
    severity: str = "medium"
    action: str = "require_human_review"
    paths: tuple[str, ...] = ()
    max_files: int | None = None
    max_added_lines: int | None = None
    max_deleted_lines: int | None = None


@dataclass(frozen=True)
class TriggerMatch:
    """A triggered rule with human-readable reasons."""

    name: str
    severity: str
    action: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviewTriggerReport:
    """Structured result of review-trigger evaluation."""

    human_review_required: bool
    base: str
    changed_files: tuple[str, ...] = ()
    diff_stats: DiffStats = field(default_factory=DiffStats)
    triggers: tuple[TriggerMatch, ...] = ()

    def to_dict(self) -> dict:
        """Serialize report to a JSON-friendly dictionary."""
        data = asdict(self)
        data["changed_files"] = list(self.changed_files)
        data["triggers"] = [
            {
                "name": trigger.name,
                "severity": trigger.severity,
                "action": trigger.action,
                "reasons": list(trigger.reasons),
            }
            for trigger in self.triggers
        ]
        return data


def load_review_triggers(config_path: Path) -> list[ReviewTriggerRule]:
    """Load review-trigger rules from YAML."""
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    rules: list[ReviewTriggerRule] = []
    for entry in raw.get("review_triggers", []):
        rules.append(
            ReviewTriggerRule(
                name=entry.get("name", "unknown"),
                type=entry.get("type", "unknown"),
                severity=entry.get("severity", "medium"),
                action=entry.get("action", "require_human_review"),
                paths=tuple(entry.get("paths", [])),
                max_files=entry.get("max_files"),
                max_added_lines=entry.get("max_added_lines"),
                max_deleted_lines=entry.get("max_deleted_lines"),
            )
        )
    return rules


def collect_changed_files(repo_root: Path, base: str) -> list[str]:
    """Collect changed and untracked files relative to a git base."""
    files: list[str] = []
    commands = [
        ["git", "diff", "--name-only", "--diff-filter=ACMR", base],
        ["git", "diff", "--name-only", "--diff-filter=ACMR"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    for command in commands:
        result = subprocess.run(
            command,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        files.extend(line.strip() for line in result.stdout.splitlines() if line.strip())

    seen: set[str] = set()
    deduped: list[str] = []
    for file_path in files:
        if file_path not in seen:
            seen.add(file_path)
            deduped.append(file_path)
    return deduped


def collect_diff_stats(repo_root: Path, base: str) -> DiffStats:
    """Collect aggregate diff stats relative to a git base."""
    result = subprocess.run(
        ["git", "diff", "--numstat", "--diff-filter=ACMR", base],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    added_lines = 0
    deleted_lines = 0
    file_count = 0
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, deleted, _path = parts
        if added == "-" or deleted == "-":
            continue
        file_count += 1
        added_lines += int(added)
        deleted_lines += int(deleted)
    return DiffStats(file_count=file_count, added_lines=added_lines, deleted_lines=deleted_lines)


def evaluate_review_triggers(
    rules: list[ReviewTriggerRule],
    changed_files: list[str],
    diff_stats: DiffStats,
    *,
    base: str,
) -> ReviewTriggerReport:
    """Evaluate review-trigger rules for a diff."""
    triggers: list[TriggerMatch] = []
    for rule in rules:
        if rule.type == "changed_paths":
            reasons = tuple(
                f"changed path: {file_path}"
                for file_path in changed_files
                if any(fnmatch.fnmatch(file_path, pattern) for pattern in rule.paths)
            )
            if reasons:
                triggers.append(
                    TriggerMatch(
                        name=rule.name,
                        severity=rule.severity,
                        action=rule.action,
                        reasons=reasons,
                    )
                )
        elif rule.type == "diff_size":
            reasons: list[str] = []
            if rule.max_files is not None and diff_stats.file_count > rule.max_files:
                reasons.append(
                    f"diff touched {diff_stats.file_count} files (threshold: {rule.max_files})"
                )
            if (
                rule.max_added_lines is not None
                and diff_stats.added_lines > rule.max_added_lines
            ):
                reasons.append(
                    f"diff added {diff_stats.added_lines} lines (threshold: {rule.max_added_lines})"
                )
            if (
                rule.max_deleted_lines is not None
                and diff_stats.deleted_lines > rule.max_deleted_lines
            ):
                reasons.append(
                    "diff deleted "
                    f"{diff_stats.deleted_lines} lines (threshold: {rule.max_deleted_lines})"
                )
            if reasons:
                triggers.append(
                    TriggerMatch(
                        name=rule.name,
                        severity=rule.severity,
                        action=rule.action,
                        reasons=tuple(reasons),
                    )
                )

    return ReviewTriggerReport(
        human_review_required=bool(triggers),
        base=base,
        changed_files=tuple(changed_files),
        diff_stats=diff_stats,
        triggers=tuple(triggers),
    )

