# Code Quality Dimension Spec

Use this when editing `code_quality` evidence such as
`docs/fitness/code-quality.md`.

## Purpose

Guard the shape and maintainability of the code itself.

## Typical Signals

- lint
- typecheck
- clippy or compiler warnings
- file or function budgets
- duplicate code checks
- structural smell scans
- complexity limits

## Good Metric Patterns

- prefer repository scripts for lint and typecheck
- use diff-aware commands for expensive static checks when the repository
  already does that
- keep hard gates for checks that should truly block merge
- avoid optional toolchain-specific checks as bootstrap `fast` hard gates unless
  they are locally runnable or a checked-in repo wrapper bootstraps them

## Split Guidance

Keep `code_quality` focused on static or source-local concerns.

Do not hide these here:

- API parity checks
- runtime telemetry probes
- e2e flows
- security scanners

## Narrative Body

Use the markdown body to explain:

- what code-quality failure means in this repository
- why specific budgets or thresholds exist
- any known legacy hotspots or waivers
