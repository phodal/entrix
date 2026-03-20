# Contributing

Thanks for contributing to Entrix.

## Development Setup

1. Clone the repository.
2. Create a virtual environment with your preferred tool.
3. Install the package in editable mode with development dependencies:

```bash
python -m pip install -e ".[dev]"
```

## Local Checks

Run the same baseline checks as CI before opening a pull request:

```bash
ruff check .
pytest
python -m build
```

## Pull Requests

- Keep changes scoped to a single concern when possible.
- Update documentation when changing user-facing behavior or public interfaces.
- Add or update tests for behavior changes.
- Use clear commit messages and include rationale in the pull request description.

## Design Direction

Entrix focuses on executable guardrails in the change lifecycle. Contributions should prefer:

- explicit, reviewable configuration over hidden behavior
- deterministic validation over heuristic-only automation
- clear evidence output over opaque pass/fail results

## Reporting Bugs

Use the bug report issue template and include reproduction steps, environment details, and any relevant sample fitness specs or commands.
