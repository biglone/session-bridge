import argparse
import subprocess

from codex_session_bridge import cli
from codex_session_bridge.cli import build_parser, cmd_copy_local


def _base_args() -> argparse.Namespace:
    return argparse.Namespace(
        host="jetson",
        remote_project_root="~/workspace/video-automation",
        provider="",
        max_turns=100,
        no_consistency_check=False,
        no_scan_project_codex=False,
        no_scan_home_codex=False,
        remote_db_path="",
        remote_bin="session-bridge",
        ssh_bin="ssh",
    )


def test_copy_local_success_copies_remote_output(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_run(cmd, capture_output, text):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="# Session Resume Context\n...", stderr="")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(cli, "_copy_to_clipboard", lambda _: (True, "pbcopy"))

    code = cmd_copy_local(_base_args())
    out = capsys.readouterr().out

    assert code == 0
    assert "copied to local clipboard via 'pbcopy'" in out
    assert isinstance(captured.get("cmd"), list)
    cmd = captured["cmd"]
    assert cmd[0] == "ssh"
    assert cmd[1] == "-T"
    assert cmd[2] == "jetson"
    assert "resume-latest" in cmd[3]
    assert "--no-copy" in cmd[3]


def test_copy_local_remote_failure_returns_nonzero(monkeypatch, capsys) -> None:
    def fake_run(cmd, capture_output, text):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(cmd, 23, stdout="", stderr="ssh failed")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    code = cmd_copy_local(_base_args())
    err = capsys.readouterr().err

    assert code == 23
    assert "Remote command failed via SSH" in err
    assert "ssh failed" in err


def test_copy_local_copy_failure_falls_back_to_print(monkeypatch, capsys) -> None:
    def fake_run(cmd, capture_output, text):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(cmd, 0, stdout="remote-context", stderr="")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(cli, "_copy_to_clipboard", lambda _: (False, ""))

    code = cmd_copy_local(_base_args())
    captured = capsys.readouterr()

    assert code == 0
    assert "Local clipboard copy failed" in captured.err
    assert "remote-context" in captured.out


def test_copy_local_subcommand_wired() -> None:
    parser = build_parser()
    args = parser.parse_args(["copy-local", "--host", "jetson"])
    assert args.func == cmd_copy_local
