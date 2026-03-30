# Release Readiness Dimension Spec

Use this when editing `release_readiness` evidence for repositories that already
have a real build, package, docker, or CLI smoke command.

## Purpose

Guard whether the repository can still produce the artifact it intends to ship.

## Typical Signals

- `npm run build`
- package or bundle commands
- docker build commands
- binary build commands
- CLI smoke commands that validate a distributable entrypoint

## When To Create It

Create `release-readiness` when the repository has a meaningful production or
delivery build signal that is not already covered by another dimension.

If a repository has:

- `lint`
- `test`
- `build`

then ignoring `build` is usually a mistake. Give it a dimension or explicitly
document why it is out of scope.

## Boundary

Keep this dimension focused on shipability.

Do not move these concerns here unless they are part of the actual release
surface:

- generic code-quality checks
- endpoint contract tests
- browser e2e flows
- runtime observability probes

## Weight Guidance

For minimal repositories, `release_readiness` is often the easiest place to
close the final weight gap and keep the total at `100` without distorting other
dimension meanings.
