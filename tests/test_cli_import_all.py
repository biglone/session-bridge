import argparse
import json
from pathlib import Path

from codex_session_bridge.cli import cmd_import_all
from codex_session_bridge.storage import BridgeStore


def _write_rollout(path: Path, cwd: str, sid: str) -> None:
    events = [
        {
            "timestamp": "2026-04-14T08:00:00.000Z",
            "type": "session_meta",
            "payload": {
                "id": sid,
                "timestamp": "2026-04-14T08:00:00.000Z",
                "cwd": cwd,
                "model_provider": "openai",
                "git": {"branch": "main", "commit_hash": "abc123"},
            },
        },
        {
            "timestamp": "2026-04-14T08:00:02.000Z",
            "type": "event_msg",
            "payload": {"type": "user_message", "message": "task from codex"},
        },
        {
            "timestamp": "2026-04-14T08:00:03.000Z",
            "type": "event_msg",
            "payload": {"type": "agent_message", "message": "done from codex"},
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def _write_claude(path: Path, cwd: str, sid: str) -> None:
    rows = [
        {
            "type": "user",
            "timestamp": "2026-04-14T08:01:00.000Z",
            "sessionId": sid,
            "cwd": cwd,
            "gitBranch": "main",
            "message": {"role": "user", "content": "task from claude"},
        },
        {
            "type": "assistant",
            "timestamp": "2026-04-14T08:01:02.000Z",
            "sessionId": sid,
            "cwd": cwd,
            "gitBranch": "main",
            "message": {
                "role": "assistant",
                "model": "claude-3-7-sonnet",
                "content": [{"type": "text", "text": "done from claude"}],
            },
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_cmd_import_all_ingests_both_sources(tmp_path: Path, capsys) -> None:
    project_root = str((tmp_path / "repo").resolve())
    codex_root = tmp_path / "codex-sessions"
    claude_root = tmp_path / "claude-projects"
    db_path = tmp_path / "bridge.sqlite"

    _write_rollout(codex_root / "2026/04/14/rollout-1.jsonl", cwd=project_root, sid="codex-sid")
    _write_claude(claude_root / "one.jsonl", cwd=project_root, sid="claude-sid")

    args = argparse.Namespace(
        db_path=str(db_path),
        all_projects=False,
        project_root=project_root,
        codex_sessions_root=str(codex_root),
        claude_projects_root=str(claude_root),
        codex_provider_label="codex-x",
        claude_provider_label="claude-x",
        codex_limit=20,
        claude_limit=20,
    )

    code = cmd_import_all(args)
    captured = capsys.readouterr().out
    assert code == 0
    assert "Total imported sessions: 2" in captured

    store = BridgeStore(db_path)
    sessions = store.list_sessions(project_root=project_root, limit=10)
    providers = {s.provider for s in sessions}
    assert "codex-x:openai" in providers
    assert "claude-x:claude-3-7-sonnet" in providers
