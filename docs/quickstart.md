# Quickstart

## 1) Install editable package

```bash
cd /home/Biglone/workspace/session-bridge
python3 -m pip install -e .
```

Alternative (NPM package):

```bash
npx @biglone/session-bridge --help
```

If your system blocks global pip install (PEP 668), use local venv setup:

```bash
cd /home/Biglone/workspace/session-bridge
./scripts/setup_venv.sh
```

Then run via local launcher (works with or without editable install):

```bash
./bin/bridge --help
```

## 1.5) Register plugin into Codex local marketplace (one-time)

```bash
./bin/bridge install-plugin --plugin-source /home/Biglone/workspace/session-bridge
```

This creates:

- plugin symlink: `~/plugins/session-bridge`
- marketplace entry: `~/.agents/plugins/marketplace.json`

## 2) Initialize bridge database

```bash
./bin/bridge --db-path .bridge/session-bridge.sqlite init
```

## 3) Import real Codex sessions from local history

```bash
./bin/bridge --db-path .bridge/session-bridge.sqlite import-codex \
  --sessions-root ~/.codex/sessions \
  --provider-label codex-openai-a \
  --project-root . \
  --limit 200
```

If you use another Codex account/provider profile, import it into a separate namespace:

```bash
./bin/bridge --db-path .bridge/session-bridge.sqlite import-codex \
  --sessions-root ~/another-profile/.codex/sessions \
  --provider-label codex-openai-b \
  --project-root . \
  --limit 200
```

Import Claude Code project logs as another provider namespace:

```bash
./bin/bridge --db-path .bridge/session-bridge.sqlite import-claude \
  --projects-root ~/.claude/projects \
  --provider-label claude-main \
  --project-root . \
  --limit 200
```

Or run one command for both sources:

```bash
./bin/bridge --db-path .bridge/session-bridge.sqlite import-all \
  --project-root . \
  --codex-provider-label codex-openai-a \
  --claude-provider-label claude-main \
  --codex-limit 200 \
  --claude-limit 200
```

## 4) (Optional) Add a demo session

```bash
./bin/bridge --db-path .bridge/session-bridge.sqlite sync-demo \
  --provider vendor-a \
  --provider-session-id sess-001 \
  --project-root . \
  --title "Refactor auth flow" \
  --summary "Migrated token parser and fixed tests" \
  --git-branch main \
  --git-commit abcdef123456 \
  --turn user:"continue from latest auth fix" \
  --turn assistant:"loaded context and resuming work"
```

## 5) List recent sessions

```bash
./bin/bridge --db-path .bridge/session-bridge.sqlite list --project-root . --limit 10
```

Filter by provider keyword (case-insensitive):

```bash
./bin/bridge --db-path .bridge/session-bridge.sqlite list --project-root . --provider claude
```

## 6) Build resume context

```bash
./bin/bridge --db-path .bridge/session-bridge.sqlite resume <bridge-session-id> --max-turns 20
```

Resume the latest session directly (no manual session id):

```bash
./bin/bridge --db-path .bridge/session-bridge.sqlite resume-latest \
  --project-root . \
  --provider claude \
  --max-turns 20
```

Skip repo consistency check section if needed:

```bash
./bin/bridge --db-path .bridge/session-bridge.sqlite resume <bridge-session-id> --no-consistency-check
```

## Notes

- `import-codex` parses local rollout logs and imports user/assistant turns.
- `import-claude` parses local Claude project logs and imports user/assistant turns.
- `import-all` runs both import pipelines in one command.
- `sync-demo` remains available for synthetic testing.
- imports sanitize common secret patterns (`api_key`, `access_token`, bearer headers, `sk-...`) before writing to SQLite.
