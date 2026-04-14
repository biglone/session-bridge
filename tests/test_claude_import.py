import json
from pathlib import Path

from codex_session_bridge.adapters.claude_projects import import_claude_projects, parse_claude_project_file
from codex_session_bridge.storage import BridgeStore


def _write_claude_project(path: Path, cwd: str, sid: str, prompt: str, answer: str) -> None:
    rows = [
        {
            "type": "user",
            "timestamp": "2026-04-14T08:00:00.000Z",
            "sessionId": sid,
            "cwd": cwd,
            "gitBranch": "main",
            "message": {"role": "user", "content": "<environment_context>ignore</environment_context>"},
        },
        {
            "type": "user",
            "timestamp": "2026-04-14T08:00:01.000Z",
            "sessionId": sid,
            "cwd": cwd,
            "gitBranch": "main",
            "message": {"role": "user", "content": prompt},
        },
        {
            "type": "assistant",
            "timestamp": "2026-04-14T08:00:02.000Z",
            "sessionId": sid,
            "cwd": cwd,
            "gitBranch": "main",
            "message": {
                "role": "assistant",
                "model": "claude-3-7-sonnet",
                "content": [
                    {"type": "thinking", "thinking": "hidden"},
                    {"type": "text", "text": answer},
                ],
            },
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_parse_claude_project_file_extracts_turns(tmp_path: Path) -> None:
    root = str((tmp_path / "repo").resolve())
    fp = tmp_path / "projects" / "session-1.jsonl"
    _write_claude_project(fp, cwd=root, sid="sid-1", prompt="continue the refactor", answer="done")

    parsed = parse_claude_project_file(fp)
    assert parsed is not None
    assert parsed.provider_session_id == "sid-1"
    assert parsed.project_root == root
    assert parsed.model == "claude-3-7-sonnet"
    assert parsed.title == "continue the refactor"
    assert len(parsed.turns) == 2
    assert [t.role for t in parsed.turns] == ["user", "assistant"]


def test_import_claude_projects_filters_by_project(tmp_path: Path) -> None:
    store = BridgeStore(tmp_path / "bridge.sqlite")
    root = tmp_path / "projects"
    repo_a = str((tmp_path / "repo-a").resolve())
    repo_b = str((tmp_path / "repo-b").resolve())

    _write_claude_project(root / "a.jsonl", cwd=repo_a, sid="sid-a", prompt="task a", answer="done a")
    _write_claude_project(root / "b.jsonl", cwd=repo_b, sid="sid-b", prompt="task b", answer="done b")

    stats = import_claude_projects(
        store=store,
        projects_root=root,
        provider_label="claude-alt",
        project_root_filter=repo_b,
        limit=10,
    )
    assert stats.imported == 1
    assert stats.skipped_project == 1

    sessions = store.list_sessions(project_root=repo_b, limit=10)
    assert len(sessions) == 1
    assert sessions[0].provider == "claude-alt:claude-3-7-sonnet"
