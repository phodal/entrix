"""Shell runner — execute metric commands via subprocess."""

from __future__ import annotations

import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from os import environ
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from typing import Callable

from entrix.model import Gate, Metric, MetricResult, ResultState

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[mGKHF]")

# Keep first 4KB + last 4KB so both startup context and the final
# summary (pass/fail line) survive truncation.
_OUTPUT_HEAD = 4000
_OUTPUT_TAIL = 4000
_OUTPUT_MAX = _OUTPUT_HEAD + _OUTPUT_TAIL + 200  # a bit of slack


def _smart_truncate(text: str) -> str:
    """Keep head + tail of output so both context and verdict are visible."""
    if len(text) <= _OUTPUT_MAX:
        return text
    head = text[:_OUTPUT_HEAD]
    tail = text[-_OUTPUT_TAIL:]
    omitted = len(text) - _OUTPUT_HEAD - _OUTPUT_TAIL
    return f"{head}\n\n... [{omitted} characters omitted] ...\n\n{tail}"

ProgressCallback = Callable[[str, Metric, MetricResult | None], None]
OutputCallback = Callable[[Metric, str, str], None]


class ShellRunner:
    """Executes Metric commands as shell subprocesses."""

    def __init__(
        self,
        project_root: Path,
        timeout: int = 300,
        env_overrides: dict[str, str] | None = None,
        stream_output: bool = False,
        output_callback: OutputCallback | None = None,
    ):
        self.project_root = project_root
        self.timeout = timeout
        self.env_overrides = env_overrides or {}
        self.stream_output = stream_output
        self.output_callback = output_callback

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
            if self.stream_output and self.output_callback is not None:
                output, returncode = self._run_streaming(metric, timeout=timeout)
            else:
                output, returncode = self._run_captured(metric, timeout=timeout)

            clean_output = _ANSI_ESCAPE.sub("", output)

            if metric.pattern:
                pattern_matched = bool(re.search(metric.pattern, clean_output, re.IGNORECASE))
                # Exit-code-first hybrid: non-zero exit always fails.
                # Pattern is supplementary evidence when exit code is 0.
                passed = (returncode == 0) and pattern_matched
            else:
                passed = returncode == 0

            elapsed = (time.monotonic() - start) * 1000

            # Determine result state: distinguish checker infrastructure errors
            # from genuine product failures.
            state: ResultState | None = None
            if passed:
                state = ResultState.PASS
            elif returncode != 0 and metric.pattern and not pattern_matched:
                # Both exit code AND pattern failed — likely an infrastructure
                # error (missing file, crash, stack overflow, etc.)
                state = ResultState.UNKNOWN
            else:
                state = ResultState.FAIL

            return MetricResult(
                metric_name=metric.name,
                passed=passed,
                output=_smart_truncate(clean_output),
                tier=metric.tier,
                hard_gate=metric.gate == Gate.HARD,
                duration_ms=elapsed,
                state=state,
                returncode=returncode,
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
                state=ResultState.UNKNOWN,
            )

    def _run_captured(self, metric: Metric, *, timeout: int) -> tuple[str, int]:
        result = subprocess.run(
            ["/bin/bash", "-lc", metric.command],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=self.project_root,
            env={**environ, **self.env_overrides},
        )
        return result.stdout + result.stderr, result.returncode

    def _run_streaming(self, metric: Metric, *, timeout: int) -> tuple[str, int]:
        process = subprocess.Popen(
            ["/bin/bash", "-lc", metric.command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=self.project_root,
            env={**environ, **self.env_overrides},
        )
        queue: Queue[tuple[str, str | None]] = Queue()
        chunks: list[str] = []

        def pump(stream, source: str) -> None:
            if stream is None:
                queue.put((source, None))
                return
            try:
                for line in iter(stream.readline, ""):
                    queue.put((source, line))
            finally:
                stream.close()
                queue.put((source, None))

        streams = {
            "stdout": process.stdout,
            "stderr": process.stderr,
        }
        threads = [
            Thread(target=pump, args=(stream, source), daemon=True)
            for source, stream in streams.items()
        ]
        for thread in threads:
            thread.start()

        closed_streams = 0
        deadline = time.monotonic() + timeout
        while closed_streams < len(threads):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.wait()
                raise subprocess.TimeoutExpired(metric.command, timeout)
            try:
                source, chunk = queue.get(timeout=min(0.1, remaining))
            except Empty:
                continue
            if chunk is None:
                closed_streams += 1
                continue
            chunks.append(chunk)
            self._emit_output(metric, source, chunk)

        returncode = process.wait(timeout=max(0.1, deadline - time.monotonic()))
        for thread in threads:
            thread.join(timeout=0.1)
        return "".join(chunks), returncode

    def _emit_output(self, metric: Metric, source: str, line: str) -> None:
        if self.output_callback is not None:
            self.output_callback(metric, source, line)

    def run_batch(
        self,
        metrics: list[Metric],
        *,
        parallel: bool = False,
        dry_run: bool = False,
        max_workers: int = 4,
        progress_callback: ProgressCallback | None = None,
    ) -> list[MetricResult]:
        """Execute multiple metrics, optionally in parallel.

        Results are returned in the same order as the input metrics.
        """
        if not parallel or dry_run:
            results = []
            for metric in metrics:
                self._emit_progress(progress_callback, "start", metric)
                result = self.run(metric, dry_run=dry_run)
                self._emit_progress(progress_callback, "end", metric, result)
                results.append(result)
            return results

        results: dict[int, MetricResult] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for i, metric in enumerate(metrics):
                self._emit_progress(progress_callback, "start", metric)
                futures[executor.submit(self.run, metric)] = (i, metric)
            for future in as_completed(futures):
                idx, metric = futures[future]
                result = future.result()
                self._emit_progress(progress_callback, "end", metric, result)
                results[idx] = result

        return [results[i] for i in range(len(metrics))]

    def _emit_progress(
        self,
        callback: ProgressCallback | None,
        event: str,
        metric: Metric,
        result: MetricResult | None = None,
    ) -> None:
        if callback is not None:
            callback(event, metric, result)
