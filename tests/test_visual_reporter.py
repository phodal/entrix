"""Tests for visual fitness reporters."""

from __future__ import annotations

from entrix.model import DimensionScore, FitnessReport, MetricResult, Tier
from entrix.reporters.visual import AsciiReporter, RichReporter


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
