---
dimension: code_quality
weight: 60
tier: normal
threshold:
  pass: 100
  warn: 90
metrics:
  - name: py_compile_pass
    command: python3 -m py_compile app.py 2>&1
    hard_gate: true
    tier: fast
    description: Cheap local syntax validation must pass.
---

# Code Quality

This fixture keeps a cheap local static signal in the default path.
