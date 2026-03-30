# Fixture Fitness

This fixture models a repository where:

- `CLAUDE.md` is the only agent entrypoint
- the authoritative test suite is provisioned in CI
- default local `entrix run` still stays green by keeping CI-only checks out of
  the local path
