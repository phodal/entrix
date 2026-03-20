"""Structural queries — convenience wrappers over the StructuralAnalyzer protocol."""

from __future__ import annotations

from routa_fitness.structure.protocol import StructuralAnalyzer


def callers_of(analyzer: StructuralAnalyzer, target: str) -> dict:
    """Find all callers of a function/method."""
    return analyzer.query("callers_of", target)


def callees_of(analyzer: StructuralAnalyzer, target: str) -> dict:
    """Find all functions/methods called by target."""
    return analyzer.query("callees_of", target)


def tests_for(analyzer: StructuralAnalyzer, target: str) -> dict:
    """Find test functions covering target."""
    return analyzer.query("tests_for", target)


def imports_of(analyzer: StructuralAnalyzer, target: str) -> dict:
    """Find what target imports."""
    return analyzer.query("imports_of", target)


def importers_of(analyzer: StructuralAnalyzer, target: str) -> dict:
    """Find what imports target."""
    return analyzer.query("importers_of", target)


def inheritors_of(analyzer: StructuralAnalyzer, target: str) -> dict:
    """Find classes that inherit from target."""
    return analyzer.query("inheritors_of", target)


def file_summary(analyzer: StructuralAnalyzer, target: str) -> dict:
    """Get a structural summary of a file."""
    return analyzer.query("file_summary", target)
