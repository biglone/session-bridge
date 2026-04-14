# session-bridge

Cross-provider session continuity toolkit for Codex workflows.

Run commands with `./bin/bridge` (no global pip requirement).

NPM package mode is supported (launcher bootstraps Python runtime automatically).

Global install:

```bash
npm install -g @biglone/session-bridge
```

CLI aliases after global install:
- `session-bridge` (primary)
- `sb` (short alias)
- `csbridge`
- `codex-session-bridge`

## Why this package

When you switch model providers/accounts, native `/resume` flows are often provider-isolated.
`session-bridge` helps you recover and continue project context safely by combining:

- unified session indexing across project `.codex` and home `~/.codex` histories
- `resume-latest` context reconstruction with clipboard-friendly output
- SSH-first workflow support (`copy-local` + OSC52 fallback)
- provider shim apply/run/restore for temporary cross-provider `/resume` compatibility
- import pipelines for Codex rollout logs and Claude Code project logs

Typical search terms:
`codex resume`, `cross provider session bridge`, `codex history import`, `ssh clipboard codex`, `osc52 resume`.

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
- `bridge resume` supports optional `--copy`; `bridge resume-latest` defaults to clipboard copy and supports `--no-copy`
- `bridge copy-local` runs remote `resume-latest` over SSH and copies the result into local clipboard (useful for SSH-first workflows)
- `bridge shim apply/restore/status/run` to temporarily rewrite Codex `model_provider` metadata for cross-provider `/resume`, with backup + restore manifests
- `bridge version` prints the current CLI/package version
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
