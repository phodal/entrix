"""Tests for routa_fitness.scoring."""

from routa_fitness.model import MetricResult, ResultState, Tier
from routa_fitness.scoring import score_dimension, score_report


def test_score_dimension_all_pass():
    results = [
        MetricResult(metric_name="a", passed=True, output="", tier=Tier.FAST),
        MetricResult(metric_name="b", passed=True, output="", tier=Tier.FAST),
    ]
    ds = score_dimension(results, "quality", 24)
    assert ds.score == 100.0
    assert ds.passed == 2
    assert ds.total == 2
    assert ds.hard_gate_failures == []


def test_score_dimension_partial():
    results = [
        MetricResult(metric_name="a", passed=True, output="", tier=Tier.FAST),
        MetricResult(metric_name="b", passed=False, output="", tier=Tier.FAST),
    ]
    ds = score_dimension(results, "quality", 24)
    assert ds.score == 50.0
    assert ds.passed == 1
    assert ds.total == 2


def test_score_dimension_hard_gate_failure():
    results = [
        MetricResult(metric_name="lint", passed=False, output="", tier=Tier.FAST, hard_gate=True),
    ]
    ds = score_dimension(results, "quality", 24)
    assert ds.hard_gate_failures == ["lint"]


def test_score_dimension_empty():
    ds = score_dimension([], "empty", 10)
    assert ds.score == 0.0
    assert ds.total == 0


def test_score_report_weighted():
    results_a = [MetricResult(metric_name="a", passed=True, output="", tier=Tier.FAST)]
    results_b = [MetricResult(metric_name="b", passed=False, output="", tier=Tier.FAST)]

    ds_a = score_dimension(results_a, "high_weight", 80)
    ds_b = score_dimension(results_b, "low_weight", 20)

    report = score_report([ds_a, ds_b])
    # (100 * 80 + 0 * 20) / 100 = 80.0
    assert report.final_score == 80.0
    assert report.hard_gate_blocked is False
    assert report.score_blocked is False  # 80 >= 80


def test_score_report_hard_gate_blocked():
    results = [
        MetricResult(metric_name="gate", passed=False, output="", tier=Tier.FAST, hard_gate=True),
    ]
    ds = score_dimension(results, "sec", 20)
    report = score_report([ds])
    assert report.hard_gate_blocked is True


def test_score_report_score_blocked():
    results = [
        MetricResult(metric_name="a", passed=True, output="", tier=Tier.FAST),
        MetricResult(metric_name="b", passed=False, output="", tier=Tier.FAST),
        MetricResult(metric_name="c", passed=False, output="", tier=Tier.FAST),
    ]
    ds = score_dimension(results, "quality", 100)
    report = score_report([ds], min_score=80.0)
    # 33.3% < 80%
    assert report.score_blocked is True


def test_score_dimension_ignores_unknown_and_skipped():
    results = [
        MetricResult(metric_name="pass", passed=True, output="", tier=Tier.FAST),
        MetricResult(
            metric_name="unknown",
            passed=False,
            output="unknown",
            tier=Tier.FAST,
            state=ResultState.UNKNOWN,
        ),
        MetricResult(
            metric_name="skipped",
            passed=False,
            output="skipped",
            tier=Tier.FAST,
            state=ResultState.SKIPPED,
        ),
    ]
    ds = score_dimension(results, "quality", 100)
    assert ds.passed == 1
    assert ds.total == 1
    assert ds.score == 100.0


def test_score_dimension_counts_waived_as_pass():
    results = [
        MetricResult(
            metric_name="waived",
            passed=True,
            output="waived",
            tier=Tier.FAST,
            state=ResultState.WAIVED,
        ),
        MetricResult(metric_name="fail", passed=False, output="", tier=Tier.FAST),
    ]
    ds = score_dimension(results, "quality", 100)
    assert ds.passed == 1
    assert ds.total == 2
    assert ds.score == 50.0


def test_score_report_does_not_block_when_no_scorable_weight():
    ds = score_dimension(
        [
            MetricResult(
                metric_name="graph_probe",
                passed=False,
                output="skipped",
                tier=Tier.NORMAL,
                state=ResultState.SKIPPED,
            )
        ],
        "observability",
        0,
    )
    report = score_report([ds], min_score=80.0)
    assert report.final_score == 0.0
    assert report.score_blocked is False
