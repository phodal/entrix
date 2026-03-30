#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE_ROOT="$ROOT_DIR/tests/fixtures/skill_regression"
ARTIFACT_DIR="$ROOT_DIR/.artifacts/skill-regression"
RUN_FIXTURES=0
declare -a TARGETS=()

usage() {
  cat <<'EOF'
Usage:
  bash scripts/skill_regression.sh --fixtures
  bash scripts/skill_regression.sh /abs/path/to/repo [/abs/path/to/another-repo]

Modes:
  --fixtures                Validate bundled fixture repositories without Claude.
  --artifacts-dir <path>    Override the log output directory.
  -h, --help                Show this help text.

Path mode:
  1. Injects the bundled /entrix skill into the target repo as .claude/skills/entrix
  2. Runs claude -p with /entrix to bootstrap or repair docs/fitness
  3. Verifies the result with entrix validate, entrix run --dry-run,
     entrix run --tier fast, and entrix run
EOF
}

while (($# > 0)); do
  case "$1" in
    --fixtures)
      RUN_FIXTURES=1
      ;;
    --artifacts-dir)
      shift
      ARTIFACT_DIR="${1:?missing path for --artifacts-dir}"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      TARGETS+=("$1")
      ;;
  esac
  shift
done

if (($# > 0)); then
  TARGETS+=("$@")
fi

if [[ "$RUN_FIXTURES" -eq 0 && "${#TARGETS[@]}" -eq 0 ]]; then
  usage
  exit 1
fi

mkdir -p "$ARTIFACT_DIR"

if command -v entrix >/dev/null 2>&1; then
  ENTRIX_CMD=(entrix)
elif command -v uvx >/dev/null 2>&1; then
  ENTRIX_CMD=(uvx --from entrix entrix)
else
  ENTRIX_CMD=(python3 -m entrix)
fi

if command -v claude >/dev/null 2>&1; then
  CLAUDE_CMD=(claude -p --permission-mode bypassPermissions)
else
  CLAUDE_CMD=()
fi

slugify() {
  printf '%s' "$1" | tr '/: ' '___'
}

run_logged() {
  local label="$1"
  local logfile="$2"
  local cwd="$3"
  shift 3

  echo "==> $label"
  if ! (
    cd "$cwd"
    "$@"
  ) >"$logfile" 2>&1; then
    cat "$logfile"
    return 1
  fi
}

run_entrix_logged() {
  local label="$1"
  local logfile="$2"
  local cwd="$3"
  shift 3
  run_logged "$label" "$logfile" "$cwd" "${ENTRIX_CMD[@]}" "$@"
}

run_fixture_repo() {
  local repo="$1"
  local name
  name="$(basename "$repo")"
  local repo_artifacts="$ARTIFACT_DIR/fixtures/$name"
  local worktree

  mkdir -p "$repo_artifacts"
  worktree="$(mktemp -d "${TMPDIR:-/tmp}/entrix-fixture-${name}.XXXXXX")"
  cp -R "$repo/." "$worktree"
  (
    cd "$worktree"
    git init -q
  )

  echo
  echo "### Fixture: $name"
  echo "worktree: $worktree"

  run_entrix_logged "validate $name" "$repo_artifacts/validate.log" "$worktree" validate
  run_entrix_logged "dry-run $name" "$repo_artifacts/dry-run.log" "$worktree" run --dry-run
  run_entrix_logged "fast tier $name" "$repo_artifacts/fast.log" "$worktree" run --tier fast
  run_entrix_logged "default run $name" "$repo_artifacts/run.log" "$worktree" run

  if [[ "$name" == "claude-only-ci-boundary" ]]; then
    run_entrix_logged "ci scope $name" "$repo_artifacts/ci.log" "$worktree" run --scope ci --min-score 0
  fi
}

run_fixture_smoke() {
  if [[ ! -d "$FIXTURE_ROOT" ]]; then
    echo "Fixture root not found: $FIXTURE_ROOT" >&2
    exit 1
  fi

  local fixture
  for fixture in "$FIXTURE_ROOT"/*; do
    [[ -d "$fixture" ]] || continue
    run_fixture_repo "$fixture"
  done
}

run_forward_repo() {
  local repo="$1"
  local name
  name="$(slugify "$repo")"
  local repo_artifacts="$ARTIFACT_DIR/forward/$name"

  if [[ "${#CLAUDE_CMD[@]}" -eq 0 ]]; then
    echo "claude CLI is not available; cannot run forward validation for $repo" >&2
    exit 1
  fi

  mkdir -p "$repo_artifacts"
  echo
  echo "### Forward Validation: $repo"

  (
    local skill_dir="$repo/.claude/skills"
    local skill_link="$skill_dir/entrix"
    mkdir -p "$skill_dir"
    ln -sfn "$ROOT_DIR/skills/entrix" "$skill_link"
    trap 'rm -f "$skill_link"' EXIT

    local prompt
    prompt=$'Use /entrix in this repository to generate or repair docs/fitness.\nRequirements:\n- inspect real repository signals only\n- keep default local entrix run green\n- update every existing agent entry document among AGENTS.md and CLAUDE.md consistently\n- create only AGENTS.md if neither entry doc exists\n- model CI-only or provisioned-only checks with execution_scope: ci\n- iterate with entrix validate, entrix run --dry-run, entrix run --tier fast when available, and plain entrix run until the local result is executable'

    run_logged "claude /entrix $repo" "$repo_artifacts/claude.log" "$repo" "${CLAUDE_CMD[@]}" "$prompt"
    run_entrix_logged "validate $repo" "$repo_artifacts/validate.log" "$repo" validate
    run_entrix_logged "dry-run $repo" "$repo_artifacts/dry-run.log" "$repo" run --dry-run
    run_entrix_logged "fast tier $repo" "$repo_artifacts/fast.log" "$repo" run --tier fast
    run_entrix_logged "default run $repo" "$repo_artifacts/run.log" "$repo" run
    run_logged "status $repo" "$repo_artifacts/status.log" "$repo" git status --short -- docs/fitness AGENTS.md CLAUDE.md
  )
}

if [[ "$RUN_FIXTURES" -eq 1 ]]; then
  run_fixture_smoke
fi

if [[ "${#TARGETS[@]}" -gt 0 ]]; then
  for target in "${TARGETS[@]}"; do
    run_forward_repo "$target"
  done
fi

echo
echo "Skill regression completed. Logs: $ARTIFACT_DIR"
