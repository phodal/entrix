---
name: entrix
description: Set up or repair Entrix fitness specs in the current repository by discovering real quality signals, generating docs/fitness, and iterating with entrix validation until the result is executable. Use when the user asks to bootstrap entrix, add or split fitness dimensions, repair invalid fitness specs, or make docs/fitness actually runnable.
license: MIT
---

# Entrix Skill

Goal: leave the target repository with a working `docs/fitness/` configuration
that matches real tooling, is discoverable from the repository entrypoint, and
passes Entrix validation instead of merely looking plausible.

This skill now uses a small entrypoint plus reusable spec files under
`specs/`. Read those specs instead of improvising schema details.

## Skill Folder Contents

- `specs/README.md`: second-level map of the available specs
- `specs/schema-frontmatter.spec.md`: Entrix-compatible evidence file shape
- `specs/manifest.spec.md`: required `manifest.yaml` shape
- `specs/dimension-boundaries.spec.md`: how to split or merge dimensions
- `specs/dimension-*.spec.md`: per-dimension guidance
- `examples/`: copyable minimal snippets
- `../../tests/fixtures/skill_regression/`: bundled repository profiles used by
  the skill regression harness

## Read Order

For any bootstrap or repair task, read in this order:

1. target repository `AGENTS.md` and `CLAUDE.md` if present
2. target repository manifests and task runners:
   `package.json`, `pyproject.toml`, `Cargo.toml`, `justfile`, `Makefile`
3. target repository `.github/workflows/**`
4. existing target `docs/fitness/**` if present
5. this skill's `specs/README.md`
6. only the specific `specs/dimension-*.spec.md` files needed for the task
7. matching `examples/*.md` when entry-document or CI-boundary behavior is
   ambiguous

## Core Rules

- Use real repository signals only. Do not invent commands.
- Prefer repository-root-safe wrappers such as `just`, `make`, `npm run`, or
  `cargo --manifest-path ...` when a bare tool invocation would depend on a
  subdirectory working directory.
- Prefer checked-in scripts and CI-established commands over plausible
  defaults.
- For bootstrap output, prefer commands that are runnable in the current local
  environment, not only commands that look semantically correct from CI or repo
  structure.
- Only create a security metric when the repository shows direct evidence for
  that tool in scripts, CI, or checked-in docs. Do not add common scanners by
  assumption.
- If a candidate metric depends on optional local tooling that is not installed
  and no checked-in wrapper self-bootstraps it, do not leave it as a default
  `fast` hard gate. Prefer a locally runnable wrapper, another repo-established
  signal, or explicit blocker reporting.
- If a repository's real test or build command is authoritative but requires
  repo-specific dev dependencies or CI provisioning that are missing locally,
  do not force it into the default local fast tier. Prefer a locally runnable
  smoke check plus a CI-scoped authoritative metric. Prefer `execution_scope:
  ci` over leaving that command as a default local metric that will fail on a
  fresh machine.
- Treat missing compiler/runtime versions the same way. If the repository
  requires a newer Rust, Node, Python, or similar toolchain than the current
  machine provides, do not keep those commands as default local metrics unless
  the user explicitly wants that blocker preserved.
- Use Entrix-compatible schema only. Do not invent alternate manifest or
  frontmatter shapes.
- If weighted dimensions participate in scoring, their file-level weights must
  sum to exactly `100`.
- If the repository has a real build, package, docker, or CLI smoke signal,
  consider `release_readiness` explicitly.
- If the repository has a contract or schema surface, consider
  `api_contract` explicitly.

## Schema Rules

Use the standard Entrix shapes only:

- each evidence file uses YAML frontmatter with:
  - `dimension`
  - `weight`
  - `tier`
  - `threshold`
  - `metrics`
- dimensions use `snake_case`, for example:
  - `code_quality`
  - `testability`
  - `release_readiness`
  - `api_contract`
- `manifest.yaml` uses:

```yaml
schema: fitness-manifest-v1
evidence_files:
  - docs/fitness/code_quality.md
  - docs/fitness/testability.md
```

Never use:

- `dimensions:`
- metric-level `weight`
- `pass_threshold`
- bare filenames in `manifest.yaml`
- hyphenated dimension ids when the repository already uses Entrix-style
  snake_case

## Workflow

### 1. Inspect the target repository

Determine the real executable signals from:

- package manager scripts
- task runners such as `just`
- CI workflows
- checked-in helper scripts
- existing `docs/fitness/**`

Preferred command order:

1. repository task runner or package scripts already used locally
2. root-safe commands copied from CI
3. direct tool commands only when the repo clearly uses them and the working
   directory is unambiguous

### 2. Design dimensions from actual surfaces

Common dimension families:

- `code_quality`
- `testability` or `test_coverage`
- `security`
- `release_readiness`
- `api_contract`
- `ui_consistency`
- `design_system`
- runtime evidence such as `observability` or `performance`

Keep one stable concern per file. If the repository already separates concerns,
do not collapse them into one vague file.

### 3. Write discoverable fitness docs

Minimum output for a new repository:

- `docs/fitness/README.md`
- `docs/fitness/manifest.yaml`
- `docs/fitness/review-triggers.yaml`
- at least `code_quality` and `testability` or another clearly justified test
  dimension

Keep the repository entrypoint short:

1. if `AGENTS.md` exists, add or repair a short fitness section there
2. if `CLAUDE.md` exists, add or repair the same short fitness section there too
3. if both exist, keep them consistent instead of updating only one
4. if neither exists, create a minimal `AGENTS.md`

Creation rules are strict:

- do not create a new `CLAUDE.md` when the repository did not already have one
- do not create a new `AGENTS.md` when `CLAUDE.md` already exists as the sole
  agent entrypoint unless the user explicitly asks for both
- if neither exists, create only `AGENTS.md`

Do not duplicate the whole rulebook into the entrypoint file.
The goal is discoverability from every agent entry document the repository
already uses, not just the first one you happen to see.

### 4. Validate and iterate before stopping

After generating or repairing `docs/fitness/`, you MUST validate it yourself.

Use the best available Entrix invocation in this order:

1. `entrix ...`
2. `uvx --from entrix entrix ...`
3. `python3 -m entrix ...`

Run:

```bash
entrix validate
entrix run --dry-run
```

If a `fast` tier exists or the generated commands are cheap, also run:

```bash
entrix run --tier fast
```

If validation fails because of files you wrote, fix them and re-run validation.
Do not stop after the first draft.

Mandatory repair loop:

1. generate or repair `docs/fitness`
2. run `entrix validate`
3. if it fails, read back `manifest.yaml` and every evidence file
4. fix schema, weights, paths, and command locality issues
5. run `entrix validate` again
6. run `entrix run --dry-run`
7. if validation passes, run `entrix run --tier fast` whenever that tier exists
   or the generated commands are cheap enough to execute locally
8. if the fast tier fails because of generated command locality or invented
   signals, repair and re-run validation
9. if the fast tier fails because a generated metric requires optional tooling
   that is not locally runnable, replace it with a repo-safe runnable signal,
   move it out of the bootstrap fast tier, or report the blocker explicitly
10. if a repository's real test/build command exists but fails only because the
    local environment lacks repo-specific dev dependencies, keep it out of the
    default local fast tier and model it with `execution_scope: ci` or another
    non-local authority boundary when appropriate
11. stop only when validation passes and the generated config is runnable, or
   you have a concrete repository blocker

### 5. Typical failure patterns to fix

When validation reports `0%` total weight or `No metrics matched`, check for:

- wrong frontmatter delimiters
- wrong manifest shape
- manifest entries using bare filenames instead of repo-relative paths
- non-standard keys such as `pass_threshold`
- missing file-level `weight`
- dimension names that do not match Entrix conventions

When generated commands are semantically wrong, check for:

- root-level command run against a repo whose actual `Cargo.toml` lives in a
  subdirectory
- repo guidance that prefers `just test` over a raw `cargo nextest` variant
- fabricated security tools not actually used by the repository
- build commands that differ from the repository's real release/build path
- commands copied from CI that silently depended on a workflow-specific working
  directory
- optional toolchain checks that are real in principle but not locally runnable
  from the target repository without extra undeclared setup
- real test commands that need dev dependencies the current local environment
  has not installed, even though CI or contributor docs expect them
- existing `AGENTS.md` and `CLAUDE.md` files where the generated output updated
  only one of them
- repositories with only `CLAUDE.md` where the generated output invented a new
  `AGENTS.md`

## Quality Bar

The skill is complete only when all of the following are true:

- `docs/fitness/` exists and is coherent
- `docs/fitness/README.md` exists
- `manifest.yaml` includes `schema: fitness-manifest-v1`
- `manifest.yaml` lists repo-relative evidence file paths
- every existing repository entry document among `AGENTS.md` and `CLAUDE.md`
  points to the fitness docs consistently
- no extra agent entry document was created unless the user explicitly asked for
  it
- weights sum to `100`
- every metric maps to a real repository command
- every `fast` hard gate chosen by the skill is locally runnable, or is called
  out as a concrete repository blocker
- commands that are authoritative only in CI or provisioned environments are
  modeled as such instead of pretending to be default local fast checks
- default local `entrix run` does not execute CI-only metrics unless the user
  explicitly asks for that scope
- default local `entrix run` passes as a whole; soft or advisory metrics that
  are expected to fail locally are CI-scoped, zero-weight, or otherwise modeled
  so they do not sink the local score below threshold
- validation has been attempted with Entrix itself
- the generated config has been exercised beyond `dry-run` whenever a cheap
  fast-tier run is available
- validation failures caused by generated files have been repaired

## Avoid

- leaving fitness undiscoverable from agent entry docs
- inventing alternate schemas that Entrix does not parse
- inventing security or coverage tools the repository does not use
- using raw subdirectory-dependent commands when repo-root-safe wrappers exist
- stopping after producing files that merely look reasonable
