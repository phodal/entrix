"""Tests for entrix.runners.shell."""

from datetime import date, timedelta
from pathlib import Path

from entrix.model import Metric, ResultState, Waiver
from entrix.runners.shell import ShellRunner


def test_dry_run():
    runner = ShellRunner(Path("/tmp"))
    m = Metric(name="test", command="echo hello")
    result = runner.run(m, dry_run=True)
    assert result.passed is True
    assert "[DRY-RUN]" in result.output
    assert result.metric_name == "test"


def test_run_success_exit_code():
    runner = ShellRunner(Path("/tmp"))
    m = Metric(name="echo_test", command="echo ok")
    result = runner.run(m)
    assert result.passed is True
    assert "ok" in result.output


def test_run_failure_exit_code():
    runner = ShellRunner(Path("/tmp"))
    m = Metric(name="fail_test", command="exit 1")
    result = runner.run(m)
    assert result.passed is False


def test_run_pattern_match():
    runner = ShellRunner(Path("/tmp"))
    m = Metric(name="pattern_test", command="echo 'Tests 42 passed'", pattern=r"Tests\s+\d+\s+passed")
    result = runner.run(m)
    assert result.passed is True


def test_run_pattern_no_match():
    runner = ShellRunner(Path("/tmp"))
    m = Metric(name="pattern_fail", command="echo 'Tests 0 failed'", pattern=r"Tests\s+\d+\s+passed")
    result = runner.run(m)
    assert result.passed is False


def test_run_timeout():
    runner = ShellRunner(Path("/tmp"), timeout=1)
    m = Metric(name="slow", command="sleep 10")
    result = runner.run(m)
    assert result.passed is False
    assert "TIMEOUT" in result.output


def test_run_metric_specific_timeout():
    runner = ShellRunner(Path("/tmp"), timeout=5)
    m = Metric(name="slow", command="sleep 2", timeout_seconds=1)
    result = runner.run(m)
    assert result.passed is False
    assert "TIMEOUT (1s)" in result.output


def test_run_hard_gate_preserved():
    runner = ShellRunner(Path("/tmp"))
    m = Metric(name="gate", command="echo ok", hard_gate=True)
    result = runner.run(m)
    assert result.hard_gate is True


def test_run_batch_serial():
    runner = ShellRunner(Path("/tmp"))
    metrics = [
        Metric(name="a", command="echo a"),
        Metric(name="b", command="echo b"),
    ]
    results = runner.run_batch(metrics)
    assert len(results) == 2
    assert results[0].metric_name == "a"
    assert results[1].metric_name == "b"


def test_run_batch_parallel():
    runner = ShellRunner(Path("/tmp"))
    metrics = [
        Metric(name="a", command="echo a"),
        Metric(name="b", command="echo b"),
    ]
    results = runner.run_batch(metrics, parallel=True)
    assert len(results) == 2
    # Order preserved
    assert results[0].metric_name == "a"
    assert results[1].metric_name == "b"


def test_run_batch_dry_run():
    runner = ShellRunner(Path("/tmp"))
    metrics = [Metric(name="x", command="rm -rf /")]
    results = runner.run_batch(metrics, dry_run=True)
    assert results[0].passed is True
    assert "[DRY-RUN]" in results[0].output


def test_run_batch_emits_progress_events():
    runner = ShellRunner(Path("/tmp"))
    metrics = [Metric(name="a", command="echo a"), Metric(name="b", command="echo b")]
    events: list[tuple[str, str, str | None]] = []

    def capture(event: str, metric: Metric, result) -> None:
        events.append((event, metric.name, None if result is None else result.state.value))

    runner.run_batch(metrics, progress_callback=capture)

    assert events == [
        ("start", "a", None),
        ("end", "a", "pass"),
        ("start", "b", None),
        ("end", "b", "pass"),
    ]


def test_run_streams_output_lines_to_callback():
    emitted: list[tuple[str, str, str]] = []
    runner = ShellRunner(
        Path("/tmp"),
        stream_output=True,
        output_callback=lambda metric, source, line: emitted.append((metric.name, source, line.strip())),
    )
    metric = Metric(name="streamed", command="printf 'hello\\n'; printf 'oops\\n' >&2")

    result = runner.run(metric)

    assert result.passed is True
    assert "hello" in result.output
    assert "oops" in result.output
    assert ("streamed", "stdout", "hello") in emitted
    assert ("streamed", "stderr", "oops") in emitted


def test_run_waived_metric():
    runner = ShellRunner(Path("/tmp"))
    metric = Metric(
        name="waived",
        command="exit 1",
        waiver=Waiver(reason="temporary waiver", expires_at=date.today() + timedelta(days=1)),
    )
    result = runner.run(metric)
    assert result.passed is True


# === Fix 1: ANSI escape codes don't cause false failures ===

def test_run_pattern_match_with_ansi_codes():
    """Pattern matching should work correctly even when output contains ANSI color codes."""
    runner = ShellRunner(Path("/tmp"))
    m = Metric(
        name="ansi_test",
        command=r"printf '\033[1m\033[32mTests  1236 passed\033[39m\033[22m'",
        pattern=r"Tests\s+\d+\s+passed",
    )
    result = runner.run(m)
    assert result.passed is True
    assert result.state == ResultState.PASS


# === Fix 1: Exit-code-first hybrid judgment ===

def test_run_pattern_exit_code_nonzero_overrides_pattern():
    """Even if the pattern is found, a non-zero exit code means failure."""
    runner = ShellRunner(Path("/tmp"))
    m = Metric(
        name="exit_override",
        command="echo 'Tests 42 passed' && exit 1",
        pattern=r"Tests\s+\d+\s+passed",
    )
    result = runner.run(m)
    assert result.passed is False


# === Fix 2: Output stored with ANSI stripped ===

def test_output_is_ansi_stripped():
    """Stored output should have ANSI codes removed for clean display."""
    runner = ShellRunner(Path("/tmp"))
    m = Metric(name="ansi_strip", command=r"printf '\033[31mred text\033[0m'")
    result = runner.run(m)
    assert "\x1b" not in result.output
    assert "red text" in result.output


# === Fix 2: Smart truncation keeps head and tail ===

def test_output_smart_truncation_preserves_tail():
    """Long output should keep both head and tail, not just first N chars."""
    runner = ShellRunner(Path("/tmp"))
    # Generate output with a distinctive marker at the end
    m = Metric(
        name="truncation_test",
        command="for i in $(seq 1 500); do echo 'filler line $i'; done; echo 'FINAL_VERDICT: ok'",
    )
    result = runner.run(m)
    # The tail should be preserved
    assert "FINAL_VERDICT: ok" in result.output


# === Fix 5: returncode is stored on MetricResult ===

def test_result_stores_returncode():
    """MetricResult should store the process exit code."""
    runner = ShellRunner(Path("/tmp"))
    m = Metric(name="rc_test", command="exit 42")
    result = runner.run(m)
    assert result.returncode == 42
    assert result.passed is False


# === Fix 6: Distinguish checker infra errors ===

def test_infra_error_when_both_exit_and_pattern_fail():
    """When exit code != 0 AND pattern not found, result should be UNKNOWN (infra error)."""
    runner = ShellRunner(Path("/tmp"))
    m = Metric(
        name="infra_fail",
        command="echo 'ENOENT: no such file' && exit 1",
        pattern=r"Tests\s+\d+\s+passed",
    )
    result = runner.run(m)
    assert result.passed is False
    assert result.state == ResultState.UNKNOWN
    assert result.is_infra_error is True


def test_product_failure_when_exit_ok_but_pattern_fails():
    """When exit code is 0 but pattern not found, it's a real failure (not infra)."""
    runner = ShellRunner(Path("/tmp"))
    m = Metric(
        name="product_fail",
        command="echo 'Tests 0 failed'",
        pattern=r"Tests\s+\d+\s+passed",
    )
    result = runner.run(m)
    assert result.passed is False
    assert result.state == ResultState.FAIL
    assert result.is_infra_error is False
