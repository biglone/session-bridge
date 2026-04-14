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
```

The NPM launcher will:

1. create/update runtime venv at `~/.session-bridge/runtime`
2. install Python package into that venv
3. run the bridge CLI
