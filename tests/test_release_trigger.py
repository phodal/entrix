from __future__ import annotations

import textwrap
from pathlib import Path

from entrix.release_trigger import evaluate_release_triggers, load_release_manifest, load_release_triggers


def _write_release_trigger_config(tmp_path: Path) -> Path:
    config = tmp_path / "release-triggers.yaml"
    config.write_text(
        textwrap.dedent(
            """\
            release_triggers:
              - name: unexpected_sourcemap_in_release
                type: unexpected_file
                patterns:
                  - "**/*.map"
                apply_to:
                  - npm_tarball
                severity: critical
                action: block_release
              - name: npm_tarball_growth_guard
                type: artifact_size_delta
                apply_to:
                  - npm_tarball
                group_by:
                  - target
                  - channel
                max_growth_percent: 20
                min_growth_bytes: 100
                severity: high
                action: require_human_review
              - name: cli_binary_size_limit
                type: artifact_size_delta
                apply_to:
                  - cli_binary
                max_size_bytes: 1000
                severity: high
                action: require_human_review
              - name: packaging_boundary_changed
                type: release_boundary_change
                paths:
                  - scripts/release/**
              - name: capability_or_supply_chain_drift
                type: capability_change
                paths:
                  - apps/desktop/src-tauri/capabilities/**
              - name: release_manifest_missing
                type: manifest_missing
                severity: critical
                action: block_release
            """
        ),
        encoding="utf-8",
    )
    return config


def _write_manifest(path: Path, content: str) -> Path:
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def test_release_trigger_blocks_unexpected_sourcemaps_and_manifest_missing(tmp_path: Path):
    config_path = _write_release_trigger_config(tmp_path)
    manifest_path = _write_manifest(
        tmp_path / "manifest.json",
        """\
        {
          "artifacts": [
            {
              "kind": "npm_tarball",
              "path": "dist/npm/routa-cli-0.1.0.tgz",
              "target": "linux-x64",
              "channel": "latest",
              "size_bytes": 512,
              "file_count": 3,
              "entries": [
                {"path": "package/package.json", "size_bytes": 100},
                {"path": "package/dist/index.js", "size_bytes": 200},
                {"path": "package/dist/index.js.map", "size_bytes": 212}
              ]
            }
          ]
        }
        """,
    )
    rules = load_release_triggers(config_path)
    manifest_label, artifacts = load_release_manifest(manifest_path)
    report = evaluate_release_triggers(rules, artifacts, manifest_path=manifest_label)

    assert report.blocked is True
    assert report.human_review_required is True
    assert any(trigger.name == "unexpected_sourcemap_in_release" for trigger in report.triggers)

    empty_manifest_path = _write_manifest(tmp_path / "empty-manifest.json", '{"artifacts": []}')
    _, empty_artifacts = load_release_manifest(empty_manifest_path)
    empty_report = evaluate_release_triggers(rules, empty_artifacts, manifest_path=str(empty_manifest_path))
    assert empty_report.blocked is True
    assert any(trigger.name == "release_manifest_missing" for trigger in empty_report.triggers)


def test_release_trigger_detects_growth_and_release_sensitive_changes(tmp_path: Path):
    config_path = _write_release_trigger_config(tmp_path)
    current_manifest_path = _write_manifest(
        tmp_path / "current-manifest.json",
        """\
        {
          "artifacts": [
            {
              "kind": "npm_tarball",
              "path": "dist/npm/routa-cli-0.2.0.tgz",
              "target": "linux-x64",
              "channel": "latest",
              "size_bytes": 1600,
              "file_count": 10
            },
            {
              "kind": "cli_binary",
              "path": "dist/cli-artifacts/linux-x64/routa",
              "target": "linux-x64",
              "channel": "latest",
              "size_bytes": 1400,
              "file_count": 1
            }
          ]
        }
        """,
    )
    baseline_manifest_path = _write_manifest(
        tmp_path / "baseline-manifest.json",
        """\
        {
          "artifacts": [
            {
              "kind": "npm_tarball",
              "path": "dist/npm/routa-cli-0.1.9.tgz",
              "target": "linux-x64",
              "channel": "latest",
              "size_bytes": 1000,
              "file_count": 8
            }
          ]
        }
        """,
    )
    rules = load_release_triggers(config_path)
    manifest_label, artifacts = load_release_manifest(current_manifest_path)
    baseline_label, baseline_artifacts = load_release_manifest(baseline_manifest_path)
    report = evaluate_release_triggers(
        rules,
        artifacts,
        manifest_path=manifest_label,
        baseline_artifacts=baseline_artifacts,
        baseline_manifest_path=baseline_label,
        changed_files=[
            "scripts/release/stage-routa-cli-npm.mjs",
            "apps/desktop/src-tauri/capabilities/default.json",
        ],
    )

    assert report.blocked is False
    assert report.human_review_required is True
    names = {trigger.name for trigger in report.triggers}
    assert "npm_tarball_growth_guard" in names
    assert "cli_binary_size_limit" in names
    assert "packaging_boundary_changed" in names
    assert "capability_or_supply_chain_drift" in names
