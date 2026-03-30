```yaml
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
    evidence_type: probe
    confidence: high
    stability: noisy
    description: Verify tracing signal is visible in staging.
---
```

```md
# Observability

This dimension contributes evidence but does not currently affect the weighted
fitness score.
```
