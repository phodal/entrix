"""JSON reporter — machine-readable output for CI pipelines."""

from __future__ import annotations

import sys

from routa_fitness.model import FitnessReport
from routa_fitness.reporting import report_to_dict


class JsonReporter:
    """Outputs fitness report as JSON to stdout or a file."""

    def report(self, report: FitnessReport, *, file=None) -> None:
        """Serialize the fitness report to JSON.

        Args:
            report: The fitness report to serialize.
            file: File-like object to write to (defaults to stdout).
        """
        out = file or sys.stdout
        import json

        json.dump(report_to_dict(report), out, indent=2, ensure_ascii=False)
        out.write("\n")
