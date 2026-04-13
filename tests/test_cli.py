"""Tests for entrix.cli."""

import argparse
import hashlib
import json
from pathlib import Path

from entrix.cli import (
    _ShellOutputController,
    _domains_from_files,
    _metric_domains,
    build_parser,
    cmd_analyze_long_file,
    cmd_hook_file_length,
    cmd_graph_test_mapping,
    cmd_run,
)
from entrix.file_budgets import FileBudgetViolation
from entrix.engine import matches_changed_files
from entrix.reporters.terminal import TerminalReporter
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
    assert args.stream == "failures"
    assert args.format == "text"
    assert args.progress_refresh == 4
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
            "--stream",
            "all",
            "--format",
            "rich",
            "--progress-refresh",
            "8",
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
    assert args.stream == "all"
    assert args.format == "rich"
    assert args.progress_refresh == 8
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


def test_parser_run_stream_without_value_defaults_to_all():
    parser = build_parser()
    args = parser.parse_args(["run", "--stream"])
    assert args.stream == "all"


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


def test_parser_release_trigger_defaults():
    parser = build_parser()
    args = parser.parse_args(["release-trigger", "--manifest", "dist/release/manifest.json"])
    assert args.command == "release-trigger"
    assert args.manifest == "dist/release/manifest.json"
    assert args.baseline_manifest is None
    assert args.base == "HEAD~1"
    assert args.config is None
    assert args.fail_on_trigger is False
    assert args.json is False
    assert args.files == []


def test_parser_release_trigger_flags():
    parser = build_parser()
    args = parser.parse_args(
        [
            "release-trigger",
            "--manifest",
            "dist/release/manifest.json",
            "--baseline-manifest",
            "dist/release/baseline.json",
            "--base",
            "main",
            "--config",
            "docs/fitness/release-triggers.yaml",
            "--fail-on-trigger",
            "--json",
            "scripts/release/stage-routa-cli-npm.mjs",
        ]
    )
    assert args.command == "release-trigger"
    assert args.manifest == "dist/release/manifest.json"
    assert args.baseline_manifest == "dist/release/baseline.json"
    assert args.base == "main"
    assert args.config == "docs/fitness/release-triggers.yaml"
    assert args.fail_on_trigger is True
    assert args.json is True
    assert args.files == ["scripts/release/stage-routa-cli-npm.mjs"]


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


def test_cmd_hook_file_length_prints_structure_summary(monkeypatch, capsys, tmp_path):
    config = object()
    violation = FileBudgetViolation(
        path="src/app.ts",
        line_count=1201,
        max_lines=1000,
        reason="legacy hotspot",
    )

    monkeypatch.setattr("entrix.cli._find_project_root", lambda: tmp_path)
    monkeypatch.setattr("entrix.cli.load_config", lambda _path: config)
    monkeypatch.setattr("entrix.cli.evaluate_paths", lambda *_args, **_kwargs: [violation])
    monkeypatch.setattr(
        "entrix.cli.is_tracked_source_file",
        lambda path, loaded_config: loaded_config is config and path == "src/app.ts",
    )
    monkeypatch.setattr(
        "entrix.cli.analyze_long_files",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "files": [
                {
                    "filePath": "src/app.ts",
                    "status": "ok",
                    "classes": [
                        {
                            "name": "AppController",
                            "startLine": 10,
                            "endLine": 120,
                            "lineCount": 111,
                            "methodCount": 2,
                            "methods": [
                                {
                                    "name": "handleRequest",
                                    "startLine": 20,
                                    "endLine": 80,
                                    "lineCount": 61,
                                },
                                {
                                    "name": "renderView",
                                    "startLine": 82,
                                    "endLine": 110,
                                    "lineCount": 29,
                                },
                            ],
                        }
                    ],
                    "functions": [
                        {
                            "name": "bootstrap",
                            "startLine": 130,
                            "endLine": 170,
                            "lineCount": 41,
                        }
                    ],
                    "warnings": [],
                }
            ],
        },
    )

    args = argparse.Namespace(
        config=str(tmp_path / "file_budgets.json"),
        files=["src/app.ts"],
        staged_only=False,
        strict_limit=False,
        base="HEAD",
    )

    exit_code = cmd_hook_file_length(args)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "file_budget_checked: 1" in out
    assert "file_budget_violations: 1" in out
    assert "current file length 1201 exceeds limit 1000: src/app.ts | legacy hotspot" in out
    assert "Refactor the oversized file before commit." in out
    assert "Structure summary (tree-sitter symbols):" in out
    assert "- src/app.ts" in out
    assert "class AppController (L10-120, 111, methods=2)" in out
    assert "method handleRequest (L20-80, 61)" in out
    assert "functions: bootstrap (L130-170, 41)" in out


def test_cmd_hook_file_length_handles_unavailable_structure_summary(
    monkeypatch,
    capsys,
    tmp_path,
):
    config = object()
    violation = FileBudgetViolation(
        path="src/app.ts",
        line_count=1201,
        max_lines=1000,
    )

    monkeypatch.setattr("entrix.cli._find_project_root", lambda: tmp_path)
    monkeypatch.setattr("entrix.cli.load_config", lambda _path: config)
    monkeypatch.setattr("entrix.cli.evaluate_paths", lambda *_args, **_kwargs: [violation])
    monkeypatch.setattr(
        "entrix.cli.is_tracked_source_file",
        lambda path, loaded_config: loaded_config is config and path == "src/app.ts",
    )
    monkeypatch.setattr(
        "entrix.cli.analyze_long_files",
        lambda *_args, **_kwargs: {
            "status": "unavailable",
            "summary": "long-file analysis requires tree-sitter-language-pack",
            "files": [],
        },
    )

    args = argparse.Namespace(
        config=str(tmp_path / "file_budgets.json"),
        files=["src/app.ts"],
        staged_only=False,
        strict_limit=False,
        base="HEAD",
    )

    exit_code = cmd_hook_file_length(args)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert (
        "Structure summary unavailable: long-file analysis requires tree-sitter-language-pack"
        in out
    )


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


def test_parser_graph_test_mapping_flags():
    parser = build_parser()
    args = parser.parse_args(
        [
            "graph",
            "test-mapping",
            "--base",
            "HEAD~2",
            "--build-mode",
            "skip",
            "--no-graph",
            "--fail-on-missing",
            "--json",
            "src/a.ts",
        ]
    )
    assert args.command == "graph"
    assert args.graph_command == "test-mapping"
    assert args.base == "HEAD~2"
    assert args.build_mode == "skip"
    assert args.no_graph is True
    assert args.fail_on_missing is True
    assert args.json is True
    assert args.files == ["src/a.ts"]


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
        stream="off",
        progress_refresh=4,
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


def test_cmd_run_emits_runtime_fitness_event(tmp_path, monkeypatch):
    dimension = type("Dimension", (), {"name": "testability", "weight": 18, "source_file": "docs/fitness/unit-test.md"})()
    report = FitnessReport(
        final_score=97.0,
        hard_gate_blocked=False,
        score_blocked=False,
        dimensions=[
            type("DimensionReport", (), {
                "dimension": "testability",
                "weight": 18,
                "passed": 1,
                "total": 1,
                "score": 97.0,
                "hard_gate_failures": [],
                "results": [
                    MetricResult(
                        metric_name="eslint_pass",
                        passed=True,
                        output="ok",
                        tier=Tier.FAST,
                        state=ResultState.PASS,
                    )
                ]
            })()
        ],
    )

    monkeypatch.setattr("entrix.cli._find_project_root", lambda: tmp_path)
    monkeypatch.setattr("entrix.cli._find_fitness_dir", lambda _project_root: tmp_path / "docs" / "fitness")
    monkeypatch.setattr("entrix.cli.get_project_preset", lambda: object())
    monkeypatch.setattr("entrix.cli._collect_run_files", lambda _args, _project_root: [])
    monkeypatch.setattr("entrix.cli.run_fitness_report", lambda *_args, **_kwargs: (report, [dimension]))
    monkeypatch.setattr("entrix.cli.enforce", lambda _report, _policy: 0)
    monkeypatch.setattr("entrix.cli.write_report_output", lambda *_args, **_kwargs: None)

    args = argparse.Namespace(
        tier="fast",
        scope=None,
        parallel=False,
        dry_run=False,
        verbose=False,
        stream="off",
        format="text",
        progress_refresh=4,
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
    runtime_root = Path("/tmp") / "harness-monitor" / "runtime" / hashlib.sha256(str(tmp_path).encode("utf-8")).hexdigest()
    event_path = runtime_root / "events.jsonl"
    payload = json.loads(event_path.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert payload["type"] == "fitness"
    assert payload["mode"] == "fast"
    assert payload["status"] == "passed"
    assert payload["final_score"] == 97.0
    assert payload["artifact_path"]

    artifact_path = Path(payload["artifact_path"])
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["mode"] == "fast"
    assert artifact["final_score"] == 97.0

    mailbox_dir = runtime_root / "mailbox" / "fitness" / "new"
    mailbox_messages = sorted(mailbox_dir.glob("*.json"))
    assert mailbox_messages


def test_cmd_graph_test_mapping_returns_non_zero_when_missing(monkeypatch):
    monkeypatch.setattr("entrix.cli._find_project_root", lambda: Path("/tmp/project"))
    monkeypatch.setattr(
        "entrix.cli.analyze_test_mappings",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "status_counts": {"missing": 1},
            "mappings": [],
        },
    )

    args = argparse.Namespace(
        files=["src/demo.ts"],
        base="HEAD",
        build_mode="auto",
        no_graph=True,
        fail_on_missing=True,
        json=True,
    )

    exit_code = cmd_graph_test_mapping(args)

    assert exit_code == 2


def test_cmd_graph_test_mapping_allows_missing_when_flag_disabled(monkeypatch):
    monkeypatch.setattr("entrix.cli._find_project_root", lambda: Path("/tmp/project"))
    monkeypatch.setattr(
        "entrix.cli.analyze_test_mappings",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "status_counts": {"missing": 2},
            "mappings": [],
        },
    )

    args = argparse.Namespace(
        files=["src/demo.ts"],
        base="HEAD",
        build_mode="auto",
        no_graph=True,
        fail_on_missing=False,
        json=True,
    )

    exit_code = cmd_graph_test_mapping(args)

    assert exit_code == 0


def test_shell_output_controller_streams_all_output_immediately(capsys):
    controller = _ShellOutputController(TerminalReporter(), mode="all")
    metric = Metric(name="lint", command="npm run lint")

    controller.handle_output(metric, "stdout", "line one\n")

    out = capsys.readouterr().out
    assert "[LOG][stdout] lint: line one" in out


def test_shell_output_controller_flushes_failure_logs_only_for_failures(capsys):
    controller = _ShellOutputController(TerminalReporter(), mode="failures")
    metric = Metric(name="lint", command="npm run lint", tier=Tier.FAST)
    failure = MetricResult(
        metric_name="lint",
        passed=False,
        output="failed",
        tier=Tier.FAST,
        state=ResultState.FAIL,
    )

    controller.handle_output(metric, "stdout", "line one\n")
    controller.handle_progress("end", metric, failure)

    out = capsys.readouterr().out
    assert "[DONE] lint: FAIL [fast]" in out
    assert "[LOG][stdout] lint: line one" in out


def test_shell_output_controller_discards_success_logs_in_failures_mode(capsys):
    controller = _ShellOutputController(TerminalReporter(), mode="failures")
    metric = Metric(name="lint", command="npm run lint", tier=Tier.FAST)
    success = MetricResult(
        metric_name="lint",
        passed=True,
        output="ok",
        tier=Tier.FAST,
        state=ResultState.PASS,
    )

    controller.handle_output(metric, "stdout", "line one\n")
    controller.handle_progress("end", metric, success)

    out = capsys.readouterr().out
    assert "[DONE] lint: PASS [fast]" in out
    assert "[LOG][stdout] lint: line one" not in out
