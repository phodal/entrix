---
dimension: performance
weight: 0
tier: deep
threshold:
  pass: 100
  warn: 80
metrics:
  - name: frontend_perf_smoke
    command: npm run test:performance 2>&1
    hard_gate: false
    tier: deep
    execution_scope: ci
    gate: advisory
    kind: holistic
    analysis: dynamic
    stability: noisy
    evidence_type: probe
    confidence: medium
    description: CI perf smoke can surface regressions without pretending local runs are authoritative.
---

# Performance

Keep performance evidence separate from design-system and page-shell checks.

Use `weight: 0` until the repository has a trustworthy runtime budget workflow.
