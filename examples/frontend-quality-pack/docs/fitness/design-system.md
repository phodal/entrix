---
dimension: design_system
weight: 35
tier: normal
threshold:
  pass: 100
  warn: 90
metrics:
  - name: component_accessibility_smoke
    command: npm run test:accessibility 2>&1
    hard_gate: true
    tier: normal
    execution_scope: ci
    description: Component-level accessibility smoke checks must pass in CI.

  - name: component_visual_contract
    command: npm run test:visual:components 2>&1
    hard_gate: false
    tier: normal
    execution_scope: ci
    gate: soft
    description: Reusable components should keep their visual contract stable.
---

# Design System

This layer is for reusable component quality rather than page-specific flows.

Typical uses:

- component accessibility smoke
- visual-regression or snapshot coverage
- token and slot contract validation
