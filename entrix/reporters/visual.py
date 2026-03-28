"""Visual reporters for fitness summaries."""

from __future__ import annotations

from importlib import import_module
from typing import TextIO

from entrix.model import Dimension, DimensionScore, FitnessReport, Metric, MetricResult, ResultState

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


class RichLiveProgressReporter:
    """TTY live progress reporter modeled after hook-runtime's rolling dashboard."""

    def __init__(self, *, stream: TextIO, tail_lines: int = 6):
        self.stream = stream
        self.tail_lines = tail_lines
        self._states: dict[str, dict] = {}
        self._order: list[str] = []
        self._tail: list[str] = []
        self._live = None
        self._console = None
        self._rich = _load_rich_live()

    def setup(self, dimensions: list[Dimension]) -> None:
        for dimension in dimensions:
            for metric in dimension.metrics:
                self._order.append(metric.name)
                self._states[metric.name] = {
                    "metric": metric,
                    "status": "queued",
                    "duration_ms": None,
                }

        if self._rich is None:
            return

        Console, Live = self._rich["Console"], self._rich["Live"]
        self._console = Console(file=self.stream)
        self._live = Live(self._renderable(), console=self._console, refresh_per_second=8, transient=False)
        self._live.start()

    def handle_progress(self, event: str, metric: Metric, result: MetricResult | None) -> None:
        state = self._states.get(metric.name)
        if state is None:
            return
        if event == "start":
            state["status"] = "running"
            self._refresh()
            return

        status = "passed"
        if result is not None:
            status_map = {
                ResultState.PASS: "passed",
                ResultState.FAIL: "failed",
                ResultState.UNKNOWN: "unknown",
                ResultState.SKIPPED: "skipped",
                ResultState.WAIVED: "waived",
            }
            status = status_map.get(result.state, "unknown")
            state["duration_ms"] = result.duration_ms
            if result.output and result.state in {ResultState.FAIL, ResultState.SKIPPED, ResultState.UNKNOWN}:
                for line in result.output.strip().splitlines()[:3]:
                    self._append_tail(metric.name, line)
        state["status"] = status
        self._refresh()

    def close(self) -> None:
        if self._live is not None:
            self._live.update(self._renderable(), refresh=True)
            self._live.stop()
            self._live = None

    def snapshot_lines(self) -> list[str]:
        counts = {"queued": 0, "running": 0, "passed": 0, "failed": 0, "skipped": 0, "waived": 0, "unknown": 0}
        for state in self._states.values():
            counts[state["status"]] += 1
        lines = [
            (
                f"[fitness] {counts['passed']} passed | {counts['failed']} failed | "
                f"{counts['running']} running | {counts['queued']} queued"
            )
        ]
        for idx, metric_name in enumerate(self._order, start=1):
            state = self._states[metric_name]
            duration = (
                f" {state['duration_ms'] / 1000:.1f}s"
                if state["duration_ms"] is not None
                else ""
            )
            lines.append(f"[{idx}/{len(self._order)}] {state['status'].upper()} {metric_name}{duration}")
        if self._tail:
            lines.append("[fitness tail]")
            lines.extend(self._tail)
        return lines

    def _append_tail(self, metric_name: str, line: str) -> None:
        self._tail.append(f"[{metric_name}] {line}".rstrip())
        if len(self._tail) > self.tail_lines:
            self._tail = self._tail[-self.tail_lines :]

    def _refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._renderable(), refresh=True)

    def _renderable(self):
        if self._rich is None:
            return None
        Table, Text, Group, Panel = (
            self._rich["Table"],
            self._rich["Text"],
            self._rich["Group"],
            self._rich["Panel"],
        )
        counts = {"queued": 0, "running": 0, "passed": 0, "failed": 0, "skipped": 0, "waived": 0, "unknown": 0}
        for state in self._states.values():
            counts[state["status"]] += 1

        summary = Text.assemble(
            ("[fitness] ", "bold"),
            (f"{counts['passed']} passed", "green"),
            (" | ", ""),
            (f"{counts['failed']} failed", "red"),
            (" | ", ""),
            (f"{counts['running']} running", "blue"),
            (" | ", ""),
            (f"{counts['queued']} queued", "yellow"),
        )

        table = Table(show_header=True, header_style="bold", expand=True)
        table.add_column("#", justify="right", width=4)
        table.add_column("Metric")
        table.add_column("State", width=10)
        table.add_column("Tier", width=8)
        table.add_column("Time", justify="right", width=8)
        for idx, metric_name in enumerate(self._order, start=1):
            state = self._states[metric_name]
            metric = state["metric"]
            table.add_row(
                str(idx),
                metric.name,
                _status_text(state["status"], Text),
                metric.tier.value,
                "" if state["duration_ms"] is None else f"{state['duration_ms'] / 1000:.1f}s",
            )

        renderables = [summary, table]
        if self._tail:
            renderables.append(Panel("\n".join(self._tail), title="fitness tail", border_style="yellow"))
        return Group(*renderables)


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


def _load_rich_live():
    try:
        console_module = import_module("rich.console")
        live_module = import_module("rich.live")
        table_module = import_module("rich.table")
        text_module = import_module("rich.text")
        panel_module = import_module("rich.panel")
    except ImportError:
        return None
    return {
        "Console": console_module.Console,
        "Group": console_module.Group,
        "Live": live_module.Live,
        "Panel": panel_module.Panel,
        "Table": table_module.Table,
        "Text": text_module.Text,
    }


def _status_text(status: str, Text):
    color_map = {
        "queued": "yellow",
        "running": "blue",
        "passed": "green",
        "failed": "red",
        "skipped": "yellow",
        "waived": "yellow",
        "unknown": "cyan",
    }
    label_map = {
        "queued": "WAIT",
        "running": "RUN",
        "passed": "PASS",
        "failed": "FAIL",
        "skipped": "SKIP",
        "waived": "WAIVE",
        "unknown": "UNK",
    }
    return Text(label_map[status], style=color_map[status])
