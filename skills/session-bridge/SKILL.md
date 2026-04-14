---
name: session-bridge
description: Bridge coding sessions across Codex providers/accounts by syncing context into a local normalized store and rebuilding resume context.
---

# Session Bridge Skill

## Intent

Keep session continuity when switching Codex providers or accounts.

## Workflow

1. Capture current provider session metadata and conversation turns.
2. Normalize into a provider-agnostic schema.
3. Store to local bridge database indexed by repo path and timestamps.
4. Rebuild compact resume context for a fresh session.

## Commands

- `bridge sync`: ingest current provider session into local store
- `bridge list`: list latest sessions for current repository
- `bridge resume <bridge_session_id>`: generate recovery context

## Guardrails

- Never exfiltrate provider tokens, cookies, or secrets.
- Prefer local encrypted storage for sensitive conversation data.
- Resume output must include git branch and commit fingerprints when available.
