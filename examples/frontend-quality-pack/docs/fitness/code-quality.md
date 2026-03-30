---
dimension: code_quality
weight: 25
tier: normal
threshold:
  pass: 100
  warn: 90
metrics:
  - name: css_lint_pass
    command: npm run lint:css 2>&1
    hard_gate: true
    tier: fast
    description: CSS naming and maintainability rules must pass.

  - name: token_usage_contract
    command: npm run lint:tokens 2>&1
    hard_gate: true
    tier: fast
    description: Shell and navigation surfaces must keep using approved design tokens.
---

# Code Quality

This layer keeps the cheapest frontend hygiene checks deterministic and local.

Typical uses:

- stylelint or equivalent CSS linting
- token-usage guards
- class-name or layering conventions
