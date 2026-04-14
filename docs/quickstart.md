# Quickstart

## 1) Install editable package

```bash
cd /home/Biglone/workspace/codex-session-bridge-plugin
python3 -m pip install -e .
```

## 2) Initialize bridge database

```bash
bridge --db-path .bridge/session-bridge.sqlite init
```

## 3) Import real Codex sessions from local history

```bash
bridge --db-path .bridge/session-bridge.sqlite import-codex \
  --sessions-root ~/.codex/sessions \
  --provider-label codex-openai-a \
  --project-root . \
  --limit 200
```

If you use another Codex account/provider profile, import it into a separate namespace:

```bash
bridge --db-path .bridge/session-bridge.sqlite import-codex \
  --sessions-root ~/another-profile/.codex/sessions \
  --provider-label codex-openai-b \
  --project-root . \
  --limit 200
```

## 4) (Optional) Add a demo session

```bash
bridge --db-path .bridge/session-bridge.sqlite sync-demo \
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
bridge --db-path .bridge/session-bridge.sqlite list --project-root . --limit 10
```

## 6) Build resume context

```bash
bridge --db-path .bridge/session-bridge.sqlite resume <bridge-session-id> --max-turns 20
```

## Notes

- `import-codex` parses local rollout logs and imports user/assistant turns.
- `sync-demo` remains available for synthetic testing.
