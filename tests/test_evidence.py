"""Tests for routa_fitness.evidence."""

import textwrap
from pathlib import Path

from routa_fitness.evidence import load_dimensions, parse_frontmatter, validate_weights
from routa_fitness.model import (
    AnalysisMode,
    Confidence,
    EvidenceType,
    ExecutionScope,
    FitnessKind,
    Gate,
    Stability,
    Tier,
)


def test_parse_frontmatter_valid():
    content = textwrap.dedent("""\
        ---
        dimension: testability
        weight: 20
        metrics:
          - name: ts_test
            command: npm run test
        ---
        # Body
    """)
    fm = parse_frontmatter(content)
    assert fm is not None
    assert fm["dimension"] == "testability"
    assert fm["weight"] == 20
    assert len(fm["metrics"]) == 1


def test_parse_frontmatter_missing():
    assert parse_frontmatter("# No frontmatter here") is None


def test_parse_frontmatter_empty_yaml():
    content = "---\n---\n# Empty"
    fm = parse_frontmatter(content)
    assert fm is None  # yaml.safe_load returns None for empty


def test_load_dimensions(tmp_path: Path):
    md = tmp_path / "security.md"
    md.write_text(textwrap.dedent("""\
        ---
        dimension: security
        weight: 20
        threshold:
          pass: 90
          warn: 75
        metrics:
          - name: npm_audit
            command: npm audit
            hard_gate: true
            tier: fast
          - name: cargo_audit
            command: cargo audit
        ---
        # Security evidence
    """))

    dims = load_dimensions(tmp_path)
    assert len(dims) == 1
    dim = dims[0]
    assert dim.name == "security"
    assert dim.weight == 20
    assert dim.threshold_pass == 90
    assert dim.threshold_warn == 75
    assert len(dim.metrics) == 2
    assert dim.metrics[0].hard_gate is True
    assert dim.metrics[0].tier == Tier.FAST
    assert dim.metrics[1].tier == Tier.NORMAL
    assert dim.source_file == "security.md"


def test_load_dimensions_parses_v2_fields_and_preserves_v1_compat(tmp_path: Path):
    md = tmp_path / "runtime.md"
    md.write_text(textwrap.dedent("""\
        ---
        dimension: observability
        weight: 0
        metrics:
          - name: tracing_signal_available
            command: ./scripts/check.sh 2>&1
            pattern: "signal_ok"
            hard_gate: false
            tier: deep
            description: verify tracing signal
            execution_scope: staging
            gate: advisory
            kind: holistic
            analysis: dynamic
            stability: noisy
            evidence_type: probe
            scope: [web, rust]
            run_when_changed:
              - src/instrumentation.ts
              - crates/routa-server/src/telemetry/**
            timeout_seconds: 120
            owner: platform
            confidence: high
            waiver:
              reason: legacy hotspot pending refactor
              owner: phodal
              tracking_issue: 217
              expires_at: 2026-04-30
          - name: legacy_metric
            command: echo legacy
            hard_gate: true
        ---
        # Runtime evidence
    """))

    dims = load_dimensions(tmp_path)
    assert len(dims) == 1
    metrics = dims[0].metrics
    assert len(metrics) == 2

    runtime_metric = metrics[0]
    assert runtime_metric.execution_scope == ExecutionScope.STAGING
    assert runtime_metric.gate == Gate.ADVISORY
    assert runtime_metric.kind == FitnessKind.HOLISTIC
    assert runtime_metric.analysis == AnalysisMode.DYNAMIC
    assert runtime_metric.stability == Stability.NOISY
    assert runtime_metric.evidence_type == EvidenceType.PROBE
    assert runtime_metric.scope == ["web", "rust"]
    assert runtime_metric.run_when_changed == [
        "src/instrumentation.ts",
        "crates/routa-server/src/telemetry/**",
    ]
    assert runtime_metric.timeout_seconds == 120
    assert runtime_metric.owner == "platform"
    assert runtime_metric.confidence == Confidence.HIGH
    assert runtime_metric.waiver is not None
    assert runtime_metric.waiver.reason == "legacy hotspot pending refactor"
    assert runtime_metric.waiver.owner == "phodal"
    assert runtime_metric.waiver.tracking_issue == 217
    assert str(runtime_metric.waiver.expires_at) == "2026-04-30"

    legacy_metric = metrics[1]
    assert legacy_metric.gate == Gate.HARD
    assert legacy_metric.execution_scope == ExecutionScope.LOCAL
    assert legacy_metric.kind == FitnessKind.ATOMIC
    assert legacy_metric.analysis == AnalysisMode.STATIC


def test_load_dimensions_invalid_v2_values_fall_back_to_defaults(tmp_path: Path):
    md = tmp_path / "bad-values.md"
    md.write_text(textwrap.dedent("""\
        ---
        dimension: testability
        weight: 10
        metrics:
          - name: weird_metric
            command: echo ok
            tier: ultra
            execution_scope: moon
            gate: severe
            kind: hybrid
            analysis: magical
            stability: flaky
            evidence_type: unsupported
            confidence: maybe
            scope: not-a-list
            run_when_changed: not-a-list
        ---
        # Bad values
    """))

    dims = load_dimensions(tmp_path)
    metric = dims[0].metrics[0]
    assert metric.tier == Tier.NORMAL
    assert metric.execution_scope == ExecutionScope.LOCAL
    assert metric.gate == Gate.SOFT
    assert metric.kind == FitnessKind.ATOMIC
    assert metric.analysis == AnalysisMode.STATIC
    assert metric.stability == Stability.DETERMINISTIC
    assert metric.evidence_type == EvidenceType.COMMAND
    assert metric.confidence == Confidence.UNKNOWN
    assert metric.scope == []
    assert metric.run_when_changed == []


def test_load_dimensions_skips_readme(tmp_path: Path):
    (tmp_path / "README.md").write_text("---\ndimension: x\nweight: 10\nmetrics:\n  - name: y\n    command: z\n---\n")
    dims = load_dimensions(tmp_path)
    assert len(dims) == 0


def test_load_dimensions_skips_no_frontmatter(tmp_path: Path):
    (tmp_path / "notes.md").write_text("# Just notes\nNo frontmatter here.")
    dims = load_dimensions(tmp_path)
    assert len(dims) == 0


def test_load_dimensions_uses_manifest_when_present(tmp_path: Path):
    fitness_dir = tmp_path / "docs" / "fitness"
    runtime_dir = fitness_dir / "runtime"
    runtime_dir.mkdir(parents=True)
    (fitness_dir / "manifest.yaml").write_text(textwrap.dedent("""\
        schema: fitness-manifest-v1
        evidence_files:
          - docs/fitness/runtime/observability.md
    """))
    (fitness_dir / "ignored.md").write_text(textwrap.dedent("""\
        ---
        dimension: ignored
        weight: 100
        metrics:
          - name: ignored
            command: echo ignored
        ---
    """))
    (runtime_dir / "observability.md").write_text(textwrap.dedent("""\
        ---
        dimension: observability
        weight: 0
        metrics:
          - name: tracing_signal_available
            command: echo signal_ok
        ---
    """))

    dims = load_dimensions(fitness_dir)
    assert len(dims) == 1
    assert dims[0].name == "observability"
    assert dims[0].source_file == "runtime/observability.md"


def test_validate_weights():
    from routa_fitness.model import Dimension

    dims = [
        Dimension(name="a", weight=60),
        Dimension(name="b", weight=40),
    ]
    valid, total = validate_weights(dims)
    assert valid is True
    assert total == 100


def test_validate_weights_fail():
    from routa_fitness.model import Dimension

    dims = [Dimension(name="a", weight=50)]
    valid, total = validate_weights(dims)
    assert valid is False
    assert total == 50
