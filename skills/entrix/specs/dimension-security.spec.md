# Security Dimension Spec

Use this when editing `security` evidence such as
`docs/fitness/security.md`.

## Purpose

Guard dependency risk and security scanning outcomes.

## Typical Signals

- `npm audit`
- `cargo audit`
- `pip-audit`
- semgrep
- SARIF-producing scanners

Only use a security tool when the repository already shows direct evidence for
it in:

- CI workflows
- checked-in task runners or scripts
- checked-in security docs
- existing fitness files

## Hard-Gate Guidance

Reserve hard gates for truly blocking findings, typically critical
vulnerabilities or repository policies with clear merge-stop meaning.

## Boundary

Do not move generic lint or code-quality issues here just because they “feel
unsafe”. Security metrics should reflect actual security tools, policies, or
findings.

## Anti-Patterns

- adding `cargo audit` because it is common in Rust repos when the repository
  only runs `cargo deny`
- inferring a security scanner from ecosystem conventions instead of repository
  evidence
