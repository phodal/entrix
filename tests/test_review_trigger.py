"""Tests for entrix.review_trigger."""

from __future__ import annotations

import textwrap
from pathlib import Path

from entrix.review_trigger import (
    DiffStats,
    evaluate_review_triggers,
    load_review_triggers,
)

def _write_review_trigger_config(tmp_path: Path) -> Path:
    config = tmp_path / "review-triggers.yaml"
    config.write_text(
        textwrap.dedent(
            """\
            review_triggers:
              - name: high_risk_directory_change
                type: changed_paths
                paths:
                  - src/core/acp/**
                severity: high
                action: require_human_review
              - name: directory_file_count_guard
                type: directory_file_count
                directories:
                  - scripts
                max_files: 2
              - name: sensitive_contract_change
                type: sensitive_file_change
                paths:
                  - api-contract.yaml
              - name: code_without_evidence
                type: evidence_gap
                paths:
                  - src/core/acp/**
                evidence_paths:
                  - docs/fitness/**
              - name: cross_boundary_change
                type: cross_boundary_change
                boundaries:
                  web:
                    - src/**
                  rust:
                    - crates/**
                  tools:
                    - tools/**
                min_boundaries: 2
              - name: oversized_change
                type: diff_size
                max_files: 5
                max_added_lines: 100
                max_deleted_lines: 20
            """
        ),
        encoding="utf-8",
    )
    return config


def test_load_review_triggers(tmp_path: Path):
    config = _write_review_trigger_config(tmp_path)

    rules = load_review_triggers(config)

    assert len(rules) == 6
    assert rules[0].paths == ("src/core/acp/**",)
    assert rules[1].directories == ("scripts",)
    assert rules[5].max_files == 5
    assert rules[3].evidence_paths == ("docs/fitness/**",)
    assert rules[4].min_boundaries == 2


def test_evaluate_review_triggers_matches_changed_paths(tmp_path: Path):
    report = evaluate_review_triggers(
        load_review_triggers(_write_review_trigger_config(tmp_path)),
        ["src/core/acp/agent.ts", "src/app/page.tsx"],
        DiffStats(file_count=2, added_lines=20, deleted_lines=5),
        base="HEAD~1",
    )

    assert report.human_review_required is True
    assert report.triggers[0].name == "high_risk_directory_change"
    assert "src/core/acp/agent.ts" in report.triggers[0].reasons[0]


def test_evaluate_review_triggers_matches_diff_size(tmp_path: Path):
    report = evaluate_review_triggers(
        load_review_triggers(_write_review_trigger_config(tmp_path)),
        ["src/app/page.tsx"],
        DiffStats(file_count=20, added_lines=700, deleted_lines=10),
        base="HEAD~1",
    )

    assert report.human_review_required is True
    names = {trigger.name for trigger in report.triggers}
    assert "oversized_change" in names


def test_evaluate_review_triggers_directory_file_count(tmp_path: Path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "a.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (scripts_dir / "b.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (scripts_dir / "c.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (scripts_dir / "nested").mkdir()
    (scripts_dir / "nested" / "ignored.sh").write_text("#!/bin/sh\n", encoding="utf-8")

    report = evaluate_review_triggers(
        load_review_triggers(_write_review_trigger_config(tmp_path)),
        ["scripts/a.sh"],
        DiffStats(file_count=1, added_lines=5, deleted_lines=0),
        base="HEAD~1",
        repo_root=tmp_path,
    )

    names = {trigger.name for trigger in report.triggers}
    assert "directory_file_count_guard" in names
    assert "direct files" in report.triggers[0].reasons[0]


def test_evaluate_review_triggers_returns_clean_report(tmp_path: Path):
    report = evaluate_review_triggers(
        load_review_triggers(_write_review_trigger_config(tmp_path)),
        ["src/app/page.tsx"],
        DiffStats(file_count=1, added_lines=10, deleted_lines=2),
        base="HEAD~1",
    )

    assert report.human_review_required is False
    assert report.triggers == ()


def test_evaluate_review_triggers_sensitive_file_change(tmp_path: Path):
    report = evaluate_review_triggers(
        load_review_triggers(_write_review_trigger_config(tmp_path)),
        ["api-contract.yaml", "src/app/page.tsx"],
        DiffStats(file_count=2, added_lines=20, deleted_lines=1),
        base="HEAD~1",
    )

    names = {trigger.name for trigger in report.triggers}
    assert "sensitive_contract_change" in names


def test_evaluate_review_triggers_evidence_gap(tmp_path: Path):
    report = evaluate_review_triggers(
        load_review_triggers(_write_review_trigger_config(tmp_path)),
        ["src/core/acp/session.ts"],
        DiffStats(file_count=1, added_lines=30, deleted_lines=5),
        base="HEAD~1",
    )

    names = {trigger.name for trigger in report.triggers}
    assert "code_without_evidence" in names


def test_evaluate_review_triggers_cross_boundary_change(tmp_path: Path):
    report = evaluate_review_triggers(
        load_review_triggers(_write_review_trigger_config(tmp_path)),
        ["src/core/acp/session.ts", "crates/routa-server/src/api/mod.rs"],
        DiffStats(file_count=2, added_lines=50, deleted_lines=10),
        base="HEAD~1",
    )

    names = {trigger.name for trigger in report.triggers}
    assert "cross_boundary_change" in names
