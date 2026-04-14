import argparse
from pathlib import Path

from codex_session_bridge import cli
from codex_session_bridge.cli import build_parser, cmd_resume_latest
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
        copy=False,
        no_consistency_check=True,
    )
    code = cmd_resume_latest(args)
    out = capsys.readouterr().out
    assert code == 0
    assert "provider: claude-main" in out
    assert "claude user" in out


def test_cmd_resume_latest_copy_mode_prints_hint_only(tmp_path: Path, capsys, monkeypatch) -> None:
    db_path = tmp_path / "bridge.sqlite"
    project_root = str((tmp_path / "repo").resolve())
    store = BridgeStore(db_path)

    session = BridgeSession.new(
        provider="codex-openai-a",
        provider_session_id="sid-codex",
        project_root=project_root,
        title="codex task",
        summary="codex summary",
    )
    store.upsert_session(session)
    store.add_turn(BridgeTurn.new(session.id, "user", "very long payload"))

    monkeypatch.setattr(cli, "_copy_to_clipboard", lambda _: (True, "pbcopy"))

    args = argparse.Namespace(
        db_path=str(db_path),
        project_root=project_root,
        provider="codex",
        max_turns=5,
        copy=True,
        no_consistency_check=True,
    )
    code = cmd_resume_latest(args)
    out = capsys.readouterr().out

    assert code == 0
    assert "copied to clipboard" in out
    assert "Open a new Codex session and paste to continue." in out
    assert "## Recent Turns" not in out
    assert "very long payload" not in out


def test_cmd_resume_latest_copy_mode_fallback_prints_context(tmp_path: Path, capsys, monkeypatch) -> None:
    db_path = tmp_path / "bridge.sqlite"
    project_root = str((tmp_path / "repo").resolve())
    store = BridgeStore(db_path)

    session = BridgeSession.new(
        provider="codex-openai-a",
        provider_session_id="sid-codex",
        project_root=project_root,
        title="codex task",
        summary="codex summary",
    )
    store.upsert_session(session)
    store.add_turn(BridgeTurn.new(session.id, "user", "needs fallback"))

    monkeypatch.setattr(cli, "_copy_to_clipboard", lambda _: (False, ""))

    args = argparse.Namespace(
        db_path=str(db_path),
        project_root=project_root,
        provider="codex",
        max_turns=5,
        copy=True,
        no_consistency_check=True,
    )
    code = cmd_resume_latest(args)
    captured = capsys.readouterr()

    assert code == 0
    assert "Clipboard copy failed" in captured.err
    assert "## Recent Turns" in captured.out
    assert "needs fallback" in captured.out


def test_resume_latest_default_max_turns_is_20() -> None:
    parser = build_parser()
    args = parser.parse_args(["resume-latest"])
    assert args.max_turns == 20
    assert args.copy is True


def test_resume_latest_no_copy_flag_disables_clipboard_mode() -> None:
    parser = build_parser()
    args = parser.parse_args(["resume-latest", "--no-copy"])
    assert args.copy is False
