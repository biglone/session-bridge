# codex-session-bridge-plugin

Cross-provider session bridge for Codex-style workflows.

## Goal

Provide a local bridge so users can switch between different Codex providers/accounts and still recover:

- recent session list
- task context and decisions
- key commands/files changed

This project does not try to reuse vendor-native server session IDs. It rebuilds context in a new session.

## Planned Milestones

1. Plugin metadata and installable skeleton
2. Local unified session store (SQLite)
3. Provider adapters for import/sync
4. Resume bridge command to reconstruct context
5. Consistency checks against git state

## Status

MVP ready:

- SQLite bridge store
- `bridge list` and `bridge resume`
- `bridge import-codex` for real local Codex rollout logs
- `bridge import-claude` for real local Claude project logs
- `bridge sync-demo` for synthetic test data

## Quick Start

See [`docs/quickstart.md`](./docs/quickstart.md).
