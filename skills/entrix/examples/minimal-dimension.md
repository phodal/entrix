```yaml
---
dimension: code_quality
weight: 20
tier: normal
threshold:
  pass: 90
  warn: 80
metrics:
  - name: lint_pass
    command: npm run lint 2>&1
    hard_gate: true
    tier: fast
    description: Lint must pass.
---
```

```md
# Code Quality

Explain what this dimension guards and why these checks belong here.
```
