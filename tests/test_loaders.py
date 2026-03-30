"""Tests for loader-layer imports."""

from pathlib import Path

from entrix.loaders import load_dimensions, parse_frontmatter, validate_weights
from entrix.model import Dimension


def test_loader_parse_frontmatter():
    content = "---\ndimension: quality\nweight: 100\nmetrics: []\n---\n"
    fm = parse_frontmatter(content)
    assert fm is not None
    assert fm["dimension"] == "quality"


def test_loader_validate_weights():
    valid, total = validate_weights([Dimension(name="quality", weight=100)])
    assert valid is True
    assert total == 100


def test_frontend_quality_pack_loads_and_validates():
    repo_root = Path(__file__).resolve().parents[1]
    fitness_dir = repo_root / "examples" / "frontend-quality-pack" / "docs" / "fitness"

    dimensions = load_dimensions(fitness_dir)
    valid, total = validate_weights(dimensions)

    assert valid is True
    assert total == 100
    assert {dimension.name for dimension in dimensions} == {
        "code_quality",
        "design_system",
        "ui_consistency",
        "performance",
    }


def test_loader_load_dimensions(tmp_path: Path):
    fixture = tmp_path / "quality.md"
    fixture.write_text("---\ndimension: quality\nweight: 100\nmetrics: []\n---\n", encoding="utf-8")
    dimensions = load_dimensions(tmp_path)
    assert len(dimensions) == 1
    assert dimensions[0].name == "quality"
