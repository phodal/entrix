"""Release-trigger rules for guarding release surface drift."""

from __future__ import annotations

import fnmatch
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ReleaseArtifact:
    """A normalized artifact entry from the release manifest."""

    kind: str
    path: str
    target: str | None = None
    arch: str | None = None
    channel: str | None = None
    size_bytes: int = 0
    unpacked_size_bytes: int | None = None
    file_count: int = 0
    sourcemap_count: int = 0
    sourcemap_bytes: int = 0
    entries: tuple[dict[str, object], ...] = ()
    largest_entries: tuple[dict[str, object], ...] = ()

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "path": self.path,
            "target": self.target,
            "arch": self.arch,
            "channel": self.channel,
            "size_bytes": self.size_bytes,
            "unpacked_size_bytes": self.unpacked_size_bytes,
            "file_count": self.file_count,
            "sourcemap_count": self.sourcemap_count,
            "sourcemap_bytes": self.sourcemap_bytes,
            "entries": list(self.entries),
            "largest_entries": list(self.largest_entries),
        }


@dataclass(frozen=True)
class ReleaseTriggerRule:
    """A single release-trigger rule."""

    name: str
    type: str
    severity: str = "medium"
    action: str = "require_human_review"
    patterns: tuple[str, ...] = ()
    apply_to: tuple[str, ...] = ()
    group_by: tuple[str, ...] = ()
    baseline: str | None = None
    max_growth_percent: float | None = None
    min_growth_bytes: int | None = None
    max_size_bytes: int | None = None
    max_file_count: int | None = None
    paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class TriggerMatch:
    """A triggered rule with human-readable reasons."""

    name: str
    severity: str
    action: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReleaseTriggerReport:
    """Structured result of release-trigger evaluation."""

    blocked: bool
    human_review_required: bool
    baseline_present: bool
    manifest_path: str
    baseline_manifest_path: str | None = None
    changed_files: tuple[str, ...] = ()
    artifacts: tuple[ReleaseArtifact, ...] = ()
    triggers: tuple[TriggerMatch, ...] = ()

    def to_dict(self) -> dict:
        data = asdict(self)
        data["changed_files"] = list(self.changed_files)
        data["artifacts"] = [artifact.to_dict() for artifact in self.artifacts]
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


def load_release_triggers(config_path: Path) -> list[ReleaseTriggerRule]:
    """Load release-trigger rules from YAML."""
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    rules: list[ReleaseTriggerRule] = []
    for entry in raw.get("release_triggers", []):
        rules.append(
            ReleaseTriggerRule(
                name=entry.get("name", "unknown"),
                type=entry.get("type", "unknown"),
                severity=entry.get("severity", "medium"),
                action=entry.get("action", "require_human_review"),
                patterns=tuple(entry.get("patterns", [])),
                apply_to=tuple(entry.get("apply_to", [])),
                group_by=tuple(entry.get("group_by", [])),
                baseline=entry.get("baseline"),
                max_growth_percent=float(entry["max_growth_percent"])
                if entry.get("max_growth_percent") is not None
                else None,
                min_growth_bytes=entry.get("min_growth_bytes"),
                max_size_bytes=entry.get("max_size_bytes"),
                max_file_count=entry.get("max_file_count"),
                paths=tuple(entry.get("paths", [])),
            )
        )
    return rules


def load_release_manifest(manifest_path: Path) -> tuple[str, tuple[ReleaseArtifact, ...]]:
    """Load a release manifest from JSON."""
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = tuple(
        ReleaseArtifact(
            kind=str(entry.get("kind", "unknown")),
            path=str(entry.get("path", "")),
            target=entry.get("target"),
            arch=entry.get("arch"),
            channel=entry.get("channel"),
            size_bytes=int(entry.get("size_bytes", 0) or 0),
            unpacked_size_bytes=(
                int(entry["unpacked_size_bytes"])
                if entry.get("unpacked_size_bytes") is not None
                else None
            ),
            file_count=int(entry.get("file_count", 0) or 0),
            sourcemap_count=int(entry.get("sourcemap_count", 0) or 0),
            sourcemap_bytes=int(entry.get("sourcemap_bytes", 0) or 0),
            entries=tuple(entry.get("entries", []) or ()),
            largest_entries=tuple(entry.get("largest_entries", []) or ()),
        )
        for entry in raw.get("artifacts", [])
    )
    return str(raw.get("manifest_path", manifest_path)), artifacts


def _artifact_matches_rule(artifact: ReleaseArtifact, rule: ReleaseTriggerRule) -> bool:
    return not rule.apply_to or artifact.kind in rule.apply_to


def _artifact_group_key(artifact: ReleaseArtifact, group_by: tuple[str, ...]) -> tuple[str, ...]:
    if not group_by:
        return (artifact.kind, artifact.target or "", artifact.arch or "", artifact.channel or "")
    values: list[str] = []
    for field_name in group_by:
        value = getattr(artifact, field_name, None)
        values.append("" if value is None else str(value))
    return tuple(values)


def _find_baseline_artifact(
    artifact: ReleaseArtifact,
    baseline_artifacts: tuple[ReleaseArtifact, ...],
    rule: ReleaseTriggerRule,
) -> ReleaseArtifact | None:
    current_key = _artifact_group_key(artifact, rule.group_by)
    for candidate in baseline_artifacts:
        if candidate.kind != artifact.kind:
            continue
        if _artifact_group_key(candidate, rule.group_by) == current_key:
            return candidate
    return None


def evaluate_release_triggers(
    rules: list[ReleaseTriggerRule],
    artifacts: tuple[ReleaseArtifact, ...],
    *,
    manifest_path: str,
    changed_files: list[str] | None = None,
    baseline_artifacts: tuple[ReleaseArtifact, ...] = (),
    baseline_manifest_path: str | None = None,
) -> ReleaseTriggerReport:
    """Evaluate release-trigger rules for the current release surface."""
    changed_files = changed_files or []
    triggers: list[TriggerMatch] = []

    for rule in rules:
        if rule.type == "manifest_missing":
            if not artifacts:
                triggers.append(
                    TriggerMatch(
                        name=rule.name,
                        severity=rule.severity,
                        action=rule.action,
                        reasons=("release manifest contained no artifacts",),
                    )
                )
        elif rule.type == "unexpected_file":
            reasons: list[str] = []
            for artifact in artifacts:
                if not _artifact_matches_rule(artifact, rule):
                    continue
                for entry in artifact.entries:
                    entry_path = str(entry.get("path", ""))
                    if any(fnmatch.fnmatch(entry_path, pattern) for pattern in rule.patterns):
                        reasons.append(
                            f"artifact {artifact.kind} ({artifact.path}) contains unexpected entry: {entry_path}"
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
        elif rule.type == "artifact_size_delta":
            reasons: list[str] = []
            for artifact in artifacts:
                if not _artifact_matches_rule(artifact, rule):
                    continue
                if rule.max_size_bytes is not None and artifact.size_bytes > rule.max_size_bytes:
                    reasons.append(
                        f"artifact {artifact.kind} ({artifact.path}) size {artifact.size_bytes} exceeds limit {rule.max_size_bytes}"
                    )
                if rule.max_file_count is not None and artifact.file_count > rule.max_file_count:
                    reasons.append(
                        f"artifact {artifact.kind} ({artifact.path}) file count {artifact.file_count} exceeds limit {rule.max_file_count}"
                    )
                baseline_artifact = _find_baseline_artifact(artifact, baseline_artifacts, rule)
                if baseline_artifact is None or baseline_artifact.size_bytes <= 0:
                    continue
                growth_bytes = artifact.size_bytes - baseline_artifact.size_bytes
                growth_percent = (growth_bytes / baseline_artifact.size_bytes) * 100.0
                if growth_bytes <= 0:
                    continue
                percent_exceeded = (
                    rule.max_growth_percent is not None and growth_percent > rule.max_growth_percent
                )
                bytes_exceeded = (
                    rule.min_growth_bytes is None or growth_bytes >= rule.min_growth_bytes
                )
                if percent_exceeded and bytes_exceeded:
                    reasons.append(
                        "artifact "
                        f"{artifact.kind} ({artifact.path}) grew by {growth_bytes} bytes "
                        f"({growth_percent:.1f}%) versus baseline {baseline_artifact.path}"
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
        elif rule.type in {"release_boundary_change", "capability_change"}:
            reasons = tuple(
                f"changed release-sensitive path: {file_path}"
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

    blocked = any(trigger.action == "block_release" for trigger in triggers)
    human_review_required = blocked or any(
        trigger.action == "require_human_review" for trigger in triggers
    )
    return ReleaseTriggerReport(
        blocked=blocked,
        human_review_required=human_review_required,
        baseline_present=bool(baseline_artifacts),
        manifest_path=manifest_path,
        baseline_manifest_path=baseline_manifest_path,
        changed_files=tuple(changed_files),
        artifacts=artifacts,
        triggers=tuple(triggers),
    )
