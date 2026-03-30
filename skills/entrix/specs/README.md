# Fitness Skill Specs

Use this index the same way `slide-skill/artifact_tool/README.md` is used: it
is a second-level map, not the full implementation.

## Foundation Specs

- `schema-frontmatter.spec.md`: required and optional YAML fields for evidence
  files, plus when to use advanced metric metadata.
- `manifest.spec.md`: how `docs/fitness/manifest.yaml` registers evidence files
  and how to keep it in sync.
- `dimension-boundaries.spec.md`: how to decide whether the change belongs in an
  existing file, a new file in the same dimension, or a brand-new dimension.

## Dimension Specs

- `dimension-code-quality.spec.md`
- `dimension-engineering-governance.spec.md`
- `dimension-testability.spec.md`
- `dimension-security.spec.md`
- `dimension-api-contract.spec.md`
- `dimension-release-readiness.spec.md`
- `dimension-design-system.spec.md`
- `dimension-ui-consistency.spec.md`
- `dimension-runtime.spec.md`

## Examples

- `../examples/minimal-dimension.md`
- `../examples/advisory-probe-metric.md`
- `../examples/runtime-zero-weight-dimension.md`

## Reading Guidance

Read only the specs needed for the current task:

- adding or editing metrics: `schema-frontmatter.spec.md` + one dimension spec
- adding or removing files: `manifest.spec.md` + `dimension-boundaries.spec.md`
- deciding split vs merge: `dimension-boundaries.spec.md`
- adding runtime evidence: `dimension-runtime.spec.md`
- deciding what to do with build or packaging signals:
  `dimension-release-readiness.spec.md`
