"""Tests for entrix.cli."""

import argparse
from pathlib import Path

from entrix.cli import _domains_from_files, _metric_domains, build_parser, cmd_analyze_long_file, cmd_run
from entrix.engine import matches_changed_files
from entrix.model import ExecutionScope, FitnessReport, Metric, MetricResult, ResultState, Tier
from entrix.presets import get_project_preset
from entrix.reporting import report_to_dict


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
    assert args.dimension == []
    assert args.metric == []


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
            "--dimension",
            "code_quality",
            "--dimension",
            "testability",
            "--metric",
            "eslint_pass",
            "--metric",
            "ts_typecheck_pass",
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
    assert args.dimension == ["code_quality", "testability"]
    assert args.metric == ["eslint_pass", "ts_typecheck_pass"]


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


def test_parser_hook_file_length_flags():
    parser = build_parser()
    args = parser.parse_args(
        [
            "hook",
            "file-length",
            "--config",
            "tools/entrix/file_budgets.pre_commit.json",
            "--staged-only",
            "--strict-limit",
            "src/app/page.tsx",
        ]
    )
    assert args.command == "hook"
    assert args.hook_command == "file-length"
    assert args.config == "tools/entrix/file_budgets.pre_commit.json"
    assert args.staged_only is True
    assert args.strict_limit is True
    assert args.files == ["src/app/page.tsx"]


def test_parser_analyze_long_file_flags():
    parser = build_parser()
    args = parser.parse_args(
        [
            "analyze",
            "long-file",
            "--files",
            "src/a.ts",
            "src/b.py",
            "--base",
            "HEAD~2",
            "--config",
            "tools/entrix/file_budgets.json",
            "--strict-limit",
            "--min-lines",
            "80",
            "--comment-review-commit-threshold",
            "9",
            "--json",
        ]
    )
    assert args.command == "analyze"
    assert args.analyze_command == "long-file"
    assert args.files == ["src/a.ts", "src/b.py"]
    assert args.base == "HEAD~2"
    assert args.config == "tools/entrix/file_budgets.json"
    assert args.strict_limit is True
    assert args.min_lines == 80
    assert args.comment_review_commit_threshold == 9
    assert args.json is True


def test_parser_analyze_long_file_positional_paths():
    parser = build_parser()
    args = parser.parse_args(
        [
            "analyze",
            "long-file",
            "src/a.ts",
            "src/b.py",
        ]
    )
    assert args.command == "analyze"
    assert args.analyze_command == "long-file"
    assert args.paths == ["src/a.ts", "src/b.py"]
    assert args.files == []


def test_parser_analyze_long_file_supports_positional_and_flagged_files():
    parser = build_parser()
    args = parser.parse_args(
        [
            "analyze",
            "long-file",
            "src/a.ts",
            "--files",
            "src/b.py",
            "src/c.rs",
        ]
    )
    assert args.paths == ["src/a.ts"]
    assert args.files == ["src/b.py", "src/c.rs"]


def test_cmd_analyze_long_file_merges_positional_and_flagged_files(monkeypatch):
    captured = {}

    monkeypatch.setattr("entrix.cli._find_project_root", lambda: ".")

    def fake_analyze_long_files(*_args, **kwargs):
        captured["files"] = kwargs["files"]
        return {"status": "ok", "base": "HEAD", "files": []}

    monkeypatch.setattr("entrix.cli.analyze_long_files", fake_analyze_long_files)
    monkeypatch.setattr("entrix.cli._print_long_file_analysis", lambda *_args, **_kwargs: None)

    args = argparse.Namespace(
        files=["src/b.py", "src/a.ts"],
        paths=["src/a.ts", "src/c.rs"],
        config=None,
        base="HEAD",
        strict_limit=False,
        comment_review_commit_threshold=5,
        json=False,
        min_lines=60,
    )

    exit_code = cmd_analyze_long_file(args)

    assert exit_code == 0
    assert captured["files"] == ["src/b.py", "src/a.ts", "src/c.rs"]


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
    assert "entrix" in help_text
    assert "validate" in help_text


def test_domains_from_files():
    domains = _domains_from_files(
        [
            "crates/routa-server/src/main.rs",
            "src/app/page.tsx",
            "tools/entrix/entrix/cli.py",
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


def test_cmd_run_defaults_scope_to_local(monkeypatch):
    captured = {}

    monkeypatch.setattr("entrix.cli._find_project_root", lambda: Path("/tmp"))
    monkeypatch.setattr("entrix.cli._find_fitness_dir", lambda _project_root: Path("/tmp/docs/fitness"))
    monkeypatch.setattr("entrix.cli.get_project_preset", lambda: object())
    monkeypatch.setattr("entrix.cli._collect_run_files", lambda _args, _project_root: [])
    monkeypatch.setattr(
        "entrix.cli.run_fitness_report",
        lambda _project_root, policy, _preset, **_kwargs: (
            captured.setdefault("execution_scope", policy.execution_scope),
            [],
        ),
    )
    monkeypatch.setattr("entrix.cli.write_report_output", lambda *_args, **_kwargs: None)

    args = argparse.Namespace(
        tier=None,
        scope=None,
        parallel=False,
        dry_run=False,
        verbose=False,
        min_score=80.0,
        dimension=[],
        metric=[],
        output=None,
        changed_only=False,
        files=[],
        base="HEAD",
    )

    exit_code = cmd_run(args)

    assert exit_code == 0
    assert captured["execution_scope"] == ExecutionScope.LOCAL
