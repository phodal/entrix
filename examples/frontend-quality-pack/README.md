# Frontend Quality Pack

This example shows how a consuming web application can express layered frontend
quality gates in normal Entrix files without hardcoding product-specific policy
into the Entrix engine.

It models four surfaces:

- `code_quality`: CSS and token-hygiene style checks
- `design_system`: component-layer accessibility and visual-contract checks
- `ui_consistency`: page-shell and browser-flow consistency checks
- `performance`: zero-weight runtime/perf smoke guidance

## Layout

Copy the `docs/fitness/` directory into your application repository and adapt
the commands to your own scripts:

```text
docs/fitness/
  manifest.yaml
  code-quality.md
  design-system.md
  ui-consistency.md
  performance.md
  review-triggers.yaml
```

## Suggested Commands

```bash
entrix validate
entrix run --tier fast
entrix run --tier normal --scope ci --min-score 0
entrix review-trigger --base HEAD~1 --config docs/fitness/review-triggers.yaml
```

## Why This Pack Exists

The point is not to prescribe Storybook, Chromatic, Playwright, or Lighthouse as
mandatory tooling. The point is to show a reusable shape:

- cheap local code-quality checks
- CI-scoped component and page checks
- zero-weight performance evidence until runtime collection is trustworthy
- review-trigger rules that escalate risky shell and navigation changes
