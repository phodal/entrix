---
dimension: release_readiness
weight: 25
tier: normal
threshold:
  pass: 100
  warn: 90
metrics:
  - name: cli_help_smoke
    command: python3 -m entrix --help 2>&1
    pattern: "usage: entrix"
    hard_gate: true
    tier: fast
    description: "The local package entrypoint must still render CLI help."

  - name: package_build_pass
    command: python3 -m build --no-isolation 2>&1
    hard_gate: true
    tier: normal
    description: "The project must still produce source and wheel distributions."
---

# Release Readiness

This dimension proves the package is still consumable:

- the CLI can boot
- the package can build from the repository root
