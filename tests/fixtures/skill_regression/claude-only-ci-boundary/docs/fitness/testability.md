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
    description: Cheap local import smoke keeps default runs green.

  - name: pytest_suite
    command: python3 -m pytest -q 2>&1
    hard_gate: true
    tier: normal
    execution_scope: ci
    description: The authoritative suite is provisioned in CI.
---

# Testability

This fixture preserves a real CI-owned suite without making default local runs
depend on dev-only provisioning.
