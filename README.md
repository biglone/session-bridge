# codex-session-bridge-plugin

Cross-provider session bridge for Codex-style workflows.

Run commands with `./bin/bridge` (no global pip requirement).

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
- `bridge list` with provider filter (`--provider`)
- `bridge resume` / `bridge resume-latest` with repository consistency check
- `bridge import-codex` for real local Codex rollout logs
- `bridge import-claude` for real local Claude project logs
- `bridge import-all` to ingest both providers in one command
- `bridge install-plugin` to register into `~/.agents/plugins/marketplace.json`
- `bridge sync-demo` for synthetic test data
- imported text is sanitized for common `token/key/bearer` secret patterns

## Quick Start

See [`docs/quickstart.md`](./docs/quickstart.md).
