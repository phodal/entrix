"""Terminal reporter — colored output matching the original fitness.py format."""

from __future__ import annotations

from routa_fitness.model import DimensionScore, FitnessReport, MetricResult, ResultState


class TerminalReporter:
    """Prints fitness results to the terminal with emoji status indicators."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def print_header(
        self, *, dry_run: bool = False, tier: str | None = None, parallel: bool = False
    ) -> None:
        print("=" * 60)
        print("FITNESS FUNCTION REPORT")
        if dry_run:
            print("(DRY-RUN MODE)")
        if tier:
            print(f"(TIER: {tier.upper()})")
        if parallel:
            print("(PARALLEL MODE)")
        print("=" * 60)

    def print_dimension(self, ds: DimensionScore, *, show_tier: bool = False) -> None:
        print(f"\n## {ds.dimension.upper()} (weight: {ds.weight}%)")
        for result in ds.results:
            self._print_result(result, show_tier=show_tier)
        if ds.total > 0:
            print(f"   Score: {ds.score:.0f}%")

    def _print_result(self, result: MetricResult, *, show_tier: bool = False) -> None:
        status_labels = {
            ResultState.PASS: "\u2705 PASS",
            ResultState.FAIL: "\u274c FAIL",
            ResultState.UNKNOWN: "\u2753 UNKNOWN",
            ResultState.SKIPPED: "\u23ed\ufe0f SKIPPED",
            ResultState.WAIVED: "\u26a0\ufe0f WAIVED",
        }
        status = status_labels.get(result.state, "\u2753 UNKNOWN")
        hard = " [HARD GATE]" if result.hard_gate else ""
        tier_label = f" [{result.tier.value}]" if show_tier else ""

        print(f"   - {result.metric_name}: {status}{hard}{tier_label}")

        if result.state == ResultState.FAIL and (self.verbose or result.hard_gate):
            if result.output and result.output != f"TIMEOUT ({result.duration_ms:.0f}s)":
                lines = result.output.strip().split("\n")
                for line in lines[:10]:
                    print(f"     > {line}")
                if len(lines) > 10:
                    print(f"     > ... ({len(lines) - 10} more lines)")

    def print_footer(self, report: FitnessReport) -> None:
        print("\n" + "=" * 60)
        scored_dimensions = [ds for ds in report.dimensions if ds.weight > 0 and ds.total > 0]

        if report.hard_gate_blocked:
            failures = []
            for ds in report.dimensions:
                failures.extend(ds.hard_gate_failures)
            print(f"\u274c HARD GATES FAILED: {', '.join(failures)}")
            print("   Cannot proceed until hard gates pass.")
        elif report.dimensions and not scored_dimensions:
            print("FINAL SCORE: n/a")
            print("\u2705 PASS - No weighted metrics were scored in this run")
        elif report.dimensions:
            print(f"FINAL SCORE: {report.final_score:.1f}%")
            if report.score_blocked:
                print("\u274c BLOCK - Score too low")
            elif report.final_score >= 90:
                print("\u2705 PASS")
            elif report.final_score >= 80:
                print("\u26a0\ufe0f  WARN - Consider improvements")
            else:
                print("\u2705 PASS")

        print("=" * 60)

    def report(self, report: FitnessReport, *, show_tier: bool = False) -> None:
        """Print a complete fitness report."""
        for ds in report.dimensions:
            self.print_dimension(ds, show_tier=show_tier)
        self.print_footer(report)
