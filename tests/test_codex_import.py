import json
from pathlib import Path

from codex_session_bridge.adapters.codex_rollout import import_codex_rollouts, parse_rollout_file
from codex_session_bridge.storage import BridgeStore


def _write_rollout(path: Path, cwd: str, sid: str, prompt: str, answer: str) -> None:
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
            "timestamp": "2026-04-14T08:00:01.000Z",
            "type": "event_msg",
            "payload": {
                "type": "user_message",
                "message": "<environment_context>ignore me</environment_context>",
            },
        },
        {
            "timestamp": "2026-04-14T08:00:02.000Z",
            "type": "event_msg",
            "payload": {
                "type": "user_message",
                "message": prompt,
            },
        },
        {
            "timestamp": "2026-04-14T08:00:03.000Z",
            "type": "event_msg",
            "payload": {
                "type": "agent_message",
                "message": answer,
            },
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def test_parse_rollout_file_extracts_summary_and_turns(tmp_path: Path) -> None:
    project_root = str((tmp_path / "repo").resolve())
    rollout_path = tmp_path / "sessions" / "2026" / "04" / "14" / "rollout-1.jsonl"
    _write_rollout(
        rollout_path,
        cwd=project_root,
        sid="sess-123",
        prompt="please continue auth refactor",
        answer="I updated parser and tests are green.",
    )

    parsed = parse_rollout_file(rollout_path)
    assert parsed is not None
    assert parsed.provider_session_id == "sess-123"
    assert parsed.project_root == project_root
    assert parsed.title == "please continue auth refactor"
    assert "tests are green" in parsed.summary
    assert len(parsed.turns) == 2


def test_import_codex_rollouts_respects_project_filter(tmp_path: Path) -> None:
    db = tmp_path / "bridge.sqlite"
    store = BridgeStore(db)
    repo_a = str((tmp_path / "repo-a").resolve())
    repo_b = str((tmp_path / "repo-b").resolve())
    root = tmp_path / "sessions"

    _write_rollout(
        root / "2026/04/14/rollout-a.jsonl",
        cwd=repo_a,
        sid="sess-a",
        prompt="task A",
        answer="done A",
    )
    _write_rollout(
        root / "2026/04/14/rollout-b.jsonl",
        cwd=repo_b,
        sid="sess-b",
        prompt="task B",
        answer="done B",
    )

    stats = import_codex_rollouts(
        store=store,
        sessions_root=root,
        provider_label="codex-main",
        project_root_filter=repo_a,
        limit=20,
    )
    assert stats.imported == 1
    assert stats.skipped_project == 1

    sessions = store.list_sessions(project_root=repo_a, limit=10)
    assert len(sessions) == 1
    assert sessions[0].provider == "codex-main:openai"
    turns = store.list_turns(sessions[0].id, limit=10)
    assert [t.role for t in turns] == ["user", "assistant"]
