# Entry Document Topology

Use this decision table when deciding which agent entry documents to update.

| Repository state | Required result |
| --- | --- |
| `AGENTS.md` exists, `CLAUDE.md` missing | update `AGENTS.md` only |
| `CLAUDE.md` exists, `AGENTS.md` missing | update `CLAUDE.md` only |
| both exist | update both and keep the fitness section identical |
| neither exists | create only `AGENTS.md` |

Never create an extra second entry document just because it exists in other
repositories.
