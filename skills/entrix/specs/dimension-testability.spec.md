# Testability Dimension Spec

Use this when editing `testability` evidence such as
`docs/fitness/unit-test.md`.

## Purpose

Guard whether the repository has enough executable regression evidence for the
behaviors it changes.

## Typical Signals

- unit test pass
- integration test pass
- graph-derived test radius probes
- evidence matrices that map behavior to tests

## Authoring Pattern

Combine executable frontmatter with a narrative checklist of verified,
blocked, and pending behaviors.

This dimension works well when the markdown body captures:

- critical behaviors
- status per behavior
- exact test file paths
- gaps that still block confidence

## Local vs CI Authority

Prefer locally runnable tests for the default bootstrap path.

If the repository's real test suite is authoritative but the current local
environment is missing repo-specific dev dependencies, treat that as an
environment boundary instead of forcing the suite into a local `fast` hard
gate. In those cases:

- keep any cheap local smoke or scoped tests in local tiers when they truly run
- model the full authoritative suite with `execution_scope: ci` when CI is the
  real place it is provisioned to run
- explain the dependency boundary in the markdown body

For bootstrap output, prefer making plain local `entrix run` green on a fresh
machine. A repository's full pytest or integration suite can still be preserved
as authoritative evidence, but if it depends on dev-only packages that are not
installed locally, it should usually be `execution_scope: ci` rather than a
default local metric.

The same rule applies to coverage generation and similar non-hard-gate checks:
if they are useful evidence but not reliably green in ordinary local runs,
model them as CI-scoped or otherwise keep them from dragging the weighted local
score below the dimension threshold.

## Boundary

Keep endpoint-level contract details in `api_contract` when the repository
treats API parity as a first-class surface.

Use `testability` for:

- behavior regression evidence
- unit or integration breadth
- verification completeness
