"""Visual reporters for fitness summaries."""

from __future__ import annotations

from importlib import import_module

from entrix.model import DimensionScore, FitnessReport

PASS_THRESHOLD = 90.0
WARN_THRESHOLD = 80.0


def _status_for_score(score: float, *, scorable: bool = True) -> str:
    if not scorable:
        return "INFO"
    if score >= PASS_THRESHOLD:
        return "PASS"
    if score >= WARN_THRESHOLD:
        return "WARN"
    return "BLOCK"


def _bar(score: float, *, width: int = 18, filled: str = "█", empty: str = "░") -> str:
    clamped = max(0.0, min(score, 100.0))
    count = round((clamped / 100.0) * width)
    return filled * count + empty * (width - count)


def _metric_summary(ds: DimensionScore) -> str:
    if ds.total == 0:
        return "n/a"
    return f"{ds.passed}/{ds.total}"


def _failing_metrics(report: FitnessReport) -> list[str]:
    failures: list[str] = []
    for ds in report.dimensions:
        for result in ds.results:
            if result.state and result.state.value == "fail":
                failures.append(result.metric_name)
    return failures


class AsciiReporter:
    """Render a compact scorecard using Unicode blocks."""

    def __init__(self, *, width: int = 18):
        self.width = width

    def report(self, report: FitnessReport) -> None:
        print("\nVISUAL SCORECARD")
        print("-" * 60)
        for ds in report.dimensions:
            scorable = ds.weight > 0 and ds.total > 0
            label = ds.dimension.upper()[:16].ljust(16)
            status = _status_for_score(ds.score, scorable=scorable)
            score_text = "n/a" if not scorable else f"{ds.score:5.1f}%"
            print(
                f"{label} {_bar(ds.score, width=self.width)} {score_text} "
                f"{status:<5} weight={ds.weight:>2}% metrics={_metric_summary(ds)}"
            )

        print("-" * 60)
        final_status = _status_for_score(report.final_score, scorable=bool(report.dimensions))
        print(f"FINAL SCORE      {_bar(report.final_score, width=self.width)} {report.final_score:5.1f}% {final_status}")
        if report.hard_gate_blocked:
            print("Hard gates are blocking this run.")
        elif report.score_blocked:
            print("Score is below the configured minimum threshold.")

        failures = _failing_metrics(report)
        if failures:
            print(f"Failing metrics: {', '.join(failures)}")


class RichReporter:
    """Render a richer scorecard when `rich` is available."""

    def __init__(self, *, width: int = 18):
        self.width = width

    def report(self, report: FitnessReport) -> None:
        rich = _load_rich()
        if rich is None:
            print("rich is not installed; falling back to ASCII scorecard. Install with `pip install entrix[visual]`.")
            AsciiReporter(width=self.width).report(report)
            return

        Console, Table, Text = rich
        console = Console()
        table = Table(title="Fitness Scorecard", show_lines=False)
        table.add_column("Dimension", style="bold")
        table.add_column("Score")
        table.add_column("Weight", justify="right")
        table.add_column("Metrics", justify="right")
        table.add_column("Status")

        for ds in report.dimensions:
            scorable = ds.weight > 0 and ds.total > 0
            status = _status_for_score(ds.score, scorable=scorable)
            color = _rich_color(status)
            score_text = "n/a" if not scorable else f"{ds.score:5.1f}%"
            bar = Text(_bar(ds.score, width=self.width), style=color)
            table.add_row(
                ds.dimension.upper(),
                Text.assemble(bar, f" {score_text}"),
                f"{ds.weight}%",
                _metric_summary(ds),
                Text(status, style=color),
            )

        console.print()
        console.print(table)
        console.print()
        final_status = _status_for_score(report.final_score, scorable=bool(report.dimensions))
        final_color = _rich_color(final_status)
        console.print(
            Text.assemble(
                ("FINAL SCORE ", "bold"),
                (_bar(report.final_score, width=self.width), final_color),
                (f" {report.final_score:5.1f}% {final_status}", final_color),
            )
        )
        failures = _failing_metrics(report)
        if failures:
            console.print(Text(f"Failing metrics: {', '.join(failures)}", style="red"))


def _rich_color(status: str) -> str:
    if status == "PASS":
        return "green"
    if status == "WARN":
        return "yellow"
    if status == "BLOCK":
        return "red"
    return "cyan"


def _load_rich():
    try:
        console_module = import_module("rich.console")
        table_module = import_module("rich.table")
        text_module = import_module("rich.text")
    except ImportError:
        return None
    return console_module.Console, table_module.Table, text_module.Text
