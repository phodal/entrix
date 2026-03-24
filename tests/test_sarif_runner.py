"""Tests for entrix.runners.sarif."""

from pathlib import Path

from entrix.model import Metric, ResultState
from entrix.runners.sarif import SarifRunner


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_sarif_runner_passes_when_no_error_results(tmp_path: Path):
    _write(
        tmp_path / "reports" / "ok.sarif",
        """{
  "version": "2.1.0",
  "runs": [
    {
      "results": [
        {"level": "warning"},
        {"level": "note"}
      ]
    }
  ]
}""",
    )
    runner = SarifRunner(tmp_path)
    result = runner.run(Metric(name="sarif_ok", command="reports/ok.sarif"))

    assert result.passed is True
    assert result.state == ResultState.PASS
    assert "sarif_errors=0" in result.output
    assert "sarif_warnings=1" in result.output
    assert "sarif_notes=1" in result.output


def test_sarif_runner_fails_when_error_results_exist(tmp_path: Path):
    _write(
        tmp_path / "reports" / "fail.sarif",
        """{
  "version": "2.1.0",
  "runs": [
    {
      "results": [
        {"level": "error"},
        {"level": "warning"}
      ]
    }
  ]
}""",
    )
    runner = SarifRunner(tmp_path)
    result = runner.run(Metric(name="sarif_fail", command="reports/fail.sarif"))

    assert result.passed is False
    assert result.state == ResultState.FAIL
    assert "sarif_errors=1" in result.output


def test_sarif_runner_uses_pattern_for_custom_policy(tmp_path: Path):
    _write(
        tmp_path / "reports" / "warn.sarif",
        """{
  "version": "2.1.0",
  "runs": [
    {"results": [{"level": "warning"}]}
  ]
}""",
    )
    runner = SarifRunner(tmp_path)
    result = runner.run(
        Metric(
            name="sarif_pattern",
            command="reports/warn.sarif",
            pattern=r"sarif_warnings=0",
        )
    )

    assert result.passed is False
    assert result.state == ResultState.FAIL


def test_sarif_runner_returns_unknown_for_invalid_payload(tmp_path: Path):
    _write(tmp_path / "reports" / "broken.sarif", "{ not-json")
    runner = SarifRunner(tmp_path)
    result = runner.run(Metric(name="sarif_unknown", command="reports/broken.sarif"))

    assert result.passed is False
    assert result.state == ResultState.UNKNOWN
    assert "SARIF parse error" in result.output

