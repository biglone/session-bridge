# session-bridge

Cross-provider session bridge for Codex-style workflows.

Run commands with `./bin/bridge` (no global pip requirement).

NPM package mode is supported (launcher bootstraps Python runtime automatically).

## Goal

Provide a local bridge so users can switch between different Codex providers/accounts and still recover:

- recent session list
- task context and decisions
- key commands/files changed

This project does not try to reuse vendor-native server session IDs. It rebuilds context in a new session.

## Completed Milestones

1. Plugin metadata and installable skeleton
2. Local unified session store (SQLite)
3. Provider adapters for import/sync
4. Resume bridge command to reconstruct context
5. Consistency checks against git state

## Status

Release-candidate baseline:

- SQLite bridge store
- `bridge list` with provider filter (`--provider`)
- `bridge resume` / `bridge resume-latest` with repository consistency check
- `bridge import-codex` for real local Codex rollout logs
- `bridge import-claude` for real local Claude project logs
- `bridge import-all` to ingest both providers in one command
- `bridge list` / `bridge resume-latest` auto-scan project-local `.codex` histories, then fallback to home `~/.codex` histories (including multi-account subpaths) before reading store
- `bridge resume` / `bridge resume-latest` support `--copy` to copy resume context to clipboard for quick paste into a new Codex session
- `bridge install-plugin` to register into `~/.agents/plugins/marketplace.json`
- `bridge sync-demo` for synthetic test data
- imported text is sanitized for common `token/key/bearer` secret patterns
- release governance docs (`CHANGELOG`, `CONTRIBUTING`, `SECURITY`, `CODE_OF_CONDUCT`)
- CI release gates for tests and package checks

## Quick Start

See [`docs/quickstart.md`](./docs/quickstart.md).
NPM publish/use flow: [`docs/npm-publish.md`](./docs/npm-publish.md).
Release checklist: [`docs/release.md`](./docs/release.md).
Privacy policy: [`docs/privacy.md`](./docs/privacy.md).
Terms: [`docs/terms.md`](./docs/terms.md).

Local release preflight command:

```bash
npm run release:check
```

## Global Install Behavior

When installed globally via npm, plugin registration now runs automatically:

```bash
npm install -g @biglone/session-bridge
```

Auto-registration can be controlled with environment variables:

- `SESSION_BRIDGE_SKIP_AUTO_INSTALL=1`: skip plugin registration
- `SESSION_BRIDGE_AUTO_INSTALL=1`: force plugin registration even for local installs
