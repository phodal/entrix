"""Shared execution engine for fitness runs."""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path

from entrix.governance import GovernancePolicy, filter_dimensions
from entrix.loaders import load_dimensions
from entrix.model import Dimension, EvidenceType, FitnessReport, Gate, Metric, MetricResult, ResultState
from entrix.presets.base import ProjectPreset
from entrix.runners.graph import GraphRunner
from entrix.runners.shell import ShellRunner
from entrix.scoring import score_dimension, score_report


def collect_changed_files(project_root: Path, base: str) -> list[str]:
    """Collect changed files from git for incremental fitness runs."""
    from entrix.presets import get_project_preset

    preset = get_project_preset()
    files: list[str] = []

    commands = [
        ["git", "diff", "--name-only", "--diff-filter=ACMR", base],
        ["git", "diff", "--name-only", "--diff-filter=ACMR"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]

    for command in commands:
        result = subprocess.run(
            command,
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        files.extend(line.strip() for line in result.stdout.splitlines() if line.strip())

    seen: set[str] = set()
    deduped: list[str] = []
    for file_path in files:
        if preset.should_ignore_changed_file(file_path):
            continue
        if file_path not in seen:
            seen.add(file_path)
            deduped.append(file_path)
    return deduped


def matches_changed_files(
    metric: Metric,
    changed_files: list[str],
    domains: set[str],
    preset: ProjectPreset,
) -> bool:
    """Check whether a metric should run for a changed file set."""
    if metric.run_when_changed:
        return any(
            fnmatch.fnmatch(changed_file, pattern)
            for changed_file in changed_files
            for pattern in metric.run_when_changed
        )
    if not domains:
        return False
    if "config" in domains:
        return True
    metric_domains = preset.metric_domains(metric)
    return "global" in metric_domains or bool(metric_domains.intersection(domains))


def filter_dimensions_for_incremental(
    dimensions: list[Dimension],
    changed_files: list[str],
    domains: set[str],
    preset: ProjectPreset,
) -> list[Dimension]:
    """Return only dimensions with metrics relevant to the changed file set."""
    if not changed_files:
        return []
    if "config" in domains:
        return dimensions

    filtered_dimensions: list[Dimension] = []
    for dimension in dimensions:
        filtered_metrics = []
        for metric in dimension.metrics:
            if matches_changed_files(metric, changed_files, domains, preset):
                filtered_metrics.append(metric)
        if filtered_metrics:
            filtered_dimensions.append(
                Dimension(
                    name=dimension.name,
                    weight=dimension.weight,
                    threshold_pass=dimension.threshold_pass,
                    threshold_warn=dimension.threshold_warn,
                    metrics=filtered_metrics,
                    source_file=dimension.source_file,
                )
            )
    return filtered_dimensions


def run_fitness_report(
    project_root: Path,
    policy: GovernancePolicy,
    preset: ProjectPreset,
    *,
    changed_files: list[str] | None = None,
    base: str = "HEAD",
) -> tuple[FitnessReport, list[Dimension]]:
    """Execute a fitness run and return report plus the selected dimensions."""
    dimensions = filter_dimensions(load_dimensions(preset.fitness_dir(project_root)), policy)

    runner_env: dict[str, str] = {}
    effective_changed_files = changed_files or []
    if effective_changed_files:
        changed_domains = preset.domains_from_files(effective_changed_files)
        dimensions = filter_dimensions_for_incremental(
            dimensions,
            effective_changed_files,
            changed_domains,
            preset,
        )
        runner_env = {
            "ROUTA_FITNESS_CHANGED_ONLY": "1",
            "ROUTA_FITNESS_CHANGED_BASE": base,
            "ROUTA_FITNESS_CHANGED_FILES": "\n".join(effective_changed_files),
        }

    shell_runner = ShellRunner(project_root, env_overrides=runner_env)
    graph_runner = GraphRunner(project_root)
    dimension_scores = []
    for dim in dimensions:
        results = _run_metric_batch(
            dim.metrics,
            shell_runner=shell_runner,
            graph_runner=graph_runner,
            dry_run=policy.dry_run,
            parallel=policy.parallel,
            changed_files=effective_changed_files,
            base=base,
        )
        dimension_scores.append(score_dimension(results, dim.name, dim.weight))

    return score_report(dimension_scores, min_score=policy.min_score), dimensions


def _run_metric_batch(
    metrics: list[Metric],
    *,
    shell_runner: ShellRunner,
    graph_runner: GraphRunner,
    dry_run: bool,
    parallel: bool,
    changed_files: list[str],
    base: str,
) -> list[MetricResult]:
    """Execute a mixed batch of shell and probe metrics while preserving order."""
    results: list[MetricResult] = []
    shell_batch: list[Metric] = []
    shell_indexes: list[int] = []

    for index, metric in enumerate(metrics):
        if metric.evidence_type == EvidenceType.PROBE:
            results.append(
                _run_probe_metric(
                    metric,
                    graph_runner=graph_runner,
                    dry_run=dry_run,
                    changed_files=changed_files,
                    base=base,
                )
            )
            continue

        results.append(
            MetricResult(
                metric_name=metric.name,
                passed=False,
                output="",
                tier=metric.tier,
                hard_gate=metric.gate == Gate.HARD,
                state=ResultState.UNKNOWN,
            )
        )
        shell_batch.append(metric)
        shell_indexes.append(index)

    if shell_batch:
        shell_results = shell_runner.run_batch(
            shell_batch,
            parallel=parallel,
            dry_run=dry_run,
        )
        for index, result in zip(shell_indexes, shell_results, strict=False):
            results[index] = result

    return results


def _run_probe_metric(
    metric: Metric,
    *,
    graph_runner: GraphRunner,
    dry_run: bool,
    changed_files: list[str],
    base: str,
) -> MetricResult:
    """Execute a graph-backed probe metric."""
    if metric.waiver and metric.waiver.is_active():
        return MetricResult(
            metric_name=metric.name,
            passed=True,
            output=f"[WAIVED] {metric.waiver.reason}",
            tier=metric.tier,
            hard_gate=metric.gate == Gate.HARD,
            state=ResultState.WAIVED,
        )

    if dry_run:
        return MetricResult(
            metric_name=metric.name,
            passed=True,
            output=f"[DRY-RUN] Would run probe: {metric.command}",
            tier=metric.tier,
            hard_gate=metric.gate == Gate.HARD,
        )

    if metric.command == "graph:impact":
        result = graph_runner.probe_impact(changed_files or None, base=base)
    elif metric.command in {"graph:test-radius", "graph:test-coverage"}:
        result = graph_runner.probe_test_coverage(changed_files or None, base=base)
    else:
        return MetricResult(
            metric_name=metric.name,
            passed=False,
            output=f"Unsupported probe command: {metric.command}",
            tier=metric.tier,
            hard_gate=metric.gate == Gate.HARD,
            state=ResultState.UNKNOWN,
        )

    result.metric_name = metric.name
    result.tier = metric.tier
    result.hard_gate = metric.gate == Gate.HARD
    return result
