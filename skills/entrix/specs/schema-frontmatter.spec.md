# Schema And Frontmatter Spec

Fitness evidence files are executable markdown documents. Their YAML frontmatter
is the contract that Entrix reads.

## Required Shape

Each evidence file should begin with:

```yaml
---
dimension: code_quality
weight: 18
tier: normal
threshold:
  pass: 90
  warn: 80
metrics:
  - name: example_metric
    command: npm run lint 2>&1
    hard_gate: true
    tier: fast
    description: Example description
---
```

## Required File-Level Fields

- `dimension`: logical quality surface reported by Entrix
- `weight`: contribution to the weighted score; use `0` only for evidence-only
  runtime surfaces
- `tier`: the default tier for the dimension file
- `threshold`: score boundaries for this dimension
- `metrics`: executable checks or probes

## Common Metric Fields

- `name`
- `command`
- `pattern` when success should be matched from output instead of exit code only
- `hard_gate`
- `tier`
- `description`

Entrix's default authoring shape is intentionally small. Start with these
fields unless you have a repository-specific reason to add more.

## Validity Rules

- Use `snake_case` for `dimension` values, for example `code_quality`,
  `api_contract`, `release_readiness`.
- Put `weight` at the file level, not inside individual metrics.
- Use `pattern` when needed; do not invent fields such as `pass_threshold`.
- `hard_gate` belongs on metrics in the common shape used by this repository.
- Keep `run_when_changed` on metrics when you need it; do not invent alternate
  top-level nesting models unless the target Entrix version explicitly supports
  them.
- The markdown body comes after a closing `---` delimiter.

## Manifest Compatibility

For Entrix repositories like this one, `docs/fitness/manifest.yaml` must look
like:

```yaml
schema: fitness-manifest-v1
evidence_files:
  - docs/fitness/code-quality.md
  - docs/fitness/testability.md
```

Do not invent alternate manifest shapes such as:

- `dimensions:`
- nested `tiers:` maps
- inline descriptions inside the manifest

Those may read well to humans but they are not the executable manifest shape
Entrix expects here.

## Advanced Metric Fields

Use advanced fields only when the repository context justifies them:

- `execution_scope`
- `timeout_seconds`
- `gate`
- `evidence_type`
- `confidence`
- `stability`
- `kind`
- `analysis`
- `owner`
- `run_when_changed`
- `waiver`

These fields belong in the frontmatter because they affect execution or policy.
Do not bury them in narrative markdown.

## Authoring Rules

- If weighted dimensions are part of the active score, make the total across
  those files sum to exactly `100`.
- Commands should be runnable from the repository root unless the repo's own
  wrapper intentionally changes working directory.
- Capture stderr with `2>&1` when the repository uses shell commands directly.
- Prefer repository scripts over raw tool invocations when both exist.
- If the repository root does not contain the relevant manifest, prefer root
  wrappers such as `just test` or explicit `--manifest-path` forms over bare
  `cargo` commands.
- For bootstrap output, prefer commands that are locally runnable in the
  current environment. A metric is not a good default fast-tier candidate when
  it depends on optional tooling that is absent locally and the repository does
  not provide a checked-in wrapper that bootstraps or vendors it.
- Use `pattern` only when output matching is more reliable than raw exit code.
- Keep metric names stable; reports and CI fan-out often depend on them.
- If a command is intentionally advisory, express that with metadata instead of
  inventing a fake pass condition.

## Anti-Patterns

- placeholder commands such as `echo TODO`
- overly broad buckets that mix unrelated concerns
- duplicating threshold logic in the markdown body
- adding advanced fields “just in case”
- leaving the weighted dimensions at `90`, `95`, or any other incomplete total
- using metric-level `weight` fields instead of file-level `weight`
- inventing custom keys like `pass_threshold`
- inventing a non-Entrix manifest structure
- writing commands that only work from a subdirectory when Entrix will execute
  from the repository root
- using a locally missing optional tool as a default `fast` hard gate when the
  repository offers no runnable wrapper for it
- changing `dimension` names casually, because downstream reporting may depend
  on them
