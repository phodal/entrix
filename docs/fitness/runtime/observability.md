---
dimension: observability
weight: 0
tier: deep
threshold:
  pass: 100
  warn: 80
metrics:
  - name: tracing_signal_available
    command: ./scripts/obs/check-tracing-signal.sh 2>&1
    pattern: "signal_ok"
    hard_gate: false
    tier: deep
    execution_scope: staging
    gate: advisory
    kind: holistic
    analysis: dynamic
    stability: noisy
    evidence_type: probe
    scope:
      - web
      - runtime
    run_when_changed:
      - src/instrumentation.ts
      - scripts/obs/**
    owner: platform
    confidence: high
    description: Verify that tracing and runtime visibility signals are observable in staging.

  - name: tracing_signal_contract_declared
    command: "printf 'signal_contract: pending\\n'"
    pattern: "signal_contract: pending"
    hard_gate: false
    tier: normal
    execution_scope: ci
    gate: soft
    kind: atomic
    analysis: static
    stability: deterministic
    evidence_type: manual_attestation
    scope:
      - docs
      - runtime
    run_when_changed:
      - docs/fitness/runtime/observability.md
      - src/instrumentation.ts
    owner: platform
    confidence: medium
    description: Keep a lightweight CI-visible contract until a stronger runtime probe is wired in.
---

# Observability

This file demonstrates how runtime visibility evidence should be modeled in
Entrix without forcing staging-oriented signals into the local default run.

Key points:

- `weight: 0` keeps this dimension out of the weighted local score
- `execution_scope: staging` marks the runtime probe as authoritative only in a
  provisioned environment
- `stability: noisy` and `evidence_type: probe` document that the signal is
  runtime-derived rather than a deterministic unit-style check
- the CI-facing contract metric keeps the dimension discoverable even before a
  full staging pipeline is wired in
