# ADR 0001: Git History Signals for Long-File Analysis

- Status: Accepted
- Date: 2026-03-22

## Context

Entrix already exposes `analyze long-file` as a structural reporter for oversized files.
The initial output focused on:

- file line count
- budget limit
- top-level class-like declarations
- top-level functions grouped by size

That shape is useful for identifying where a large file can be split, but it is still incomplete as a refactoring priority signal.

Not every long file is equally urgent:

- some long files are central and change often
- some long files are legacy but mostly stable
- some long files are large because they aggregate definitions or protocols but rarely move

If Entrix only reports size and structure, it risks over-prioritizing files that are large but operationally quiet.

## Decision

Entrix long-file analysis should include Git-based change history as an additional physical design signal.

The first signal is:

- `commitCount`: number of commits touching the file, based on `git log --follow -- <file>`

This signal is added to both:

- JSON output from `entrix analyze long-file --json`
- human-readable terminal output

## Rationale

This follows a physical design view of the codebase:

- logical design explains what the system means
- physical design explains how the code is organized and how it actually changes over time

Git history helps reveal which files are structurally important in practice, not just in theory.

For refactoring triage, the combination matters more than any single metric:

- long file + frequent commits = unstable hotspot, higher refactor priority
- long file + few commits = lower urgency, possibly not a core business surface

This framing is aligned with the idea discussed in Phodal's article on Git-based physical code analysis:

- <https://www.phodal.com/blog/git-based-code-physical-design/>

The key idea is not that Git history replaces structural analysis.
It complements it by turning "large and awkward" into "large, awkward, and frequently stressed by change".

## Consequences

Positive:

- better prioritization for long-file refactors
- lower false urgency for stable legacy files
- more credible input for LLM-guided refactoring prompts
- a clearer bridge between structural analysis and repository history

Tradeoffs:

- `commitCount` is cumulative and does not distinguish recent activity from historical churn
- renamed files only work as well as `git log --follow` can reconstruct history
- commit count is still a proxy, not a direct measure of business criticality

## Follow-up

Possible future extensions:

- `recentCommitCount90d` or other time-windowed activity metrics
- combined heuristics such as `lineCount * recentCommitCount`
- module-level aggregation to detect unstable directories, not only unstable files
- reporter guidance that ranks oversized files by both size and change frequency
