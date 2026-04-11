"""Terminal reporter — colored output matching the original fitness.py format."""

from __future__ import annotations

from entrix.model import DimensionScore, FitnessReport, MetricResult, ResultState


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

    def print_metric_progress(
        self,
        event: str,
        *,
        metric_name: str,
        tier: str,
        hard_gate: bool,
        result: MetricResult | None = None,
    ) -> None:
        hard = " [HARD GATE]" if hard_gate else ""
        tier_label = f" [{tier}]"
        if event == "start":
            print(f"[RUNNING] {metric_name}{hard}{tier_label}")
            return

        status_labels = {
            ResultState.PASS: "PASS",
            ResultState.FAIL: "FAIL",
            ResultState.UNKNOWN: "UNKNOWN",
            ResultState.SKIPPED: "SKIPPED",
            ResultState.WAIVED: "WAIVED",
        }
        status = status_labels.get(result.state if result else None, "UNKNOWN")
        duration = f" in {result.duration_ms / 1000:.1f}s" if result and result.duration_ms > 0 else ""
        print(f"[DONE] {metric_name}: {status}{hard}{tier_label}{duration}")

    def print_metric_output(self, *, metric_name: str, source: str, line: str) -> None:
        text = line.rstrip()
        if not text:
            return
        print(f"[LOG][{source}] {metric_name}: {text}")

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

        # Annotate infrastructure errors distinctly so developers know the
        # checker itself is broken, not their code.
        infra_tag = ""
        if result.is_infra_error:
            infra_tag = " [INFRA ERROR]"

        print(f"   - {result.metric_name}: {status}{hard}{tier_label}{infra_tag}")

        if result.state in (ResultState.FAIL, ResultState.UNKNOWN) and (self.verbose or result.hard_gate or result.is_infra_error):
            if result.output and result.output != f"TIMEOUT ({result.duration_ms:.0f}s)":
                lines = result.output.strip().split("\n")
                # Show head + tail of output so both context and verdict are visible
                max_head = 20
                max_tail = 30
                if len(lines) <= max_head + max_tail:
                    for line in lines:
                        print(f"     > {line}")
                else:
                    for line in lines[:max_head]:
                        print(f"     > {line}")
                    omitted = len(lines) - max_head - max_tail
                    print(f"     > ... ({omitted} lines omitted) ...")
                    for line in lines[-max_tail:]:
                        print(f"     > {line}")

    def print_footer(self, report: FitnessReport) -> None:
        print("\n" + "=" * 60)
        scored_dimensions = [ds for ds in report.dimensions if ds.weight > 0 and ds.total > 0]

        # Collect infrastructure errors across all dimensions
        infra_errors = []
        for ds in report.dimensions:
            for r in ds.results:
                if r.is_infra_error:
                    infra_errors.append(r.metric_name)

        if infra_errors:
            print(f"\u26a0\ufe0f  INFRA ERRORS: {', '.join(infra_errors)}")
            print("   These failures are likely checker/tooling problems, not code defects.")

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
