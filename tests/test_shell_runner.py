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


def test_run_waived_metric():
    runner = ShellRunner(Path("/tmp"))
    metric = Metric(
        name="waived",
        command="exit 1",
        waiver=Waiver(reason="temporary waiver", expires_at=date.today() + timedelta(days=1)),
    )
    result = runner.run(metric)
    assert result.passed is True
    assert result.state == ResultState.WAIVED
    assert "temporary waiver" in result.output
