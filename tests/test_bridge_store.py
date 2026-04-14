from pathlib import Path

from codex_session_bridge.models import BridgeSession, BridgeTurn
from codex_session_bridge.resume import build_resume_context
from codex_session_bridge.storage import BridgeStore


def test_upsert_and_list_sessions(tmp_path: Path) -> None:
    store = BridgeStore(tmp_path / "bridge.sqlite")
    project_root = str(tmp_path.resolve())

    session = BridgeSession.new(
        provider="vendor-a",
        provider_session_id="sess-1",
        project_root=project_root,
        title="test task",
        summary="summary",
        git_branch="main",
        git_commit="abc123",
    )
    store.upsert_session(session)

    sessions = store.list_sessions(project_root=project_root, limit=5)
    assert len(sessions) == 1
    assert sessions[0].id == session.id
    assert sessions[0].provider == "vendor-a"


def test_resume_context_contains_recent_turns(tmp_path: Path) -> None:
    store = BridgeStore(tmp_path / "bridge.sqlite")
    project_root = str(tmp_path.resolve())

    session = BridgeSession.new(
        provider="vendor-b",
        provider_session_id="sess-2",
        project_root=project_root,
        title="resume me",
        summary="important context",
        git_branch="feature/bridge",
        git_commit="deadbeef",
    )
    store.upsert_session(session)
    store.add_turns(
        [
            BridgeTurn.new(session.id, "user", "please continue"),
            BridgeTurn.new(session.id, "assistant", "continuing now"),
        ]
    )

    turns = store.list_turns(session.id, limit=10)
    context = build_resume_context(session, turns)

    assert "resume me" in context
    assert "vendor-b" in context
    assert "please continue" in context
    assert "continuing now" in context


def test_list_sessions_provider_filter(tmp_path: Path) -> None:
    store = BridgeStore(tmp_path / "bridge.sqlite")
    project_root = str(tmp_path.resolve())

    s1 = BridgeSession.new(
        provider="codex-openai-a",
        provider_session_id="sess-a",
        project_root=project_root,
        title="task a",
        summary="a",
    )
    s2 = BridgeSession.new(
        provider="claude-main",
        provider_session_id="sess-b",
        project_root=project_root,
        title="task b",
        summary="b",
    )
    store.upsert_session(s1)
    store.upsert_session(s2)

    codex_sessions = store.list_sessions(project_root=project_root, provider_filter="CoDeX", limit=10)
    claude_sessions = store.list_sessions(project_root=project_root, provider_filter="claude", limit=10)

    assert len(codex_sessions) == 1
    assert codex_sessions[0].provider == "codex-openai-a"
    assert len(claude_sessions) == 1
    assert claude_sessions[0].provider == "claude-main"

    latest_any = store.get_latest_session(project_root=project_root)
    latest_claude = store.get_latest_session(project_root=project_root, provider_filter="claude")
    assert latest_any is not None
    assert latest_claude is not None
    assert latest_claude.provider == "claude-main"
