# File-Length Hook Template

Use this template to fail `pre-commit` when staged source files exceed a fixed line budget.

## 1. Install `entrix`

```bash
pip install entrix
```

For local development against the repository checkout:

```bash
pip install -e tools/entrix
```

## 2. Copy the budget config

Save [`file_budgets.pre_commit.json`](./file_budgets.pre_commit.json) into your repository, for example at `tools/entrix/file_budgets.pre_commit.json`.

Adjust these keys as needed:

- `default_max_lines`: fallback file limit
- `include_roots`: directories to scan
- `extensions`: tracked source extensions
- `extension_max_lines`: per-extension overrides
- `excluded_parts`: ignored build/vendor paths

## 3. Wire it into `.husky/pre-commit`

```sh
#!/usr/bin/env sh

if [ -n "$SKIP_HOOKS" ]; then
  echo "SKIP_HOOKS is set, skipping pre-commit checks"
  exit 0
fi

PYTHONPATH=tools/entrix python3 -m entrix hook file-length \
  --config tools/entrix/file_budgets.pre_commit.json \
  --staged-only \
  --strict-limit
```

If you also want lint in the same hook, run it after the file-length guard.

## 4. Expected failure output

```text
file_budget_checked: 1
file_budget_violations: 1
current file length 2383 exceeds limit 1500: src/app/page.tsx
Refactor the oversized file before commit.
```

## CLI options

- `--staged-only`: evaluate only files currently staged in the git index
- `--strict-limit`: ignore HEAD baseline ratcheting and enforce the configured limit directly
- `files...`: optional explicit relative paths when you want to run the check outside Git hooks
