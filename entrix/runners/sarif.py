"""SARIF runner — evaluate metrics from SARIF evidence."""

from __future__ import annotations

import json
import re
import subprocess
import time
from os import environ
from pathlib import Path
from typing import Any

from entrix.model import Gate, Metric, MetricResult, ResultState


class SarifRunner:
    """Loads SARIF evidence from file path or command stdout and evaluates findings."""

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
        """Execute a SARIF metric and evaluate it into PASS/FAIL/UNKNOWN."""
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
                output=f"[DRY-RUN] Would read SARIF evidence: {metric.command}",
                tier=metric.tier,
                hard_gate=metric.gate == Gate.HARD,
            )

        start = time.monotonic()
        timeout = metric.timeout_seconds or self.timeout
        try:
            payload = self._load_payload(metric.command, timeout=timeout)
            summary = _summarize_sarif(payload)
            summary_line = (
                f"sarif_runs={summary['runs']} "
                f"sarif_results={summary['results']} "
                f"sarif_errors={summary['errors']} "
                f"sarif_warnings={summary['warnings']} "
                f"sarif_notes={summary['notes']}"
            )
            if metric.pattern:
                passed = bool(re.search(metric.pattern, summary_line, re.IGNORECASE))
            else:
                passed = summary["errors"] == 0
            elapsed = (time.monotonic() - start) * 1000
            return MetricResult(
                metric_name=metric.name,
                passed=passed,
                output=summary_line,
                tier=metric.tier,
                hard_gate=metric.gate == Gate.HARD,
                duration_ms=elapsed,
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.monotonic() - start) * 1000
            return MetricResult(
                metric_name=metric.name,
                passed=False,
                output=f"SARIF TIMEOUT ({timeout}s)",
                tier=metric.tier,
                hard_gate=metric.gate == Gate.HARD,
                duration_ms=elapsed,
                state=ResultState.UNKNOWN,
            )
        except Exception as error:
            elapsed = (time.monotonic() - start) * 1000
            return MetricResult(
                metric_name=metric.name,
                passed=False,
                output=f"SARIF parse error: {error}",
                tier=metric.tier,
                hard_gate=metric.gate == Gate.HARD,
                duration_ms=elapsed,
                state=ResultState.UNKNOWN,
            )

    def run_batch(self, metrics: list[Metric], *, dry_run: bool = False) -> list[MetricResult]:
        """Execute multiple SARIF metrics in order."""
        return [self.run(metric, dry_run=dry_run) for metric in metrics]

    def _load_payload(self, command: str, *, timeout: int) -> dict[str, Any]:
        # If the command resolves to an existing file path, treat it as SARIF file input.
        candidate = (self.project_root / command).resolve()
        if candidate.is_file():
            content = candidate.read_text(encoding="utf-8")
            data = json.loads(content)
            if not isinstance(data, dict):
                raise ValueError("SARIF root must be an object")
            return data

        result = subprocess.run(
            ["/bin/bash", "-lc", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=self.project_root,
            env={**environ, **self.env_overrides},
        )
        parsed = _parse_json_from_text(result.stdout)
        if not isinstance(parsed, dict):
            raise ValueError("SARIF stdout did not contain a JSON object")
        return parsed


def _parse_json_from_text(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty stdout")
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(stripped[start : end + 1])


def _summarize_sarif(payload: dict[str, Any]) -> dict[str, int]:
    runs = payload.get("runs")
    if not isinstance(runs, list):
        raise ValueError("SARIF payload missing runs[]")

    counts = {
        "runs": len(runs),
        "results": 0,
        "errors": 0,
        "warnings": 0,
        "notes": 0,
    }
    for run in runs:
        if not isinstance(run, dict):
            continue
        results = run.get("results") or []
        if not isinstance(results, list):
            continue
        counts["results"] += len(results)
        for result in results:
            level = ""
            if isinstance(result, dict):
                raw_level = result.get("level")
                if isinstance(raw_level, str):
                    level = raw_level.lower()
            if level == "error":
                counts["errors"] += 1
            elif level == "note":
                counts["notes"] += 1
            else:
                counts["warnings"] += 1
    return counts
