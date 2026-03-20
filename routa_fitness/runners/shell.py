"""Shell runner — execute metric commands via subprocess."""

from __future__ import annotations

import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from os import environ
from pathlib import Path

from routa_fitness.model import Gate, Metric, MetricResult, ResultState


class ShellRunner:
    """Executes Metric commands as shell subprocesses."""

    def __init__(
        self,
        project_root: Path,
        timeout: int = 300,
        env_overrides: dict[str, str] | None = None,
    ):
        self.project_root = project_root
        self.timeout = timeout
        self.env_overrides = env_overrides or {}

    def run(self, metric: Metric, *, dry_run: bool = False) -> MetricResult:
        """Execute a single metric's shell command.

        Returns a MetricResult with pass/fail status based on either
        regex pattern matching or process exit code.
        """
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
                output=f"[DRY-RUN] Would run: {metric.command}",
                tier=metric.tier,
                hard_gate=metric.gate == Gate.HARD,
            )

        start = time.monotonic()
        timeout = metric.timeout_seconds or self.timeout
        try:
            result = subprocess.run(
                ["/bin/bash", "-lc", metric.command],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.project_root,
                env={**environ, **self.env_overrides},
            )
            output = result.stdout + result.stderr

            if metric.pattern:
                passed = bool(re.search(metric.pattern, output, re.IGNORECASE))
            else:
                passed = result.returncode == 0

            elapsed = (time.monotonic() - start) * 1000
            return MetricResult(
                metric_name=metric.name,
                passed=passed,
                output=output[:2000],
                tier=metric.tier,
                hard_gate=metric.gate == Gate.HARD,
                duration_ms=elapsed,
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.monotonic() - start) * 1000
            return MetricResult(
                metric_name=metric.name,
                passed=False,
                output=f"TIMEOUT ({timeout}s)",
                tier=metric.tier,
                hard_gate=metric.gate == Gate.HARD,
                duration_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return MetricResult(
                metric_name=metric.name,
                passed=False,
                output=str(e),
                tier=metric.tier,
                hard_gate=metric.gate == Gate.HARD,
                duration_ms=elapsed,
            )

    def run_batch(
        self,
        metrics: list[Metric],
        *,
        parallel: bool = False,
        dry_run: bool = False,
        max_workers: int = 4,
    ) -> list[MetricResult]:
        """Execute multiple metrics, optionally in parallel.

        Results are returned in the same order as the input metrics.
        """
        if not parallel or dry_run:
            return [self.run(m, dry_run=dry_run) for m in metrics]

        results: dict[int, MetricResult] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.run, m): i for i, m in enumerate(metrics)}
            for future in as_completed(futures):
                idx = futures[future]
                results[idx] = future.result()

        return [results[i] for i in range(len(metrics))]
