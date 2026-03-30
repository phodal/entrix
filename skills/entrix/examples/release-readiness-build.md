```yaml
---
dimension: release_readiness
weight: 10
tier: normal
threshold:
  pass: 90
  warn: 80
metrics:
  - name: build_pass
    command: npm run build 2>&1
    hard_gate: true
    tier: normal
    description: Production build must pass.
---
```

```md
# Release Readiness

This dimension verifies the repository can still produce its intended build
artifact.
```
