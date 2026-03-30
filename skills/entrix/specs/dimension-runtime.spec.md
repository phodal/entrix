# Runtime Dimension Spec

Use this when editing runtime evidence such as:

- `docs/fitness/runtime/observability.md`
- `docs/fitness/runtime/performance.md`

## Purpose

Guard runtime evidence that is valuable but may not currently participate in the
weighted score.

## Common Shape

Runtime dimensions often use:

- `weight: 0`
- advisory or probe-style metrics
- `execution_scope: ci`, `staging`, or `prod_observation`
- `evidence_type: probe`
- `stability: noisy` when the signal is non-deterministic

## Why One Spec Is Enough

`observability` and `performance` usually share authoring rules:

- they are runtime-oriented
- they often produce evidence rather than strict pass/fail certainty
- they frequently need advanced metric metadata

That makes one shared skill spec appropriate even when the repository keeps two
separate evidence files.

## Boundary

Do not convert runtime probes into hard gates unless the repository already has
very stable signals and clear operational ownership.
