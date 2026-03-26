---
name: entrix
description: Set up entrix in the current repository by discovering the real lint, test, coverage, build, contract, and review commands, generating docs/fitness, and wiring fitness into AGENTS.md or CLAUDE.md. Use when the user asks to bootstrap entrix, add fitness specs, create review-trigger rules, add agent-facing fitness instructions, or make entrix validation runnable in a project.
---

# Entrix Setup

Goal: leave the current repository with a working `docs/fitness/` configuration
that matches the real project tooling, can be validated immediately, and is
discoverable from the repository's agent entrypoint.

## Workflow

### 1. Inspect the target repository first

Work from the repository root the user wants to bootstrap.

Read the files that reveal the real toolchain and quality gates:

- `AGENTS.md`
- `CLAUDE.md`
- `package.json`
- `pyproject.toml`
- `Cargo.toml`
- `Makefile`, `justfile`, or equivalent task runners
- `.github/workflows/**`
- any existing `docs/fitness/**`

Prefer existing package scripts or CI commands over inventing new ones.

### 2. Derive the executable checks

Build the fitness spec from commands that already exist in the repository.

Preferred order:

1. package-manager or task-runner scripts already used by the repo
2. commands copied from CI workflows
3. direct tool commands only when the repository clearly uses them

Rules:

- never invent a command that does not exist
- never write placeholder metrics such as `echo TODO`
- use `hard_gate: true` only for checks that should really block progress
- keep one concern per dimension file
- make the weights of all dimension files sum to `100`
- prefer stable repository scripts over raw tool invocations when both exist

### 3. Make fitness discoverable to agents

Agents should be able to find fitness from the repository entrypoint instead of
guessing that `docs/fitness/` exists.

Update agent-facing docs in this order:

1. if `AGENTS.md` exists, add a short `Fitness Function` or `Entrix` section
2. else if `CLAUDE.md` exists, add the same section there
3. else create `AGENTS.md` with a minimal project entry and a fitness section

Keep the entrypoint short. It should point to `docs/fitness/README.md` and tell
agents when to run `entrix`.

Minimum content:

- `docs/fitness/README.md` is the fitness rulebook
- `entrix run --dry-run` for inspection
- `entrix run --tier fast` after normal source edits
- `entrix run --tier normal` after behavior, API, shared-module, or workflow changes

Do not duplicate the full rulebook into `AGENTS.md` or `CLAUDE.md`. Add an
entrypoint, not a second copy.

### 4. Create or update `docs/fitness/`

Minimum output:

- `docs/fitness/README.md`
- `docs/fitness/manifest.yaml`
- `docs/fitness/review-triggers.yaml`
- at least `code-quality.md` and `testability.md`

Create these files explicitly. Do not stop after only writing the dimension
files.

Always create dimensions from repository signals, not from generic expectations.

Recommended discovery matrix:

- `code-quality.md`
  - use existing `lint`, `typecheck`, `clippy`, formatting, file-budget, duplicate-code, or static-analysis commands
- `testability.md`
  - use existing unit/integration test commands such as `npm test`, `vitest`, `pytest`, `cargo test`
- `coverage.md`
  - create only if the repository already has a coverage script, coverage CI job, or coverage tools such as `--coverage`, `pytest --cov`, `coverage xml`, `cargo llvm-cov`
- `release-readiness.md`
  - create when the repository has a real build, package, docker, or CLI smoke command
- `security.md`
  - create only if the repository already runs or clearly installs tools such as `npm audit`, `cargo audit`, `pip-audit`, `semgrep`, `trivy`, `bandit`
- `api-contract.md`
  - create when the repository has `openapi.*`, `api-contract.*`, schema validation scripts, parity checks, or generated client/server contract checks
- `e2e.md` or UI-specific dimensions
  - create only when the repository already has Playwright, Cypress, browser automation, or other end-to-end commands
- `performance.md` or `observability.md`
  - create only when the repository already has benchmark, load, profiling, runtime probe, or telemetry checks

If coverage or contract checks already exist, do not hide them inside a vague
`testability` bucket. Give them their own dimension file unless the repository
is intentionally tiny.

Each dimension file must use executable frontmatter:

- `dimension`
- `weight`
- `tier`
- `threshold`
- `metrics`

The YAML frontmatter must start with `---` and end with a closing `---` before
any markdown body text. Do not omit the closing delimiter.

Each metric should usually include:

- `name`
- `command`
- `hard_gate`
- `tier`
- `description`

Add advanced fields only when the repository context justifies them.

Use this shape when the repository does not already have fitness files:

```yaml
---
dimension: code_quality
weight: 35
tier: normal
threshold:
  pass: 100
  warn: 90
metrics:
  - name: lint_pass
    command: npm run lint 2>&1
    hard_gate: true
    tier: fast
    description: Lint must pass.
---

# Code Quality

Explain what this dimension guards.
```

`manifest.yaml` must include the schema header and repository-relative evidence
paths:

```yaml
schema: fitness-manifest-v1
evidence_files:
  - docs/fitness/code-quality.md
  - docs/fitness/testability.md
```

### 5. Write review triggers that match real risk

Use only rules that are justified by the target repository, for example:

- `changed_paths` for core runtime or orchestration directories
- `sensitive_file_change` for contracts, schemas, release config, or governance
- `cross_boundary_change` when the repository has clear architectural boundaries
- `diff_size` for large changes
- `evidence_gap` only when there is a meaningful evidence mapping to enforce

Do not cargo-cult the Routa.js paths into another repository.

Use the exact entrix keys from the schema. For changed-file rules use `paths`,
not `patterns`. Prefer `action: require_human_review` unless the repository
already uses another action string intentionally.

Minimal shape:

```yaml
review_triggers:
  - name: oversized_change
    type: diff_size
    max_files: 10
    max_added_lines: 400
    max_deleted_lines: 250
    severity: medium
    action: require_human_review
```

### 6. Keep the narrative useful but short

`README.md` should explain:

- how to run `entrix validate`
- when to use `fast`, `normal`, and `deep`
- which dimension files exist
- which files are listed in `manifest.yaml`
- which agent entry file points to the fitness rulebook
- how dimensions map to real repository commands

`README.md` is required. Do not omit it even for a minimal bootstrap.

The markdown body below each frontmatter block should explain intent, ownership,
or guardrail scope, but the frontmatter is the executable source of truth.

### 7. Validate before finishing

Pick the correct invocation in this order:

1. `entrix ...` if the command already exists
2. `uvx --from entrix entrix ...` when `uvx` is available
3. `python3 -m entrix ...` when the package is installed but the console script is unavailable

Then run:

```bash
entrix validate
entrix run --dry-run
```

If the fast tier is cheap and runnable, also run:

```bash
entrix run --tier fast
```

If validation fails because of the files you wrote, fix them before stopping.
If validation fails because the repository's own commands are broken or missing,
keep the generated config aligned to reality and report the failing command.
If validation reports `0%` total weight or `No metrics matched`, read the files
back and check for broken frontmatter delimiters or wrong schema keys.

After validation, read back:

- the agent entry file you changed
- `docs/fitness/README.md`
- `docs/fitness/manifest.yaml`
- every generated dimension file
- `docs/fitness/review-triggers.yaml`

Verify that agent docs mention fitness and that manifest entries match the files
that actually exist.

## Quality Bar

The skill is complete only when all of the following are true:

- `AGENTS.md` or `CLAUDE.md` points to the fitness rulebook
- `docs/fitness/` exists and is coherent
- `docs/fitness/README.md` exists
- weights sum to `100`
- every metric maps to a real repository command
- `manifest.yaml` lists the active evidence files
- `manifest.yaml` includes `schema: fitness-manifest-v1`
- `review-triggers.yaml` matches the repository's actual risk boundaries
- common repository signals such as coverage, security, API contract, build, and e2e checks were considered explicitly
- validation has been attempted with the best available `entrix` invocation

## Avoid

- leaving fitness undiscoverable from agent entry docs
- copying example paths, commands, or risk boundaries without inspection
- collapsing coverage, contract, security, and release checks into one generic file when the repository already separates them
- inventing coverage thresholds or security tools that the repository does not actually use
- generating a verbose tutorial instead of completing the setup work
- turning the skill into meta-instructions about how to invoke the skill
