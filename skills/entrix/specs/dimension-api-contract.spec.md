# API Contract Dimension Spec

Use this when editing `api_contract` or contract-adjacent evidence such as
`docs/fitness/rust-api-test.md` or `docs/fitness/api-contract.md`.

## Purpose

Guard externally visible behavior that clients and integrations depend on.

## Typical Signals

- API parity checks
- schema validation
- endpoint behavior matrices
- request or response compatibility tests
- negative-path coverage for contract failures

## Split Guidance

It is acceptable for one repository to keep:

- one evidence file for executable API tests
- another evidence file for broader compatibility or evolvability rules

The important thing is that the split is explicit and discoverable.

## Boundary

Do not bury contract checks inside generic test buckets when the repository has
clear API-facing guarantees.
