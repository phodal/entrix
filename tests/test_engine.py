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
        progress_callback=None,
    ) -> list[MetricResult]:
        del parallel, dry_run, max_workers
        results = []
        for metric in metrics:
            if progress_callback is not None:
                progress_callback("start", metric, None)
            result = MetricResult(
                metric_name=metric.name,
                passed=True,
                output=f"shell:{metric.command}",
                tier=metric.tier,
            )
            if progress_callback is not None:
                progress_callback("end", metric, result)
            results.append(result)
        return results


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


class FakeSarifRunner:
    def __init__(self, _project_root: Path, env_overrides: dict[str, str] | None = None) -> None:
        self.env_overrides = env_overrides or {}
        self.calls: list[str] = []

    def run_batch(
        self,
        metrics: list[Metric],
        *,
        dry_run: bool = False,
    ) -> list[MetricResult]:
        del dry_run
        self.calls.extend(metric.name for metric in metrics)
        return [
            MetricResult(
                metric_name=metric.name,
                passed=False,
                output=f"sarif:{metric.command}",
                tier=metric.tier,
                state=ResultState.FAIL,
            )
            for metric in metrics
        ]


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
    monkeypatch.setattr(engine_module, "SarifRunner", FakeSarifRunner)
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
    monkeypatch.setattr(engine_module, "SarifRunner", FakeSarifRunner)
    monkeypatch.setattr(engine_module, "GraphRunner", FakeGraphRunner)

    report, _ = engine_module.run_fitness_report(
        tmp_path,
        GovernancePolicy(),
        get_project_preset(),
    )

    assert report.dimensions[0].results[0].state == ResultState.SKIPPED
    assert report.dimensions[0].total == 0


def test_run_fitness_report_filters_dimensions_from_policy(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        engine_module,
        "load_dimensions",
        lambda _fitness_dir: [
            Dimension(
                name="code_quality",
                weight=24,
                metrics=[Metric(name="lint", command="npm run lint")],
            ),
            Dimension(
                name="security",
                weight=20,
                metrics=[Metric(name="audit", command="npm audit")],
            ),
        ],
    )
    monkeypatch.setattr(engine_module, "ShellRunner", FakeShellRunner)
    monkeypatch.setattr(engine_module, "SarifRunner", FakeSarifRunner)
    monkeypatch.setattr(engine_module, "GraphRunner", FakeGraphRunner)

    report, dimensions = engine_module.run_fitness_report(
        tmp_path,
        GovernancePolicy(dimension_filters=("security",)),
        get_project_preset(),
    )

    assert [dimension.name for dimension in dimensions] == ["security"]
    assert [dimension.dimension for dimension in report.dimensions] == ["security"]


def test_run_fitness_report_dispatches_sarif_metrics(monkeypatch, tmp_path: Path):
    sarif_runner = FakeSarifRunner(tmp_path)
    monkeypatch.setattr(
        engine_module,
        "load_dimensions",
        lambda _fitness_dir: [
            Dimension(
                name="security",
                weight=100,
                metrics=[
                    Metric(name="semgrep_sarif", command="reports/semgrep.sarif", evidence_type=EvidenceType.SARIF),
                    Metric(name="lint", command="npm run lint"),
                ],
            )
        ],
    )
    monkeypatch.setattr(engine_module, "ShellRunner", FakeShellRunner)
    monkeypatch.setattr(engine_module, "SarifRunner", lambda _project_root, **kwargs: sarif_runner)
    monkeypatch.setattr(engine_module, "GraphRunner", FakeGraphRunner)

    report, _ = engine_module.run_fitness_report(
        tmp_path,
        GovernancePolicy(),
        get_project_preset(),
    )

    assert sarif_runner.calls == ["semgrep_sarif"]
    assert report.dimensions[0].results[0].output == "sarif:reports/semgrep.sarif"
    assert report.dimensions[0].results[1].output == "shell:npm run lint"


def test_run_fitness_report_emits_progress_events(monkeypatch, tmp_path: Path):
    events: list[tuple[str, str, str | None]] = []

    monkeypatch.setattr(
        engine_module,
        "load_dimensions",
        lambda _fitness_dir: [
            Dimension(
                name="mixed",
                weight=100,
                metrics=[
                    Metric(name="probe_metric", command="graph:impact", evidence_type=EvidenceType.PROBE),
                    Metric(name="shell_metric", command="npm run lint"),
                    Metric(name="sarif_metric", command="reports/semgrep.sarif", evidence_type=EvidenceType.SARIF),
                ],
            )
        ],
    )
    monkeypatch.setattr(engine_module, "ShellRunner", FakeShellRunner)
    monkeypatch.setattr(engine_module, "SarifRunner", FakeSarifRunner)
    monkeypatch.setattr(engine_module, "GraphRunner", FakeGraphRunner)

    def capture(event: str, metric: Metric, result: MetricResult | None) -> None:
        events.append((event, metric.name, None if result is None else result.state.value))

    engine_module.run_fitness_report(
        tmp_path,
        GovernancePolicy(),
        get_project_preset(),
        progress_callback=capture,
    )

    assert events == [
        ("start", "probe_metric", None),
        ("end", "probe_metric", "pass"),
        ("start", "shell_metric", None),
        ("end", "shell_metric", "pass"),
        ("start", "sarif_metric", None),
        ("end", "sarif_metric", "fail"),
    ]
