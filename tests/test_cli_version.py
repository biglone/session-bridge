import argparse

from codex_session_bridge import cli
from codex_session_bridge.cli import build_parser, cmd_version


def test_cmd_version_prints_resolved_version(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "_resolve_cli_version", lambda: "9.9.9")
    code = cmd_version(argparse.Namespace())
    out = capsys.readouterr().out.strip()

    assert code == 0
    assert out == "9.9.9"


def test_version_subcommand_wired() -> None:
    parser = build_parser()
    args = parser.parse_args(["version"])
    assert args.func == cmd_version
