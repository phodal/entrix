# Manifest Spec

`docs/fitness/manifest.yaml` is the registry of active evidence files.

## Shape

```yaml
schema: fitness-manifest-v1
evidence_files:
  - docs/fitness/code-quality.md
  - docs/fitness/unit-test.md
```

## Responsibilities

- declare which evidence files are active
- give agents one authoritative file list to inspect first
- keep reporting and discovery aligned with what actually exists on disk

## When To Edit

Edit `manifest.yaml` when you:

- add a new evidence file
- remove an evidence file
- rename or move an evidence file
- split one file into multiple files

Do not edit it just because you changed metric contents inside an already
registered file.

## Registration Rules

- use repository-relative paths
- list files that actually exist
- keep the list readable and stable
- if two files intentionally share one dimension, both still need manifest
  entries because manifest tracks files, not abstract dimensions

## Split Guidance

When splitting a file:

1. create the new file
2. move the relevant metrics and narrative
3. update `manifest.yaml`
4. explain the split in the markdown body if the dimension name stays the same

## Anti-Patterns

- using manifest as a category taxonomy
- leaving stale paths after renames
- adding files that contain no executable or evidence value
- assuming one manifest entry must map to one unique dimension name
