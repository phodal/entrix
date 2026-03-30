---
dimension: ui_consistency
weight: 40
tier: normal
threshold:
  pass: 100
  warn: 90
metrics:
  - name: shell_navigation_smoke
    command: npm run test:e2e:shell 2>&1
    hard_gate: true
    tier: normal
    execution_scope: ci
    description: Core shell and navigation journeys must stay stable.

  - name: page_visual_baseline
    command: npm run test:visual:pages 2>&1
    hard_gate: false
    tier: normal
    execution_scope: ci
    gate: soft
    description: High-value pages should keep their visual baselines stable.
---

# UI Consistency

This layer guards page shells and user-visible journeys.

Typical uses:

- desktop shell smoke tests
- page-level visual baselines
- critical-flow browser validation
