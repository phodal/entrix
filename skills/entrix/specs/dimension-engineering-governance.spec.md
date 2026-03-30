# Engineering Governance Dimension Spec

Use this when editing `engineering_governance` evidence such as
`docs/fitness/engineering-governance.md`.

## Purpose

Guard repository hygiene, review discipline, and change blast radius.

## Typical Signals

- diff size or blast radius probes
- external link validity
- TODO or FIXME growth
- script sprawl or budget enforcement
- repo policy conformance

## Boundary

This dimension is about safe change process and repository shape, not code
correctness itself.

Move checks elsewhere if they are really about:

- code semantics or compile correctness
- security findings
- API contract behavior
- UI rendering fidelity

## Good Uses

- checks that help decide whether deeper review is needed
- governance rules that should warn or gate before risky changes land
