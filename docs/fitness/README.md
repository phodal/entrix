# Entrix Dogfooding Rulebook

This repository uses `entrix` to govern `entrix` itself.

The goal is simple:

- keep deterministic quality gates executable
- keep review escalation explicit for risky changes
- prove the published PyPI package can run against this repository in GitHub Actions

## Local Usage

Install local development dependencies:

```bash
python3 -m pip install -e ".[dev]"
python3 -m pip install build
```

Run the governance checks from the repository root:

```bash
python3 -m entrix validate
python3 -m entrix run --tier fast
python3 -m entrix run --tier normal --min-score 0
python3 -m entrix review-trigger --base HEAD~1
```

Run the same flow using the published PyPI package:

```bash
uvx --from entrix entrix validate
uvx --from entrix entrix run --tier normal --min-score 0
uvx --from entrix entrix review-trigger --base HEAD~1
```

## Dimensions

- `code_quality`: lint and obvious change hygiene
- `testability`: pytest must keep behavior stable
- `release_readiness`: the package must still build and expose a working CLI
- `observability`: runtime visibility evidence, modeled as zero-weight runtime guidance
- `performance`: runtime budget examples, modeled separately from observability

## Execution Policy

- `fast`: cheap static checks suitable for frequent execution
- `normal`: adds tests and packaging verification
- `deep`: includes graph-backed checks and runtime-oriented evidence surfaces

Local dogfooding keeps one additional rule: plain local `entrix run` should stay
green on a fresh machine. Metrics that are authoritative only in CI or other
provisioned environments should be modeled with `execution_scope: ci` instead of
remaining in the default local execution path.

When the bundled `/entrix` skill changes, also run the fixture harness:

```bash
bash scripts/skill_regression.sh --fixtures
```

Use path mode for local forward validation against real repositories:

```bash
bash scripts/skill_regression.sh /abs/path/to/repo-a /abs/path/to/repo-b
```

## Files

- `code-quality.md`: executable code quality metrics
- `testability.md`: executable test metrics
- `release-readiness.md`: build and CLI readiness metrics
- `runtime/observability.md`: staging-oriented runtime visibility examples
- `runtime/performance.md`: runtime budget examples kept separate from observability
- `review-triggers.yaml`: risky-change escalation rules
- `manifest.yaml`: simple inventory of the active evidence files, including nested runtime docs
- `../tests/fixtures/skill_regression/`: bundled repo-profile fixtures for the
  skill regression harness
