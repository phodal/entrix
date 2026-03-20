"""Protocol definition for structural analyzers.

Decouples the fitness engine from any specific code graph implementation.
The built-in Tree-sitter adapter is the default backend, but the Protocol allows
swapping in alternative implementations (external code-review-graph, remote
service, etc.).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class StructuralAnalyzer(Protocol):
    """Interface for code structure analysis backends."""

    def build_or_update(self, *, full: bool = False, base: str = "HEAD~1") -> dict:
        """Build or incrementally update the code graph.

        Returns:
            Dict with keys like 'build_type', 'files_parsed', 'nodes', 'edges'.
        """
        ...

    def impact_radius(self, files: list[str], *, depth: int = 2) -> dict:
        """Compute blast radius from a set of changed files.

        Returns:
            Dict with 'status', 'changed_nodes', 'impacted_nodes',
            'impacted_files', 'edges'.
        """
        ...

    def query(self, query_type: str, target: str) -> dict:
        """Run a structural query (callers_of, tests_for, etc.).

        Returns:
            Dict with query-specific results.
        """
        ...

    def stats(self) -> dict:
        """Return aggregate graph statistics.

        Returns:
            Dict with 'nodes', 'edges', 'files', 'languages', etc.
        """
        ...
