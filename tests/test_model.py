"""Tests for routa_fitness.model."""

from routa_fitness.model import (
    AnalysisMode,
    Confidence,
    Dimension,
    DimensionScore,
    EvidenceType,
    ExecutionScope,
    FitnessKind,
    FitnessReport,
    Gate,
    Metric,
    MetricResult,
    ResultState,
    Stability,
    Tier,
    Waiver,
)


def test_tier_order():
    assert Tier.order(Tier.FAST) < Tier.order(Tier.NORMAL) < Tier.order(Tier.DEEP)


def test_tier_values():
    assert Tier.FAST.value == "fast"
    assert Tier.NORMAL.value == "normal"
    assert Tier.DEEP.value == "deep"


def test_metric_defaults():
    m = Metric(name="lint", command="npm run lint")
    assert m.pattern == ""
    assert m.hard_gate is False
    assert m.tier == Tier.NORMAL
    assert m.kind == FitnessKind.ATOMIC
    assert m.analysis == AnalysisMode.STATIC
    assert m.execution_scope == ExecutionScope.LOCAL
    assert m.gate == Gate.SOFT
    assert m.stability == Stability.DETERMINISTIC
    assert m.evidence_type == EvidenceType.COMMAND
    assert m.scope == []
    assert m.run_when_changed == []
    assert m.timeout_seconds is None
    assert m.owner == ""
    assert m.confidence == Confidence.UNKNOWN
    assert m.waiver is None


def test_metric_hard_gate_sets_default_gate():
    m = Metric(name="lint", command="npm run lint", hard_gate=True)
    assert m.gate == Gate.HARD


def test_dimension_defaults():
    d = Dimension(name="security", weight=20)
    assert d.threshold_pass == 90
    assert d.threshold_warn == 80
    assert d.metrics == []
    assert d.source_file == ""


def test_metric_result():
    r = MetricResult(metric_name="lint", passed=True, output="ok", tier=Tier.FAST)
    assert r.hard_gate is False
    assert r.duration_ms == 0.0
    assert r.state == ResultState.PASS


def test_metric_result_failed_defaults_state():
    r = MetricResult(metric_name="lint", passed=False, output="boom", tier=Tier.FAST)
    assert r.state == ResultState.FAIL


def test_metric_result_explicit_state_preserved():
    r = MetricResult(
        metric_name="lint",
        passed=False,
        output="skipped",
        tier=Tier.FAST,
        state=ResultState.SKIPPED,
    )
    assert r.state == ResultState.SKIPPED


def test_waiver_model():
    waiver = Waiver(reason="legacy hotspot", owner="platform", tracking_issue=217)
    assert waiver.reason == "legacy hotspot"
    assert waiver.owner == "platform"
    assert waiver.tracking_issue == 217


def test_dimension_score():
    ds = DimensionScore(dimension="security", weight=20, passed=3, total=4, score=75.0)
    assert ds.hard_gate_failures == []
    assert ds.results == []


def test_fitness_report_defaults():
    r = FitnessReport()
    assert r.dimensions == []
    assert r.final_score == 0.0
    assert r.hard_gate_blocked is False
    assert r.score_blocked is False
