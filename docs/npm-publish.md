# NPM Publish Guide

## Prerequisites

- Node.js 18+
- npm account with publish permission
- Python 3 available on end-user machines (runtime bootstrap depends on it)

## Local validation

```bash
cd /home/Biglone/workspace/session-bridge-plugin
npm run test:python
npm run pack:check
```

## Login and publish

```bash
npm login
npm publish --access public
```

If package name already exists, change `name` in `package.json` first (recommended scoped package).

## User install / run

```bash
npx @biglone/session-bridge-plugin --help
npx @biglone/session-bridge-plugin install-plugin
```

The NPM launcher will:

1. create/update runtime venv at `~/.session-bridge-plugin/runtime`
2. install Python package into that venv
3. run the bridge CLI
