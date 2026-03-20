"""Scoring engine — weighted score calculation across dimensions."""

from __future__ import annotations

from entrix.model import DimensionScore, FitnessReport, MetricResult, ResultState


_SCORABLE_PASS_STATES = {ResultState.PASS, ResultState.WAIVED}
_SCORABLE_TOTAL_STATES = {ResultState.PASS, ResultState.FAIL, ResultState.WAIVED}


def score_dimension(results: list[MetricResult], dimension_name: str, weight: int) -> DimensionScore:
    """Calculate score for a single dimension from its metric results."""
    if not results:
        return DimensionScore(
            dimension=dimension_name, weight=weight, passed=0, total=0, score=0.0
        )

    passed = sum(1 for r in results if r.state in _SCORABLE_PASS_STATES)
    total = sum(1 for r in results if r.state in _SCORABLE_TOTAL_STATES)
    score = (passed / total) * 100 if total > 0 else 0.0
    hard_gate_failures = [
        r.metric_name
        for r in results
        if r.state == ResultState.FAIL and r.hard_gate
    ]

    return DimensionScore(
        dimension=dimension_name,
        weight=weight,
        passed=passed,
        total=total,
        score=score,
        hard_gate_failures=hard_gate_failures,
        results=results,
    )


def score_report(
    dimension_scores: list[DimensionScore], min_score: float = 80.0
) -> FitnessReport:
    """Calculate final weighted score across all dimensions.

    Score formula: Σ(Weight_i × Score_i) / Σ(Weight_i)
    """
    all_hard_gate_failures = []
    weighted_sum = 0.0
    total_weight = 0

    for ds in dimension_scores:
        all_hard_gate_failures.extend(ds.hard_gate_failures)
        if ds.total > 0:
            weighted_sum += ds.score * ds.weight
            total_weight += ds.weight

    final_score = weighted_sum / total_weight if total_weight > 0 else 0.0

    return FitnessReport(
        dimensions=dimension_scores,
        final_score=final_score,
        hard_gate_blocked=len(all_hard_gate_failures) > 0,
        score_blocked=total_weight > 0 and final_score < min_score,
    )
