"""Tests for routa_fitness.governance."""

from routa_fitness.governance import (
    GovernancePolicy,
    enforce,
    filter_dimensions,
    filter_metrics,
)
from routa_fitness.model import Dimension, ExecutionScope, FitnessReport, Metric, Tier


def test_filter_metrics_no_filter():
    metrics = [Metric(name="a", command="x", tier=Tier.DEEP)]
    policy = GovernancePolicy()
    assert filter_metrics(metrics, policy) == metrics


def test_filter_metrics_fast_only():
    metrics = [
        Metric(name="fast", command="x", tier=Tier.FAST),
        Metric(name="normal", command="x", tier=Tier.NORMAL),
        Metric(name="deep", command="x", tier=Tier.DEEP),
    ]
    policy = GovernancePolicy(tier_filter=Tier.FAST)
    result = filter_metrics(metrics, policy)
    assert len(result) == 1
    assert result[0].name == "fast"


def test_filter_metrics_normal_includes_fast():
    metrics = [
        Metric(name="fast", command="x", tier=Tier.FAST),
        Metric(name="normal", command="x", tier=Tier.NORMAL),
        Metric(name="deep", command="x", tier=Tier.DEEP),
    ]
    policy = GovernancePolicy(tier_filter=Tier.NORMAL)
    result = filter_metrics(metrics, policy)
    assert len(result) == 2
    assert {m.name for m in result} == {"fast", "normal"}


def test_filter_dimensions_removes_empty():
    dims = [
        Dimension(
            name="sec",
            weight=20,
            metrics=[Metric(name="deep_only", command="x", tier=Tier.DEEP)],
        ),
    ]
    policy = GovernancePolicy(tier_filter=Tier.FAST)
    result = filter_dimensions(dims, policy)
    assert len(result) == 0


def test_filter_dimensions_preserves_matching():
    dims = [
        Dimension(
            name="quality",
            weight=24,
            metrics=[
                Metric(name="lint", command="x", tier=Tier.FAST),
                Metric(name="test", command="x", tier=Tier.NORMAL),
            ],
        ),
    ]
    policy = GovernancePolicy(tier_filter=Tier.FAST)
    result = filter_dimensions(dims, policy)
    assert len(result) == 1
    assert len(result[0].metrics) == 1
    assert result[0].metrics[0].name == "lint"


def test_filter_metrics_execution_scope():
    metrics = [
        Metric(name="local", command="x", execution_scope=ExecutionScope.LOCAL),
        Metric(name="staging", command="x", execution_scope=ExecutionScope.STAGING),
    ]
    policy = GovernancePolicy(execution_scope=ExecutionScope.STAGING)
    result = filter_metrics(metrics, policy)
    assert [metric.name for metric in result] == ["staging"]


def test_enforce_pass():
    report = FitnessReport(final_score=95.0, hard_gate_blocked=False, score_blocked=False)
    assert enforce(report, GovernancePolicy()) == 0


def test_enforce_hard_gate():
    report = FitnessReport(final_score=95.0, hard_gate_blocked=True, score_blocked=False)
    assert enforce(report, GovernancePolicy()) == 2


def test_enforce_score_block():
    report = FitnessReport(final_score=70.0, hard_gate_blocked=False, score_blocked=True)
    assert enforce(report, GovernancePolicy()) == 1


def test_enforce_hard_gate_takes_priority():
    report = FitnessReport(final_score=70.0, hard_gate_blocked=True, score_blocked=True)
    assert enforce(report, GovernancePolicy()) == 2


def test_enforce_hard_gate_disabled():
    report = FitnessReport(final_score=95.0, hard_gate_blocked=True, score_blocked=False)
    policy = GovernancePolicy(fail_on_hard_gate=False)
    assert enforce(report, policy) == 0
