# CI-Scoped Authoritative Metric

Use this pattern when the repository's real suite exists, but the local machine
should not be forced to provision it just to keep default runs green.

```yaml
---
dimension: testability
weight: 40
tier: normal
threshold:
  pass: 100
  warn: 90
metrics:
  - name: import_smoke
    command: python3 -c "import app; print(app.answer())" 2>&1
    hard_gate: true
    tier: fast
    description: Cheap local smoke check.

  - name: pytest_suite
    command: python3 -m pytest -q 2>&1
    hard_gate: true
    tier: normal
    execution_scope: ci
    description: Full suite runs in the provisioned CI environment.
---
```
