# NPM Publish Guide

## Prerequisites

- Node.js 18+
- npm account with publish permission
- Python 3 available on end-user machines (runtime bootstrap depends on it)

## Local validation

```bash
cd /path/to/session-bridge
npm run release:check
```

## Package metadata checklist (recommended before publish)

Ensure `package.json` aligns with current features:

- `description`: mention core value in one sentence (cross-provider resume continuity)
- `keywords`: include real discoverability terms, for example:
  - `codex`, `codex-cli`, `session-resume`, `cross-provider`, `context-recovery`
  - `ssh`, `clipboard`, `osc52` (if supported)
  - `claude-code` (if import integration exists)
- `homepage`, `repository`, `bugs`: valid GitHub links
- `files`: only ship runtime-relevant files

Preview NPM listing payload:

```bash
npm pack --dry-run
```

## Login and publish

```bash
npm login
npm publish --access public
```

If package name already exists, change `name` in `package.json` first (recommended scoped package).

## User install / run

```bash
npx @biglone/session-bridge --help
npx @biglone/session-bridge install-plugin
npm install -g @biglone/session-bridge
```

The NPM launcher will:

1. create/update runtime venv at `~/.session-bridge/runtime`
2. install Python package into that venv
3. run the bridge CLI

On global install, package `postinstall` now triggers `install-plugin` automatically.
