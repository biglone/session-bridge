import argparse
from pathlib import Path

from codex_session_bridge.cli import cmd_resume_latest
from codex_session_bridge.models import BridgeSession, BridgeTurn
from codex_session_bridge.storage import BridgeStore


def test_cmd_resume_latest_prints_context_for_filtered_provider(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "bridge.sqlite"
    project_root = str((tmp_path / "repo").resolve())
    store = BridgeStore(db_path)

    s1 = BridgeSession.new(
        provider="codex-openai-a",
        provider_session_id="sid-codex",
        project_root=project_root,
        title="codex task",
        summary="codex summary",
    )
    s2 = BridgeSession.new(
        provider="claude-main",
        provider_session_id="sid-claude",
        project_root=project_root,
        title="claude task",
        summary="claude summary",
    )
    store.upsert_session(s1)
    store.upsert_session(s2)
    store.add_turn(BridgeTurn.new(s1.id, "user", "codex user"))
    store.add_turn(BridgeTurn.new(s2.id, "user", "claude user"))

    args = argparse.Namespace(
        db_path=str(db_path),
        project_root=project_root,
        provider="claude",
        max_turns=5,
        no_consistency_check=True,
    )
    code = cmd_resume_latest(args)
    out = capsys.readouterr().out
    assert code == 0
    assert "provider: claude-main" in out
    assert "claude user" in out
