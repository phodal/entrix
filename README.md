# Entrix

[![PyPI version](https://img.shields.io/pypi/v/entrix.svg)](https://pypi.org/project/entrix/)
[![Python versions](https://img.shields.io/pypi/pyversions/entrix.svg)](https://pypi.org/project/entrix/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Guardrails Embedded in the Change Lifecycle**

Entrix is a Harness Engineering tool for turning quality rules, architecture
constraints, and validation steps into executable guardrails.

Instead of relying on manual review at the end of delivery, Entrix moves
validation forward: checks become codified, evidence becomes traceable, and
quality gates become part of the engineering system itself.

It is designed for teams building in the AI era, where code can be generated
faster than it can be governed.

Entrix helps teams answer three questions continuously:

- should this change pass baseline quality gates?
- what level of confidence do we have in the current change?
- when should the system route the change to deeper validation or human review?

## Lifecycle View

![Entrix Lifecycle](docs/lifecycle.svg)

Additional design context:

- `tools/entrix/docs/adr/README.md`: Entrix architecture decisions and rationale

## What It Does

Today the package provides:

- architecture fitness checks grouped by dimension
- fast / normal / deep execution tiers
- change-aware execution against the current git diff
- hard-gate and weighted-score orchestration
- `review-trigger` rules that ask for human review on risky changes
- graph-backed impact analysis, test radius estimation, and review context generation
- structural analysis for oversized files (ClassMap / FunctionMap)
- preset system for project-specific configuration

It is useful both as:

- a repository-local fitness runner for monorepos and application repos
- the beginning of a more reusable fitness engine

## Requirements

- Python 3.10 or later

## Installation

### Install from PyPI with `uv`

```bash
uv tool install entrix
```

Run without installing globally:

```bash
uvx entrix --help
uvx entrix run --tier fast
uvx entrix review-trigger --base HEAD~1
```

### Install from PyPI with `pip`

```bash
pip install entrix
```

### Optional dependencies

Entrix ships optional dependency groups for extended features:

```bash
# Graph-backed impact analysis (code-review-graph)
pip install entrix[graph]

# MCP server for AI agent integration (fastmcp)
pip install entrix[mcp]

# Development tools (pytest, ruff)
pip install entrix[dev]
```

### Run in a project without global install

```bash
uvx --from entrix entrix --help
uvx --from entrix entrix run --tier fast
```

### Develop from the Routa.js checkout

If you are using the copy of `entrix` vendored in the Routa.js monorepo, the
current repository workflow is:

```bash
pip install -e tools/entrix

PYTHONPATH=tools/entrix python3 -m entrix --help
PYTHONPATH=tools/entrix python3 -m entrix run --tier fast
PYTHONPATH=tools/entrix python3 -m entrix review-trigger --base HEAD~1
```

Most local hooks and helper scripts in this repository use the
`PYTHONPATH=tools/entrix python3 -m entrix ...` form so they can run directly
from the monorepo checkout without requiring a separately installed global
binary.

### Develop the package itself from source

If you are working on the `entrix` package source itself, clone this repository and install it from the repository root.

From the repository root:

```bash
git clone https://github.com/phodal/entrix.git
cd entrix
uv pip install -e .
```

With `pip`:

```bash
git clone https://github.com/phodal/entrix.git
cd entrix
pip install -e .
```

## Quick Start

### 1. Create a fitness spec

By default, `entrix run` looks for specs under the current project's:

```text
docs/fitness/*.md
```

Example `docs/fitness/code-quality.md`:

```yaml
---
dimension: code_quality
weight: 20
threshold:
  pass: 90
  warn: 80
metrics:
  - name: lint
    command: npm run lint 2>&1
    hard_gate: true
    tier: fast
    description: ESLint must pass

  - name: unit_tests
    command: npm run test:run 2>&1
    pattern: "Tests\\s+\\d+\\s+passed"
    hard_gate: true
    tier: normal
    description: unit tests must pass
---

# Code Quality

Narrative evidence, rules, and ownership notes can live below the frontmatter.
```

### Advanced metric fields

Beyond the basic fields shown above, each metric in the frontmatter supports additional options:

```yaml
metrics:
  - name: api_contract
    command: npm run test:contract 2>&1
    hard_gate: false
    tier: normal
    description: API contract tests

    # Execution scope — where this metric is authoritative
    # Values: local, ci, staging, prod_observation
    execution_scope: ci

    # Timeout in seconds (null = no limit)
    timeout_seconds: 120

    # Gate severity: hard, soft, advisory
    gate: soft

    # Evidence type: command, test, probe, sarif, manual_attestation
    evidence_type: test

    # Confidence level: high, medium, low, unknown
    confidence: high

    # Signal stability: deterministic, noisy
    stability: deterministic

    # Fitness kind: atomic (single check) or holistic (system-wide)
    kind: atomic

    # Analysis mode: static (code structure) or dynamic (runtime)
    analysis: dynamic

    # Owner responsible for this metric
    owner: team-platform

    # Only run when these file patterns change
    run_when_changed:
      - "src/api/**"
      - "openapi.yaml"

    # Temporary waiver to bypass a failing metric
    waiver:
      reason: "Known flaky test, fix tracked in issue #42"
      owner: team-platform
      tracking_issue: 42
      expires_at: "2025-06-01"
```

### 2. Run the checks

```bash
entrix run --tier fast
entrix run --tier normal
entrix run --tier normal --scope ci --dimension code_quality --dimension testability
entrix run --tier fast --metric eslint_pass --metric ts_typecheck_pass
entrix run --changed-only --base HEAD~1
entrix validate
```

Use `--metric` when you want to run only specific metric names without creating a temporary dimension file split.

### 3. Add review triggers

By default, `review-trigger` loads the current project's:

```text
docs/fitness/review-triggers.yaml
```

Example `docs/fitness/review-triggers.yaml`:

```yaml
review_triggers:
  - name: high_risk_directory_change
    type: changed_paths
    paths:
      - src/core/acp/**
      - src/core/orchestration/**
      - services/api/**
    severity: high
    action: require_human_review

  - name: oversized_change
    type: diff_size
    max_files: 12
    max_added_lines: 600
    max_deleted_lines: 400
    severity: medium
    action: require_human_review
```

Run it:

```bash
entrix review-trigger --base HEAD~1
entrix review-trigger --base HEAD~1 --json
```

Example output:

```json
{
  "human_review_required": true,
  "base": "HEAD~1",
  "changed_files": [
    "services/api/src/routes/acp_routes.rs"
  ],
  "diff_stats": {
    "file_count": 13,
    "added_lines": 936,
    "deleted_lines": 20
  },
  "triggers": [
    {
      "name": "high_risk_directory_change",
      "severity": "high",
      "action": "require_human_review",
      "reasons": [
        "changed path: services/api/src/routes/acp_routes.rs"
      ]
    }
  ]
}
```

## Commands

### `entrix run`

Runs dimension-based fitness checks loaded from `docs/fitness/*.md`.

Common flags:

```bash
entrix run --tier fast
entrix run --parallel
entrix run --dry-run
entrix run --verbose
entrix run --changed-only --base HEAD~1
entrix run --files src/app.ts src/lib.ts
entrix run --output report.json
entrix run --output -              # JSON to stdout
entrix run --min-score 90
```

Use `--output` to write a JSON report to a file (or `-` for stdout), useful for CI artifact collection. Use `--files` to pass an explicit list of changed files for incremental metric selection.

### `entrix validate`

Checks that dimension weights sum to `100%`.

```bash
entrix validate
```

### `entrix review-trigger`

Evaluates governance-oriented trigger rules for risky changes.

Common flags:

```bash
entrix review-trigger --base HEAD~1
entrix review-trigger --json
entrix review-trigger --fail-on-trigger
entrix review-trigger --config docs/fitness/review-triggers.yaml
```

### `entrix analyze long-file`

Structural analysis for oversized or explicit source files. Returns ClassMap / FunctionMap payloads showing classes, methods, and standalone functions with line spans.

Supported languages: Python, Rust, Go, Java, and TypeScript/JavaScript
(including `tsx` / `jsx` files).

```bash
entrix analyze long-file --files src/app.ts src/lib.ts
entrix analyze long-file --json
entrix analyze long-file --config file_budgets.json --strict-limit
entrix analyze long-file --min-lines 100
```

When no `--files` are given, the command auto-discovers files that exceed their configured line budget.

### `entrix graph ...`

Graph-backed commands support building the code graph, querying relationships, impact analysis, test radius estimation, commit history analysis, and AI-friendly review context generation.

Requires the optional graph dependency: `pip install entrix[graph]`.

#### `entrix graph build`

Build or update the code graph.

```bash
entrix graph build --base HEAD~1
entrix graph build --build-mode full --json
```

#### `entrix graph stats`

Show graph statistics (node and edge counts).

```bash
entrix graph stats
entrix graph stats --json
```

#### `entrix graph impact`

Analyze the blast radius of changed files.

```bash
entrix graph impact --base HEAD~1
entrix graph impact --base HEAD~1 --depth 3 --json
```

#### `entrix graph test-radius`

Estimate which tests are affected by changed files.

```bash
entrix graph test-radius --base HEAD~1
entrix graph test-radius --base HEAD~1 --max-targets 50 --json
```

#### `entrix graph query`

Run a structural query against the code graph.

Available patterns: `callers_of`, `callees_of`, `imports_of`, `importers_of`, `children_of`, `tests_for`, `inheritors_of`, `file_summary`.

```bash
entrix graph query callers_of "mymodule.MyClass.my_method"
entrix graph query tests_for "src/core/engine.py" --json
```

#### `entrix graph history`

Estimate test radius for recent commits using the current graph.

```bash
entrix graph history --count 20 --ref main
entrix graph history --json
```

#### `entrix graph review-context`

Build an AI-friendly review context from the current graph.

```bash
entrix graph review-context --base HEAD~1 --json
entrix graph review-context --base HEAD~1 --max-files 20 --no-source
entrix graph review-context --base HEAD~1 --output context.json
```

## Preset System

Entrix uses a preset system to adapt behavior to different project layouts. The default `ProjectPreset` looks for fitness specs in `docs/fitness/` and review triggers in `docs/fitness/review-triggers.yaml`.

Custom presets can override:

- `fitness_dir(project_root)` — where to find fitness spec files
- `review_trigger_config(project_root)` — path to the review trigger YAML
- `should_ignore_changed_file(file_path)` — filter out irrelevant changed files
- `domains_from_files(files)` — extract domain tags from changed file paths

A built-in `RoutaPreset` is included as a reference implementation for monorepo layouts.

## AI-Friendly Authoring Notes

If an AI agent is generating or updating fitness specs, these conventions work best:

- keep one dimension per file
- make the frontmatter executable and the body explanatory
- prefer stable command outputs over fragile text matching
- use `hard_gate: true` only when failure should really block progress
- keep review-trigger rules separate from scoring metrics
- treat markdown as the narrative layer, not the only source of structure

Recommended file layout:

```text
your-project/
  docs/
    fitness/
      README.md
      code-quality.md
      security.md
      review-triggers.yaml
```

Minimal bootstrap flow for a new repository:

```bash
mkdir -p docs/fitness
cat > docs/fitness/code-quality.md <<'EOF'
---
dimension: code_quality
weight: 100
threshold:
  pass: 100
  warn: 80
metrics:
  - name: lint
    command: npm run lint 2>&1
    hard_gate: true
    tier: fast
---

# Code Quality
EOF

entrix validate
entrix run --tier fast
```

## Python API

### Review trigger example

```python
from pathlib import Path

from entrix.review_trigger import (
    collect_changed_files,
    collect_diff_stats,
    evaluate_review_triggers,
    load_review_triggers,
)

repo_root = Path(".").resolve()
rules = load_review_triggers(repo_root / "docs" / "fitness" / "review-triggers.yaml")
changed_files = collect_changed_files(repo_root, "HEAD~1")
diff_stats = collect_diff_stats(repo_root, "HEAD~1")
report = evaluate_review_triggers(rules, changed_files, diff_stats, base="HEAD~1")
print(report.to_dict())
```

### Fitness spec loading example

```python
from pathlib import Path

from entrix.evidence import load_dimensions

dimensions = load_dimensions(Path("docs/fitness"))
for dimension in dimensions:
    print(dimension.name, len(dimension.metrics))
```

## Recommended Hook Integration

For generic repositories, a practical pattern is:

- `pre-commit`: run `entrix hook file-length` first, then quick lint
- `pre-push`: run full checks, then print review-trigger warnings
- CI: run `entrix run` and publish JSON/report output

That lets automation catch deterministic failures early while still escalating ambiguous risky changes to humans.

### Current Routa.js hook layout

The current Routa.js monorepo intentionally uses a slightly different split:

- `pre-commit`: `npm run lint`
- `post-commit`: `PYTHONPATH=tools/entrix python3 -m entrix hook file-length --config tools/entrix/file_budgets.pre_commit.json --strict-limit ...` as a warning-only budget report
- `pre-push`: `./scripts/smart-check.sh`, which runs a curated `entrix run --metric ...` set and then evaluates `review-trigger`

This keeps commit-time friction low while still surfacing file-budget drift and
enforcing the higher-signal fitness gates before push.

### Reusable file-length guard

`entrix` now exposes a reusable hook entrypoint:

```bash
python3 -m entrix hook file-length \
  --config tools/entrix/file_budgets.pre_commit.json \
  --staged-only \
  --strict-limit
```

Use it when you want AI-friendly oversized-file failures during `pre-commit`, for example:

```text
current file length 2383 exceeds limit 1500: src/app/page.tsx
```

A copy-pasteable template lives in [`examples/file-length-hook/`](examples/file-length-hook/).

## Known Constraints

Current constraints to be aware of:

- the package name on PyPI is `entrix`
- requires Python 3.10 or later
- the default authoring format is still markdown frontmatter under `docs/fitness`
- the project is evolving toward a cleaner core / adapter / preset split
- graph commands require the optional graph dependency: `pip install entrix[graph]`
- the current public CLI in this checkout exposes `run`, `validate`, `review-trigger`, `hook`, `analyze`, and `graph`
- `analyze long-file` structural analysis supports Python, Rust, Go, Java, TypeScript, and JavaScript

## Status

Current status:

- stable for production use in real repository workflows
- installable as a standalone PyPI package
- suitable for AI-assisted project configuration
- evolving toward a reusable fitness engine architecture

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines and contribution workflow.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
