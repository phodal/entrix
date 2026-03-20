---
dimension: testability
weight: 40
tier: normal
threshold:
  pass: 100
  warn: 90
metrics:
  - name: pytest_pass
    command: pytest 2>&1
    hard_gate: true
    tier: normal
    description: "The repository test suite must pass."
---

# Testability

Behavioral regressions are blocked here.

- changes to `entrix/` should remain covered by `tests/`
- this first dogfooding cut keeps the rule set intentionally minimal and deterministic
