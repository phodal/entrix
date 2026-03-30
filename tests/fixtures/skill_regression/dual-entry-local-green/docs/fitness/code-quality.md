---
dimension: code_quality
weight: 40
tier: normal
threshold:
  pass: 100
  warn: 90
metrics:
  - name: lint_pass
    command: make lint 2>&1
    hard_gate: true
    tier: fast
    description: Root-safe lint wrapper must pass.
---

# Code Quality

This fixture keeps static checks behind the repo's checked-in `make` wrapper.
