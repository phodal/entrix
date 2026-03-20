"""Governance — policy enforcement for fitness function execution."""

from __future__ import annotations

from dataclasses import dataclass

from routa_fitness.model import Dimension, ExecutionScope, FitnessReport, Metric, Tier


@dataclass
class GovernancePolicy:
    """Controls which metrics run, when, and what blocks."""

    tier_filter: Tier | None = None
    parallel: bool = False
    dry_run: bool = False
    verbose: bool = False
    min_score: float = 80.0
    fail_on_hard_gate: bool = True
    execution_scope: ExecutionScope | None = None


def _tier_passes_filter(metric_tier: Tier, filter_tier: Tier) -> bool:
    """Check if a metric's tier is at or below the filter level.

    Tier hierarchy: fast(0) < normal(1) < deep(2).
    --tier normal runs both fast and normal metrics.
    """
    return Tier.order(metric_tier) <= Tier.order(filter_tier)


def filter_metrics(metrics: list[Metric], policy: GovernancePolicy) -> list[Metric]:
    """Apply tier filtering to a list of metrics."""
    result = metrics
    if policy.tier_filter is not None:
        result = [m for m in result if _tier_passes_filter(m.tier, policy.tier_filter)]
    if policy.execution_scope is not None:
        result = [m for m in result if m.execution_scope == policy.execution_scope]
    return result


def filter_dimensions(
    dimensions: list[Dimension], policy: GovernancePolicy
) -> list[Dimension]:
    """Apply tier filtering to dimensions, returning only those with remaining metrics."""
    result: list[Dimension] = []
    for dim in dimensions:
        filtered = filter_metrics(dim.metrics, policy)
        if filtered:
            result.append(
                Dimension(
                    name=dim.name,
                    weight=dim.weight,
                    threshold_pass=dim.threshold_pass,
                    threshold_warn=dim.threshold_warn,
                    metrics=filtered,
                    source_file=dim.source_file,
                )
            )
    return result


def enforce(report: FitnessReport, policy: GovernancePolicy) -> int:
    """Determine exit code from a fitness report.

    Returns:
        0 — pass
        1 — score below minimum threshold
        2 — hard gate failure
    """
    if policy.fail_on_hard_gate and report.hard_gate_blocked:
        return 2
    if report.score_blocked:
        return 1
    return 0
