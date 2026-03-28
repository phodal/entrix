"""Tests for visual fitness reporters."""

from __future__ import annotations

from entrix.model import Dimension, DimensionScore, FitnessReport, Metric, MetricResult, ResultState, Tier
from entrix.reporters.visual import AsciiReporter, RichLiveProgressReporter, RichReporter


def _sample_report() -> FitnessReport:
    return FitnessReport(
        final_score=83.3,
        dimensions=[
            DimensionScore(
                dimension="code_quality",
                weight=24,
                passed=2,
                total=3,
                score=66.7,
                results=[
                    MetricResult(metric_name="lint", passed=True, output="", tier=Tier.FAST),
                    MetricResult(metric_name="tests", passed=True, output="", tier=Tier.NORMAL),
                    MetricResult(metric_name="graph_probe", passed=False, output="", tier=Tier.NORMAL),
                ],
            ),
            DimensionScore(
                dimension="observability",
                weight=0,
                passed=0,
                total=0,
                score=0.0,
                results=[],
            ),
        ],
    )


def test_ascii_reporter_renders_scorecard(capsys):
    AsciiReporter(width=10).report(_sample_report())

    output = capsys.readouterr().out
    assert "VISUAL SCORECARD" in output
    assert "CODE_QUALITY" in output
    assert "66.7%" in output
    assert "weight=24%" in output
    assert "FINAL SCORE" in output
    assert "graph_probe" in output


def test_rich_reporter_falls_back_when_rich_missing(monkeypatch, capsys):
    monkeypatch.setattr("entrix.reporters.visual._load_rich", lambda: None)

    RichReporter(width=10).report(_sample_report())

    output = capsys.readouterr().out
    assert "falling back to ASCII scorecard" in output
    assert "VISUAL SCORECARD" in output


def test_rich_live_progress_reporter_tracks_state_and_tail(monkeypatch):
    monkeypatch.setattr("entrix.reporters.visual._load_rich_live", lambda: None)
    reporter = RichLiveProgressReporter(stream=None)  # type: ignore[arg-type]
    reporter.setup(
        [
            Dimension(
                name="quality",
                weight=100,
                metrics=[
                    Metric(name="lint", command="npm run lint", tier=Tier.FAST),
                    Metric(name="tests", command="npm run test", tier=Tier.NORMAL),
                ],
            )
        ]
    )

    reporter.handle_progress("start", Metric(name="lint", command="npm run lint", tier=Tier.FAST), None)
    reporter.handle_progress(
        "end",
        Metric(name="lint", command="npm run lint", tier=Tier.FAST),
        MetricResult(metric_name="lint", passed=True, output="", tier=Tier.FAST, duration_ms=1200),
    )
    reporter.handle_progress("start", Metric(name="tests", command="npm run test", tier=Tier.NORMAL), None)
    reporter.handle_progress(
        "end",
        Metric(name="tests", command="npm run test", tier=Tier.NORMAL),
        MetricResult(
            metric_name="tests",
            passed=False,
            output="boom\nstack trace",
            tier=Tier.NORMAL,
            duration_ms=2200,
            state=ResultState.FAIL,
        ),
    )

    lines = reporter.snapshot_lines()
    assert lines[0] == "[fitness] 1 passed | 1 failed | 0 running | 0 queued"
    assert "[1/2] PASSED lint 1.2s" in lines
    assert "[2/2] FAILED tests 2.2s" in lines
    assert "[fitness tail]" in lines
    assert "[tests] boom" in lines
