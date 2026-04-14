import argparse
import json
from pathlib import Path

from codex_session_bridge.cli import cmd_list, cmd_resume_latest


def _write_rollout(path: Path, cwd: str, sid: str, user_message: str, assistant_message: str) -> None:
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
            "payload": {"type": "user_message", "message": user_message},
        },
        {
            "timestamp": "2026-04-14T08:00:03.000Z",
            "type": "event_msg",
            "payload": {"type": "agent_message", "message": assistant_message},
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def test_list_auto_scans_project_codex_directory(tmp_path: Path, capsys) -> None:
    project_root = tmp_path / "repo"
    project_root.mkdir(parents=True, exist_ok=True)
    rollout = project_root / ".codex" / "sessions" / "2026" / "04" / "14" / "rollout-1.jsonl"
    _write_rollout(
        rollout,
        cwd=str(project_root.resolve()),
        sid="sid-project-1",
        user_message="continue auth refactor",
        assistant_message="done",
    )

    args = argparse.Namespace(
        db_path=str(tmp_path / "bridge.sqlite"),
        project_root=str(project_root),
        limit=10,
        provider="",
        project_codex_dir=".codex",
        project_codex_limit=50,
        no_scan_project_codex=False,
        home_codex_dir=str(tmp_path / "home-codex"),
        home_codex_limit=50,
        no_scan_home_codex=True,
    )
    code = cmd_list(args)
    out = capsys.readouterr().out

    assert code == 0
    assert "codex-project:openai" in out
    assert "continue auth refactor" in out


def test_list_no_scan_project_codex_keeps_previous_behavior(tmp_path: Path, capsys) -> None:
    project_root = tmp_path / "repo"
    project_root.mkdir(parents=True, exist_ok=True)
    rollout = project_root / ".codex" / "sessions" / "2026" / "04" / "14" / "rollout-1.jsonl"
    _write_rollout(
        rollout,
        cwd=str(project_root.resolve()),
        sid="sid-project-2",
        user_message="continue",
        assistant_message="done",
    )

    args = argparse.Namespace(
        db_path=str(tmp_path / "bridge.sqlite"),
        project_root=str(project_root),
        limit=10,
        provider="",
        project_codex_dir=".codex",
        project_codex_limit=50,
        no_scan_project_codex=True,
        home_codex_dir=str(tmp_path / "home-codex"),
        home_codex_limit=50,
        no_scan_home_codex=True,
    )
    code = cmd_list(args)
    out = capsys.readouterr().out

    assert code == 0
    assert "No bridge sessions for" in out


def test_list_merges_multiple_project_codex_accounts(tmp_path: Path, capsys) -> None:
    project_root = tmp_path / "repo"
    project_root.mkdir(parents=True, exist_ok=True)

    _write_rollout(
        project_root / ".codex" / "account-a" / "sessions" / "2026" / "04" / "14" / "rollout-a.jsonl",
        cwd=str(project_root.resolve()),
        sid="sid-account-a",
        user_message="task a",
        assistant_message="done a",
    )
    _write_rollout(
        project_root / ".codex" / "account-b" / "sessions" / "2026" / "04" / "14" / "rollout-b.jsonl",
        cwd=str(project_root.resolve()),
        sid="sid-account-b",
        user_message="task b",
        assistant_message="done b",
    )

    args = argparse.Namespace(
        db_path=str(tmp_path / "bridge.sqlite"),
        project_root=str(project_root),
        limit=20,
        provider="",
        project_codex_dir=".codex",
        project_codex_limit=50,
        no_scan_project_codex=False,
        home_codex_dir=str(tmp_path / "home-codex"),
        home_codex_limit=50,
        no_scan_home_codex=True,
    )
    code = cmd_list(args)
    out = capsys.readouterr().out

    assert code == 0
    assert "codex-project-account-a:openai" in out
    assert "codex-project-account-b:openai" in out


def test_resume_latest_auto_scans_project_codex_directory(tmp_path: Path, capsys) -> None:
    project_root = tmp_path / "repo"
    project_root.mkdir(parents=True, exist_ok=True)
    rollout = project_root / ".codex" / "sessions" / "2026" / "04" / "14" / "rollout-1.jsonl"
    _write_rollout(
        rollout,
        cwd=str(project_root.resolve()),
        sid="sid-project-3",
        user_message="resume this work",
        assistant_message="continuing",
    )

    args = argparse.Namespace(
        db_path=str(tmp_path / "bridge.sqlite"),
        project_root=str(project_root),
        provider="",
        project_codex_dir=".codex",
        project_codex_limit=50,
        no_scan_project_codex=False,
        home_codex_dir=str(tmp_path / "home-codex"),
        home_codex_limit=50,
        no_scan_home_codex=True,
        max_turns=10,
        no_consistency_check=True,
    )
    code = cmd_resume_latest(args)
    out = capsys.readouterr().out

    assert code == 0
    assert "provider: codex-project:openai" in out
    assert "resume this work" in out


def test_list_auto_scans_home_codex_directory_when_project_codex_missing(tmp_path: Path, capsys) -> None:
    project_root = tmp_path / "repo"
    project_root.mkdir(parents=True, exist_ok=True)
    home_codex_root = tmp_path / "home-codex"
    rollout = home_codex_root / "sessions" / "2026" / "04" / "14" / "rollout-1.jsonl"
    _write_rollout(
        rollout,
        cwd=str(project_root.resolve()),
        sid="sid-home-1",
        user_message="continue from home codex",
        assistant_message="done",
    )

    args = argparse.Namespace(
        db_path=str(tmp_path / "bridge.sqlite"),
        project_root=str(project_root),
        limit=10,
        provider="",
        project_codex_dir=".codex",
        project_codex_limit=50,
        no_scan_project_codex=False,
        home_codex_dir=str(home_codex_root),
        home_codex_limit=50,
        no_scan_home_codex=False,
    )
    code = cmd_list(args)
    out = capsys.readouterr().out

    assert code == 0
    assert "codex-home:openai" in out
    assert "continue from home codex" in out


def test_list_can_disable_home_codex_scan(tmp_path: Path, capsys) -> None:
    project_root = tmp_path / "repo"
    project_root.mkdir(parents=True, exist_ok=True)
    home_codex_root = tmp_path / "home-codex"
    rollout = home_codex_root / "sessions" / "2026" / "04" / "14" / "rollout-1.jsonl"
    _write_rollout(
        rollout,
        cwd=str(project_root.resolve()),
        sid="sid-home-2",
        user_message="home session only",
        assistant_message="done",
    )

    args = argparse.Namespace(
        db_path=str(tmp_path / "bridge.sqlite"),
        project_root=str(project_root),
        limit=10,
        provider="",
        project_codex_dir=".codex",
        project_codex_limit=50,
        no_scan_project_codex=False,
        home_codex_dir=str(home_codex_root),
        home_codex_limit=50,
        no_scan_home_codex=True,
    )
    code = cmd_list(args)
    out = capsys.readouterr().out

    assert code == 0
    assert "No bridge sessions for" in out
