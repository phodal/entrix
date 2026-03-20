"""Tests for routa_fitness.cli."""

from routa_fitness.cli import _domains_from_files, _metric_domains, build_parser
from routa_fitness.engine import matches_changed_files
from routa_fitness.model import ExecutionScope, FitnessReport, Metric, MetricResult, ResultState, Tier
from routa_fitness.presets import get_project_preset
from routa_fitness.reporting import report_to_dict


def test_parser_run_defaults():
    parser = build_parser()
    args = parser.parse_args(["run"])
    assert args.command == "run"
    assert args.tier is None
    assert args.parallel is False
    assert args.dry_run is False
    assert args.verbose is False
    assert args.min_score == 80.0
    assert args.scope is None
    assert args.output is None
    assert args.changed_only is False
    assert args.files == []
    assert args.base == "HEAD"


def test_parser_run_all_flags():
    parser = build_parser()
    args = parser.parse_args(
        [
            "run",
            "--tier",
            "fast",
            "--parallel",
            "--dry-run",
            "--verbose",
            "--min-score",
            "65",
            "--scope",
            "staging",
            "--output",
            "report.json",
            "--changed-only",
            "--files",
            "src/app/page.tsx",
            "crates/routa-server/src/lib.rs",
            "--base",
            "HEAD~2",
        ]
    )
    assert args.tier == "fast"
    assert args.parallel is True
    assert args.dry_run is True
    assert args.verbose is True
    assert args.min_score == 65.0
    assert args.scope == "staging"
    assert args.output == "report.json"
    assert args.changed_only is True
    assert args.files == ["src/app/page.tsx", "crates/routa-server/src/lib.rs"]
    assert args.base == "HEAD~2"


def test_parser_validate():
    parser = build_parser()
    args = parser.parse_args(["validate"])
    assert args.command == "validate"


def test_parser_review_trigger_defaults():
    parser = build_parser()
    args = parser.parse_args(["review-trigger"])
    assert args.command == "review-trigger"
    assert args.base == "HEAD~1"
    assert args.config is None
    assert args.fail_on_trigger is False
    assert args.json is False
    assert args.files == []


def test_parser_review_trigger_flags():
    parser = build_parser()
    args = parser.parse_args(
        [
            "review-trigger",
            "--base",
            "main",
            "--config",
            "docs/fitness/review-triggers.yaml",
            "--fail-on-trigger",
            "--json",
            "src/core/acp/foo.ts",
        ]
    )
    assert args.command == "review-trigger"
    assert args.base == "main"
    assert args.config == "docs/fitness/review-triggers.yaml"
    assert args.fail_on_trigger is True
    assert args.json is True
    assert args.files == ["src/core/acp/foo.ts"]


def test_parser_graph_impact_defaults():
    parser = build_parser()
    args = parser.parse_args(["graph", "impact"])
    assert args.command == "graph"
    assert args.graph_command == "impact"
    assert args.base == "HEAD"
    assert args.depth == 2
    assert args.files == []


def test_parser_graph_test_radius_flags():
    parser = build_parser()
    args = parser.parse_args(
        ["graph", "test-radius", "--base", "HEAD~3", "--depth", "4", "--max-targets", "12", "src/a.ts"]
    )
    assert args.command == "graph"
    assert args.graph_command == "test-radius"
    assert args.base == "HEAD~3"
    assert args.depth == 4
    assert args.max_targets == 12
    assert args.files == ["src/a.ts"]


def test_parser_graph_query():
    parser = build_parser()
    args = parser.parse_args(["graph", "query", "tests_for", "MyService.run", "--json"])
    assert args.command == "graph"
    assert args.graph_command == "query"
    assert args.pattern == "tests_for"
    assert args.target == "MyService.run"
    assert args.json is True


def test_parser_graph_history():
    parser = build_parser()
    args = parser.parse_args(["graph", "history", "--count", "5", "--ref", "main"])
    assert args.command == "graph"
    assert args.graph_command == "history"
    assert args.count == 5
    assert args.ref == "main"


def test_parser_graph_review_context():
    parser = build_parser()
    args = parser.parse_args(
        [
            "graph",
            "review-context",
            "--base",
            "HEAD~2",
            "--head",
            "HEAD",
            "--depth",
            "3",
            "--max-targets",
            "10",
            "--max-files",
            "4",
            "--max-lines-per-file",
            "80",
            "--output",
            "-",
            "--files",
            "src/b.ts",
            "--no-source",
            "src/a.ts",
        ]
    )
    assert args.command == "graph"
    assert args.graph_command == "review-context"
    assert args.base == "HEAD~2"
    assert args.head == "HEAD"
    assert args.depth == 3
    assert args.max_targets == 10
    assert args.max_files == 4
    assert args.max_lines_per_file == 80
    assert args.output == "-"
    assert args.no_source is True
    assert args.files == ["src/b.ts"]
    assert args.files_positional == ["src/a.ts"]


def test_parser_no_command():
    parser = build_parser()
    args = parser.parse_args([])
    assert args.command is None


def test_parser_help_formats_without_error():
    parser = build_parser()
    help_text = parser.format_help()
    assert "routa-fitness" in help_text
    assert "validate" in help_text


def test_domains_from_files():
    domains = _domains_from_files(
        [
            "crates/routa-server/src/main.rs",
            "src/app/page.tsx",
            "tools/routa-fitness/routa_fitness/cli.py",
            "api-contract.yaml",
        ]
    )
    assert domains == {"rust", "web", "python", "config"}


def test_metric_domains():
    assert _metric_domains(Metric(name="a", command="cargo clippy --workspace")) == {"rust"}
    assert _metric_domains(Metric(name="b", command="npm run lint")) == {"web"}
    assert _metric_domains(Metric(name="c", command="python3 -m pytest")) == {"python"}
    assert _metric_domains(Metric(name="d", command="npm audit --audit-level=critical")) == {
        "web",
        "config",
    }


def test_metric_domains_prefers_explicit_scope():
    metric = Metric(name="a", command="echo ok", scope=["web", "rust"])
    assert _metric_domains(metric) == {"web", "rust"}


def test_matches_changed_files_uses_run_when_changed():
    metric = Metric(
        name="obs",
        command="echo ok",
        run_when_changed=["src/instrumentation.ts", "crates/routa-server/src/telemetry/**"],
    )
    preset = get_project_preset()
    assert matches_changed_files(metric, ["src/instrumentation.ts"], set(), preset) is True
    assert matches_changed_files(metric, ["src/app/page.tsx"], {"web"}, preset) is False


def test_matches_changed_files_falls_back_to_domains():
    metric = Metric(name="lint", command="npm run lint", execution_scope=ExecutionScope.LOCAL)
    assert matches_changed_files(metric, ["src/app/page.tsx"], {"web"}, get_project_preset()) is True


def test_report_to_dict_includes_result_state():
    report = FitnessReport(
        final_score=100.0,
        dimensions=[],
    )
    report.dimensions.append(
        type("DimensionScoreStub", (), {
            "dimension": "quality",
            "weight": 100,
            "score": 100.0,
            "passed": 1,
            "total": 1,
            "hard_gate_failures": [],
            "results": [
                MetricResult(
                    metric_name="lint",
                    passed=True,
                    output="ok",
                    tier=Tier.FAST,
                    state=ResultState.WAIVED,
                )
            ],
        })()
    )
    payload = report_to_dict(report)
    assert payload["dimensions"][0]["results"][0]["state"] == "waived"
