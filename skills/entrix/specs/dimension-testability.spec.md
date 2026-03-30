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

## Boundary

Keep endpoint-level contract details in `api_contract` when the repository
treats API parity as a first-class surface.

Use `testability` for:

- behavior regression evidence
- unit or integration breadth
- verification completeness
