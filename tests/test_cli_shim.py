import argparse
import json
import sqlite3
import subprocess
from types import SimpleNamespace
from pathlib import Path

import pytest

from codex_session_bridge import cli
from codex_session_bridge.cli import (
    build_parser,
    cmd_shim_apply,
    cmd_shim_restore,
    cmd_shim_run,
    cmd_shim_status,
)
from codex_session_bridge.shim import apply_provider_shim, list_shim_runs, restore_provider_shim


def _write_rollout(path: Path, *, thread_id: str, cwd: str, provider: str, extra: dict[str, object]) -> None:
    payload = {
        "id": thread_id,
        "timestamp": "2026-04-14T08:00:00.000Z",
        "cwd": cwd,
        "model_provider": provider,
    }
    payload.update(extra)
    events = [
        {"type": "session_meta", "timestamp": "2026-04-14T08:00:00.000Z", "payload": payload},
        {
            "type": "event_msg",
            "timestamp": "2026-04-14T08:00:01.000Z",
            "payload": {"type": "user_message", "message": "hello"},
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def _read_meta_payload(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            event = json.loads(line)
            if event.get("type") == "session_meta":
                return dict(event.get("payload", {}))
    raise AssertionError(f"session_meta missing in {path}")


def _query_thread_provider(state_db: Path, thread_id: str) -> str:
    with sqlite3.connect(state_db) as con:
        cur = con.execute("SELECT model_provider FROM threads WHERE id = ?", (thread_id,))
        row = cur.fetchone()
    if row is None:
        raise AssertionError(f"thread missing: {thread_id}")
    return str(row[0])


def _query_thread_align_fields(state_db: Path, thread_id: str) -> tuple[str, str, str]:
    with sqlite3.connect(state_db) as con:
        cur = con.execute(
            "SELECT source, model, reasoning_effort FROM threads WHERE id = ?",
            (thread_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError(f"thread missing: {thread_id}")
    return str(row[0]), str(row[1]), str(row[2])


def _setup_codex_fixture(tmp_path: Path) -> dict[str, object]:
    project_root = (tmp_path / "repo").resolve()
    project_root.mkdir(parents=True, exist_ok=True)

    codex_home = (tmp_path / "codex-home").resolve()
    codex_home.mkdir(parents=True, exist_ok=True)
    state_db = codex_home / "state_5.sqlite"

    target_rollout_rel = Path("sessions/2026/04/14/rollout-target.jsonl")
    other_rollout_rel = Path("sessions/2026/04/14/rollout-other.jsonl")
    target_rollout_abs = codex_home / target_rollout_rel
    other_rollout_abs = codex_home / other_rollout_rel

    _write_rollout(
        target_rollout_abs,
        thread_id="thread-target",
        cwd=str(project_root),
        provider="provider-target",
        extra={"model": "gpt-target", "reasoning_effort": "high", "source": "target-source"},
    )
    _write_rollout(
        other_rollout_abs,
        thread_id="thread-other",
        cwd=str(project_root),
        provider="provider-other",
        extra={"model": "gpt-other", "reasoning_effort": "low", "source": "other-source"},
    )

    with sqlite3.connect(state_db) as con:
        con.execute(
            """
            CREATE TABLE threads (
              id TEXT PRIMARY KEY,
              cwd TEXT NOT NULL,
              model_provider TEXT NOT NULL,
              rollout_path TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              source TEXT,
              cli_version TEXT,
              model TEXT,
              reasoning_effort TEXT,
              agent_path TEXT,
              memory_mode TEXT,
              sandbox_policy TEXT,
              approval_mode TEXT
            )
            """
        )
        con.execute(
            """
            INSERT INTO threads (
              id, cwd, model_provider, rollout_path, updated_at,
              source, cli_version, model, reasoning_effort,
              agent_path, memory_mode, sandbox_policy, approval_mode
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "thread-target",
                str(project_root),
                "provider-target",
                str(target_rollout_rel),
                "2026-04-14T08:00:02.000Z",
                "target-source",
                "1.0",
                "gpt-target",
                "high",
                "agent-a",
                "memory-a",
                "sandbox-a",
                "approval-a",
            ),
        )
        con.execute(
            """
            INSERT INTO threads (
              id, cwd, model_provider, rollout_path, updated_at,
              source, cli_version, model, reasoning_effort,
              agent_path, memory_mode, sandbox_policy, approval_mode
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "thread-other",
                str(project_root),
                "provider-other",
                str(other_rollout_rel),
                "2026-04-14T08:00:01.000Z",
                "other-source",
                "0.9",
                "gpt-other",
                "low",
                "agent-b",
                "memory-b",
                "sandbox-b",
                "approval-b",
            ),
        )
        con.commit()

    return {
        "project_root": project_root,
        "codex_home": codex_home,
        "state_db": state_db,
        "target_rollout": target_rollout_abs,
        "other_rollout": other_rollout_abs,
    }


def test_apply_and_restore_provider_shim(tmp_path: Path) -> None:
    fx = _setup_codex_fixture(tmp_path)
    project_root = fx["project_root"]
    codex_home = fx["codex_home"]
    state_db = fx["state_db"]
    other_rollout = fx["other_rollout"]

    applied = apply_provider_shim(
        cwd=project_root,
        target_provider="provider-target",
        codex_home=codex_home,
    )
    assert applied.candidate_threads == 1
    assert applied.changed_files == 1
    assert applied.changed_rows == 1

    meta_after_apply = _read_meta_payload(other_rollout)
    assert meta_after_apply["model_provider"] == "provider-target"
    assert _query_thread_provider(state_db, "thread-other") == "provider-target"

    restored = restore_provider_shim(cwd=project_root, run_id=applied.run_id)
    assert restored.restored_files == 1
    assert restored.restored_rows == 1

    meta_after_restore = _read_meta_payload(other_rollout)
    assert meta_after_restore["model_provider"] == "provider-other"
    assert _query_thread_provider(state_db, "thread-other") == "provider-other"

    runs = list_shim_runs(project_root)
    assert runs
    assert runs[0]["run_id"] == applied.run_id
    assert runs[0]["status"] == "restored"


def test_apply_with_template_align_updates_payload_and_sqlite(tmp_path: Path) -> None:
    fx = _setup_codex_fixture(tmp_path)
    project_root = fx["project_root"]
    codex_home = fx["codex_home"]
    state_db = fx["state_db"]
    other_rollout = fx["other_rollout"]

    applied = apply_provider_shim(
        cwd=project_root,
        target_provider="provider-target",
        codex_home=codex_home,
        template_align=True,
    )
    assert applied.changed_files == 1
    assert applied.changed_rows == 1

    payload = _read_meta_payload(other_rollout)
    assert payload["model_provider"] == "provider-target"
    assert payload["model"] == "gpt-target"
    assert payload["reasoning_effort"] == "high"
    assert payload["source"] == "target-source"

    sql_source, sql_model, sql_reasoning = _query_thread_align_fields(state_db, "thread-other")
    assert sql_source == "target-source"
    assert sql_model == "gpt-target"
    assert sql_reasoning == "high"

    restore_provider_shim(cwd=project_root, run_id=applied.run_id)
    payload_restored = _read_meta_payload(other_rollout)
    assert payload_restored["model_provider"] == "provider-other"
    assert payload_restored["model"] == "gpt-other"

    sql_source_restored, sql_model_restored, sql_reasoning_restored = _query_thread_align_fields(
        state_db,
        "thread-other",
    )
    assert sql_source_restored == "other-source"
    assert sql_model_restored == "gpt-other"
    assert sql_reasoning_restored == "low"


def test_cmd_shim_run_applies_then_restores(tmp_path: Path, monkeypatch, capsys) -> None:
    fx = _setup_codex_fixture(tmp_path)
    project_root = fx["project_root"]
    codex_home = fx["codex_home"]
    state_db = fx["state_db"]
    other_rollout = fx["other_rollout"]

    captured: dict[str, object] = {}

    def fake_run(cmd, cwd=None):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    args = argparse.Namespace(
        cwd=str(project_root),
        target_provider="provider-target",
        codex_home=str(codex_home),
        run_id="",
        template_align=False,
        force_restore=False,
        command=["--", "echo", "ok"],
    )

    code = cmd_shim_run(args)
    out = capsys.readouterr().out

    assert code == 0
    assert captured["cmd"] == ["echo", "ok"]
    assert captured["cwd"] == str(project_root)
    assert "Shim apply finished" in out
    assert "Shim restore finished" in out

    payload = _read_meta_payload(other_rollout)
    assert payload["model_provider"] == "provider-other"
    assert _query_thread_provider(state_db, "thread-other") == "provider-other"


def test_cmd_shim_apply_uses_config_provider_when_flag_missing(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir(parents=True, exist_ok=True)
    (codex_home / "config.toml").write_text('model_provider = "detected-provider"\n', encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_apply_provider_shim(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return SimpleNamespace(
            run_id="shim-run-1",
            manifest_path=tmp_path / "manifest.json",
            changed_files=0,
            changed_rows=0,
            candidate_threads=0,
            template_thread_id="",
            template_align=False,
            dry_run=True,
        )

    monkeypatch.setattr(cli, "apply_provider_shim", fake_apply_provider_shim)

    args = argparse.Namespace(
        cwd=str(tmp_path),
        target_provider="",
        codex_home=str(codex_home),
        run_id="",
        template_align=False,
        dry_run=True,
    )
    code = cmd_shim_apply(args)
    out = capsys.readouterr().out

    assert code == 0
    assert captured["target_provider"] == "detected-provider"
    assert "run_id=shim-run-1" in out


def test_cmd_shim_apply_prefers_explicit_provider_over_config(tmp_path: Path, monkeypatch) -> None:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir(parents=True, exist_ok=True)
    (codex_home / "config.toml").write_text('model_provider = "detected-provider"\n', encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_apply_provider_shim(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return SimpleNamespace(
            run_id="shim-run-2",
            manifest_path=tmp_path / "manifest.json",
            changed_files=0,
            changed_rows=0,
            candidate_threads=0,
            template_thread_id="",
            template_align=False,
            dry_run=True,
        )

    monkeypatch.setattr(cli, "apply_provider_shim", fake_apply_provider_shim)

    args = argparse.Namespace(
        cwd=str(tmp_path),
        target_provider="manual-provider",
        codex_home=str(codex_home),
        run_id="",
        template_align=False,
        dry_run=True,
    )
    code = cmd_shim_apply(args)

    assert code == 0
    assert captured["target_provider"] == "manual-provider"


def test_cmd_shim_apply_missing_provider_raises(tmp_path: Path) -> None:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir(parents=True, exist_ok=True)
    args = argparse.Namespace(
        cwd=str(tmp_path),
        target_provider="",
        codex_home=str(codex_home),
        run_id="",
        template_align=False,
        dry_run=True,
    )

    with pytest.raises(SystemExit, match="Unable to determine target provider"):
        cmd_shim_apply(args)


def test_shim_cli_subcommands_wired(tmp_path: Path) -> None:
    parser = build_parser()

    apply_args = parser.parse_args(["shim", "apply", "--cwd", str(tmp_path)])
    assert apply_args.func == cmd_shim_apply

    restore_args = parser.parse_args(["shim", "restore"])
    assert restore_args.func == cmd_shim_restore

    status_args = parser.parse_args(["shim", "status"])
    assert status_args.func == cmd_shim_status

    run_args = parser.parse_args(["shim", "run"])
    assert run_args.func == cmd_shim_run


def test_cmd_shim_run_handles_restore_keyboard_interrupt(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "apply_provider_shim",
        lambda **_: SimpleNamespace(run_id="shim-run-x", candidate_threads=1, changed_files=1, changed_rows=1),
    )
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(["codex"], 130),
    )

    def _raise_interrupt(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise KeyboardInterrupt()

    monkeypatch.setattr(cli, "_restore_with_signal_guard", _raise_interrupt)

    args = argparse.Namespace(
        cwd=str(tmp_path),
        target_provider="provider-target",
        codex_home=str(tmp_path / "codex-home"),
        run_id="",
        template_align=False,
        force_restore=False,
        command=["--", "codex"],
    )

    code = cmd_shim_run(args)
    captured = capsys.readouterr()
    assert code == 130
    assert "Manual restore may be required" in captured.err
