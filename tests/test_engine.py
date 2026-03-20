"""Tests for entrix.engine."""

from pathlib import Path

import entrix.engine as engine_module
from entrix.governance import GovernancePolicy
from entrix.model import (
    Dimension,
    EvidenceType,
    Metric,
    MetricResult,
    ResultState,
    Tier,
)
from entrix.presets import get_project_preset


class FakeShellRunner:
    def __init__(self, _project_root: Path, env_overrides: dict[str, str] | None = None) -> None:
        self.env_overrides = env_overrides or {}

    def run_batch(
        self,
        metrics: list[Metric],
        *,
        parallel: bool = False,
        dry_run: bool = False,
        max_workers: int = 4,
    ) -> list[MetricResult]:
        del parallel, dry_run, max_workers
        return [
            MetricResult(
                metric_name=metric.name,
                passed=True,
                output=f"shell:{metric.command}",
                tier=metric.tier,
            )
            for metric in metrics
        ]


class FakeGraphRunner:
    def __init__(self, _project_root: Path) -> None:
        self.calls: list[tuple[str, list[str] | None, str]] = []

    def probe_impact(self, changed_files: list[str] | None = None, *, base: str = "HEAD", **_kwargs) -> MetricResult:
        self.calls.append(("impact", changed_files, base))
        return MetricResult(
            metric_name="graph_probe",
            passed=True,
            output="graph_probe_status: ok",
            tier=Tier.NORMAL,
        )

    def probe_test_coverage(
        self,
        changed_files: list[str] | None = None,
        *,
        base: str = "HEAD",
    ) -> MetricResult:
        self.calls.append(("test-radius", changed_files, base))
        return MetricResult(
            metric_name="graph_test_coverage",
            passed=False,
            output="graph_test_coverage: skipped (graph unavailable)",
            tier=Tier.NORMAL,
            state=ResultState.SKIPPED,
        )


def test_run_fitness_report_dispatches_probe_metrics(monkeypatch, tmp_path: Path):
    graph_runner = FakeGraphRunner(tmp_path)
    monkeypatch.setattr(
        engine_module,
        "load_dimensions",
        lambda _fitness_dir: [
            Dimension(
                name="observability",
                weight=0,
                metrics=[
                    Metric(name="graph_impact", command="graph:impact", evidence_type=EvidenceType.PROBE),
                    Metric(name="lint", command="npm run lint"),
                ],
            )
        ],
    )
    monkeypatch.setattr(engine_module, "ShellRunner", FakeShellRunner)
    monkeypatch.setattr(engine_module, "GraphRunner", lambda _project_root: graph_runner)

    report, dimensions = engine_module.run_fitness_report(
        tmp_path,
        GovernancePolicy(),
        get_project_preset(),
        changed_files=["src/app/page.tsx"],
        base="HEAD~1",
    )

    assert dimensions[0].metrics[0].name == "graph_impact"
    assert report.dimensions[0].results[0].metric_name == "graph_impact"
    assert report.dimensions[0].results[1].output == "shell:npm run lint"
    assert graph_runner.calls == [("impact", ["src/app/page.tsx"], "HEAD~1")]


def test_run_fitness_report_excludes_skipped_probe_from_score(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        engine_module,
        "load_dimensions",
        lambda _fitness_dir: [
            Dimension(
                name="observability",
                weight=0,
                metrics=[
                    Metric(name="graph_test_radius", command="graph:test-radius", evidence_type=EvidenceType.PROBE)
                ],
            )
        ],
    )
    monkeypatch.setattr(engine_module, "ShellRunner", FakeShellRunner)
    monkeypatch.setattr(engine_module, "GraphRunner", FakeGraphRunner)

    report, _ = engine_module.run_fitness_report(
        tmp_path,
        GovernancePolicy(),
        get_project_preset(),
    )

    assert report.dimensions[0].results[0].state == ResultState.SKIPPED
    assert report.dimensions[0].total == 0
