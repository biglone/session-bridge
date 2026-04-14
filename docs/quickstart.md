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

## 3) Add a demo session

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

## 4) List recent sessions

```bash
bridge --db-path .bridge/session-bridge.sqlite list --project-root . --limit 10
```

## 5) Build resume context

```bash
bridge --db-path .bridge/session-bridge.sqlite resume <bridge-session-id> --max-turns 20
```

## Notes

- This MVP currently ships `sync-demo` for manual ingestion.
- Provider-specific adapters should be added in future commits.
