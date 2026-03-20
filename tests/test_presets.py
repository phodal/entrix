"""Tests for project presets."""

from pathlib import Path

from entrix.model import Metric
from entrix.presets import get_project_preset


def test_get_project_preset_returns_routa_behavior():
    preset = get_project_preset()
    assert preset.fitness_dir(Path("/repo")) == Path("/repo/docs/fitness")
    assert preset.review_trigger_config(Path("/repo")) == Path("/repo/docs/fitness/review-triggers.yaml")


def test_routa_preset_domains_from_files():
    preset = get_project_preset()
    domains = preset.domains_from_files(
        [
            "crates/routa-server/src/main.rs",
            "src/app/page.tsx",
            "tools/entrix/entrix/cli.py",
            "api-contract.yaml",
        ]
    )
    assert domains == {"rust", "web", "python", "config"}


def test_routa_preset_metric_domains():
    preset = get_project_preset()
    metric = Metric(name="lint", command="npm run lint")
    assert preset.metric_domains(metric) == {"web"}


def test_routa_preset_should_ignore_changed_file():
    preset = get_project_preset()
    assert preset.should_ignore_changed_file("docs/fitness/code-quality.md") is True
    assert preset.should_ignore_changed_file("src/app/page.tsx") is False
