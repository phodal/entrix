---
dimension: code_quality
weight: 35
tier: normal
threshold:
  pass: 100
  warn: 90
metrics:
  - name: ruff_pass
    command: ruff check . 2>&1
    hard_gate: true
    tier: fast
    description: "Ruff must pass with no lint errors."

  - name: no_new_debug_prints
    command: |
      base_ref="${ENTRIX_FITNESS_BASE:-HEAD}"
      git diff --unified=0 "$base_ref" -- . ':(exclude)docs/**' 2>/dev/null | \
        grep -E '^\+[^+].*\b(print|pprint)\(' | \
        grep -vE '(^\+\+\+|tests?/|test_)' | \
        wc -l | \
        awk '{print "new_debug_prints:", $1}'
    pattern: "new_debug_prints: 0"
    tier: fast
    description: "Production code should not grow accidental debug prints."
---

# Code Quality

This dimension keeps the low-cost hard gates deterministic:

- lint must stay green
- debug-only output should not leak into non-test Python changes
