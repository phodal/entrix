"""Tests for loader-layer imports."""

from pathlib import Path

from routa_fitness.loaders import load_dimensions, parse_frontmatter, validate_weights
from routa_fitness.model import Dimension


def test_loader_parse_frontmatter():
    content = "---\ndimension: quality\nweight: 100\nmetrics: []\n---\n"
    fm = parse_frontmatter(content)
    assert fm is not None
    assert fm["dimension"] == "quality"


def test_loader_validate_weights():
    valid, total = validate_weights([Dimension(name="quality", weight=100)])
    assert valid is True
    assert total == 100


def test_loader_load_dimensions(tmp_path: Path):
    fixture = tmp_path / "quality.md"
    fixture.write_text("---\ndimension: quality\nweight: 100\nmetrics: []\n---\n", encoding="utf-8")
    dimensions = load_dimensions(tmp_path)
    assert len(dimensions) == 1
    assert dimensions[0].name == "quality"
