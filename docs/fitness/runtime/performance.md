---
dimension: performance
weight: 0
tier: deep
threshold:
  pass: 100
  warn: 80
metrics:
  - name: latency_budget_probe_defined
    command: "printf 'latency_budget: pending\\n'"
    pattern: "latency_budget: pending"
    hard_gate: false
    tier: normal
    execution_scope: ci
    gate: advisory
    kind: holistic
    analysis: dynamic
    stability: noisy
    evidence_type: probe
    scope:
      - web
      - api
      - runtime
    run_when_changed:
      - docs/fitness/runtime/performance.md
      - src/**
      - crates/**
    owner: platform
    confidence: low
    description: Reserve a place for CI-visible latency budget evidence without pretending local timing is authoritative.

  - name: runtime_budget_signal_unavailable
    command: graph:runtime-budget
    hard_gate: false
    tier: deep
    execution_scope: prod_observation
    gate: advisory
    kind: holistic
    analysis: dynamic
    stability: noisy
    evidence_type: probe
    scope:
      - runtime
      - performance
    run_when_changed:
      - docs/fitness/runtime/performance.md
      - src/**
      - crates/**
    owner: platform
    confidence: unknown
    description: Example placeholder for a future production-observation probe that currently resolves to UNKNOWN.
---

# Performance

This file demonstrates that performance evidence is not the same thing as
observability evidence.

Key points:

- performance checks stay `weight: 0` until the repo has trustworthy runtime
  collection
- `execution_scope: ci` or `prod_observation` avoids claiming local developer
  machines are authoritative for latency budgets
- the `runtime_budget_signal_unavailable` metric intentionally models a future
  probe slot that can resolve to `UNKNOWN` until real runtime data exists
