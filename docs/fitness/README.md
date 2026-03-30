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

## Execution Policy

- `fast`: cheap static checks suitable for frequent execution
- `normal`: adds tests and packaging verification
- `deep`: reserved for future graph or security integrations

Local dogfooding keeps one additional rule: plain local `entrix run` should stay
green on a fresh machine. Metrics that are authoritative only in CI or other
provisioned environments should be modeled with `execution_scope: ci` instead of
remaining in the default local execution path.

## Files

- `code-quality.md`: executable code quality metrics
- `testability.md`: executable test metrics
- `release-readiness.md`: build and CLI readiness metrics
- `review-triggers.yaml`: risky-change escalation rules
- `manifest.yaml`: simple inventory of the active evidence files
