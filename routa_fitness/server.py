"""MCP server — expose fitness functions as tools for AI agent integration."""

from __future__ import annotations

from pathlib import Path


def create_server(project_root: Path | None = None):
    """Create and configure the FastMCP server.

    Requires the [mcp] optional dependency: pip install routa-fitness[mcp]
    """
    try:
        from fastmcp import FastMCP
    except ImportError as e:
        raise ImportError(
            "fastmcp is not installed. Install with: pip install routa-fitness[mcp]"
        ) from e

    if project_root is None:
        project_root = Path.cwd()

    mcp = FastMCP("routa-fitness", instructions="Evolutionary architecture fitness engine")

    @mcp.tool()
    def run_fitness(
        tier: str | None = None,
        scope: str | None = None,
        parallel: bool = False,
        dry_run: bool = False,
        min_score: float = 80.0,
    ) -> dict:
        """Run fitness checks and return a structured report.

        Args:
            tier: Filter by tier (fast, normal, deep). None runs all.
            scope: Filter by execution scope (local, ci, staging, prod_observation).
            parallel: Run metrics in parallel.
            dry_run: Show what would run without executing.
            min_score: Minimum weighted score before the result is considered blocked.
        """
        from routa_fitness.engine import run_fitness_report
        from routa_fitness.governance import GovernancePolicy
        from routa_fitness.model import ExecutionScope, Tier
        from routa_fitness.presets import get_project_preset
        from routa_fitness.reporting import report_to_dict

        tier_filter = Tier(tier) if tier else None
        execution_scope = ExecutionScope(scope) if scope else None
        policy = GovernancePolicy(
            tier_filter=tier_filter,
            parallel=parallel,
            dry_run=dry_run,
            min_score=min_score,
            execution_scope=execution_scope,
        )

        report, _ = run_fitness_report(project_root, policy, get_project_preset())
        return report_to_dict(report)

    @mcp.tool()
    def get_dimension_status(dimension: str) -> dict:
        """Get current status of a specific fitness dimension.

        Args:
            dimension: Dimension name (e.g. 'code_quality', 'security').
        """
        from routa_fitness.engine import run_fitness_report
        from routa_fitness.governance import GovernancePolicy
        from routa_fitness.presets import get_project_preset

        report, _ = run_fitness_report(
            project_root,
            GovernancePolicy(),
            get_project_preset(),
        )

        for ds in report.dimensions:
            if ds.dimension == dimension:
                return {
                    "final_score": report.final_score,
                    "name": ds.dimension,
                    "weight": ds.weight,
                    "score": ds.score,
                    "passed": ds.passed,
                    "total": ds.total,
                    "hard_gate_failures": ds.hard_gate_failures,
                    "results": [
                        {
                            "name": r.metric_name,
                            "passed": r.passed,
                            "state": r.state.value if r.state else None,
                            "tier": r.tier.value,
                            "hard_gate": r.hard_gate,
                        }
                        for r in ds.results
                    ],
                }

        return {"error": f"Dimension '{dimension}' not found"}

    @mcp.tool()
    def analyze_change_impact(
        changed_files: list[str] | None = None,
        depth: int = 2,
        base: str = "HEAD",
    ) -> dict:
        """Analyze blast radius of changes using the code graph.

        Requires an available graph backend.

        Args:
            changed_files: Explicit list of files, or None to auto-detect via git.
            depth: BFS traversal depth for impact analysis.
            base: Git ref to diff against.
        """
        from routa_fitness.runners.graph import GraphRunner

        runner = GraphRunner(project_root)
        if not runner.available:
            return {"status": "unavailable", "reason": "graph backend unavailable"}

        result = runner.probe_impact(base=base, max_depth=depth)
        return {
            "status": "ok",
            "passed": result.passed,
            "output": result.output,
        }

    return mcp


def main() -> None:
    """Entry point for `routa-fitness serve`."""
    server = create_server()
    server.run(transport="stdio")
