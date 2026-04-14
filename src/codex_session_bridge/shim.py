from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


IMMUTABLE_META_KEYS = {"id", "timestamp", "cwd", "model_provider"}
SQL_ALIGN_CANDIDATES = [
    "source",
    "cli_version",
    "model",
    "reasoning_effort",
    "agent_path",
    "memory_mode",
    "sandbox_policy",
    "approval_mode",
]


@dataclass
class ShimApplyResult:
    run_id: str
    manifest_path: Path
    changed_files: int
    changed_rows: int
    candidate_threads: int
    template_thread_id: str
    template_align: bool
    dry_run: bool


@dataclass
class ShimRestoreResult:
    run_id: str
    manifest_path: Path
    restored_files: int
    restored_rows: int
    skipped_file_conflicts: int
    skipped_row_conflicts: int


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{ts}-{uuid.uuid4().hex[:8]}"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _normalize_rollout_path(rollout_path: str, codex_home: Path) -> Path:
    candidate = Path(rollout_path).expanduser()
    if candidate.is_absolute():
        return candidate
    return (codex_home / candidate).resolve()


def _shim_root_for_cwd(cwd: Path) -> Path:
    return (cwd / ".bridge" / "provider-shim").resolve()


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_manifest(path: Path, content: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _list_manifest_paths(shim_root: Path) -> list[Path]:
    if not shim_root.exists():
        return []
    paths = []
    for run_dir in shim_root.iterdir():
        manifest = run_dir / "manifest.json"
        if run_dir.is_dir() and manifest.exists():
            paths.append(manifest)
    return sorted(paths, key=lambda p: p.parent.name, reverse=True)


def list_shim_runs(cwd: Path, limit: int = 20) -> list[dict[str, Any]]:
    shim_root = _shim_root_for_cwd(cwd)
    manifests = _list_manifest_paths(shim_root)[: max(limit, 1)]
    out: list[dict[str, Any]] = []
    for manifest_path in manifests:
        content = _load_manifest(manifest_path)
        out.append(
            {
                "run_id": content.get("run_id", manifest_path.parent.name),
                "status": content.get("status", "unknown"),
                "created_at": content.get("created_at", ""),
                "restored_at": content.get("restored_at", ""),
                "cwd": content.get("cwd", ""),
                "target_provider": content.get("target_provider", ""),
                "changed_files": len(content.get("files", [])),
                "changed_rows": len(content.get("sqlite_rows", [])),
                "manifest_path": str(manifest_path),
            }
        )
    return out


def _read_session_meta(path: Path, thread_id: str) -> tuple[int, dict[str, Any], list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    first_meta_idx = -1
    first_meta_obj: dict[str, Any] | None = None
    target_idx = -1
    target_obj: dict[str, Any] | None = None

    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "session_meta":
            continue
        if first_meta_idx < 0:
            first_meta_idx = idx
            first_meta_obj = obj
        payload = obj.get("payload", {})
        if payload.get("id") == thread_id:
            target_idx = idx
            target_obj = obj
            break

    if target_idx < 0 and first_meta_idx >= 0 and first_meta_obj is not None:
        target_idx = first_meta_idx
        target_obj = first_meta_obj

    if target_idx < 0 or target_obj is None:
        raise ValueError(f"session_meta not found in rollout: {path}")

    return target_idx, target_obj, lines


def _patch_session_meta(
    payload: dict[str, Any],
    target_provider: str,
    template_payload: dict[str, Any] | None,
    template_align: bool,
) -> tuple[bool, list[str]]:
    changed_keys: list[str] = []
    if payload.get("model_provider") != target_provider:
        payload["model_provider"] = target_provider
        changed_keys.append("model_provider")

    if template_align and template_payload:
        for key, value in template_payload.items():
            if key in IMMUTABLE_META_KEYS:
                continue
            current = payload.get(key, None)
            if current != value:
                payload[key] = value
                changed_keys.append(key)

    return (len(changed_keys) > 0), sorted(set(changed_keys))


def _threads_table_columns(con: sqlite3.Connection) -> set[str]:
    cur = con.execute("PRAGMA table_info(threads)")
    return {row[1] for row in cur.fetchall()}


def _backup_relative_path(target_path: Path, codex_home: Path) -> Path:
    try:
        return target_path.resolve().relative_to(codex_home.resolve())
    except ValueError:
        normalized_parts = [part for part in target_path.resolve().parts if part not in {"/", "\\"}]
        if not normalized_parts:
            return Path("external") / "unknown"
        return Path("external").joinpath(*normalized_parts)


def _select_threads_for_cwd(con: sqlite3.Connection, cwd: str) -> list[dict[str, Any]]:
    cols = _threads_table_columns(con)
    select_order = [
        "id",
        "cwd",
        "model_provider",
        "rollout_path",
        "updated_at",
        "source",
        "cli_version",
        "model",
        "reasoning_effort",
        "agent_path",
        "memory_mode",
        "sandbox_policy",
        "approval_mode",
    ]
    selected = [c for c in select_order if c in cols]
    order_column = "updated_at" if "updated_at" in cols else "id"
    query = f"SELECT {', '.join(selected)} FROM threads WHERE cwd = ? ORDER BY {order_column} DESC"
    con.row_factory = sqlite3.Row
    cur = con.execute(query, (cwd,))
    return [dict(r) for r in cur.fetchall()]


def _update_threads_rows(
    con: sqlite3.Connection,
    rows_to_update: list[dict[str, Any]],
) -> None:
    if not rows_to_update:
        return
    for row in rows_to_update:
        thread_id = row["thread_id"]
        updates = row["after"]
        set_clause = ", ".join(f"{k}=?" for k in updates.keys())
        values = list(updates.values()) + [thread_id]
        con.execute(f"UPDATE threads SET {set_clause} WHERE id = ?", values)


def apply_provider_shim(
    *,
    cwd: Path,
    target_provider: str,
    codex_home: Path,
    run_id: str | None = None,
    template_align: bool = False,
    dry_run: bool = False,
) -> ShimApplyResult:
    project_cwd = cwd.resolve()
    codex_home_resolved = codex_home.expanduser().resolve()
    state_db_path = codex_home_resolved / "state_5.sqlite"
    if not state_db_path.exists():
        raise FileNotFoundError(f"state db not found: {state_db_path}")

    with sqlite3.connect(str(state_db_path), timeout=10) as con:
        rows = _select_threads_for_cwd(con, str(project_cwd))
        if not rows:
            raise ValueError(f"no threads found for cwd={project_cwd}")

        template_row = next((r for r in rows if r.get("model_provider") == target_provider), None)
        if template_align and template_row is None:
            raise ValueError(
                f"template-align requires at least one target-provider thread for cwd={project_cwd} "
                f"provider={target_provider}"
            )
        template_payload: dict[str, Any] | None = None
        if template_row is not None:
            rollout_path = _normalize_rollout_path(str(template_row.get("rollout_path", "")), codex_home_resolved)
            if rollout_path.exists():
                _, meta_obj, _ = _read_session_meta(rollout_path, str(template_row.get("id", "")))
                template_payload = dict(meta_obj.get("payload", {}))

        candidate_rows = [r for r in rows if r.get("model_provider") != target_provider]

        effective_run_id = run_id or _new_run_id()
        shim_root = _shim_root_for_cwd(project_cwd)
        run_dir = shim_root / effective_run_id
        if run_dir.exists():
            raise FileExistsError(f"shim run directory already exists: {run_dir}")

        manifest: dict[str, Any] = {
            "version": 1,
            "run_id": effective_run_id,
            "created_at": _utc_now_iso(),
            "cwd": str(project_cwd),
            "target_provider": target_provider,
            "codex_home": str(codex_home_resolved),
            "state_db_path": str(state_db_path),
            "status": "dry_run" if dry_run else "applied",
            "template_align": template_align,
            "template_thread_id": str(template_row.get("id", "")) if template_row else "",
            "files": [],
            "sqlite_rows": [],
            "restored_at": "",
        }

        backup_files_dir = run_dir / "files"
        files_changed = 0
        sql_rows_to_update: list[dict[str, Any]] = []

        for row in candidate_rows:
            thread_id = str(row.get("id", ""))
            rollout_raw = str(row.get("rollout_path", ""))
            if not rollout_raw:
                continue
            rollout_path = _normalize_rollout_path(rollout_raw, codex_home_resolved)
            if not rollout_path.exists():
                continue

            before_bytes = rollout_path.read_bytes()
            before_sha = _sha256_bytes(before_bytes)
            idx, meta_obj, lines = _read_session_meta(rollout_path, thread_id)
            payload = dict(meta_obj.get("payload", {}))

            changed, changed_keys = _patch_session_meta(
                payload=payload,
                target_provider=target_provider,
                template_payload=template_payload,
                template_align=template_align,
            )
            if changed:
                meta_obj["payload"] = payload
                has_newline = lines[idx].endswith("\n")
                lines[idx] = json.dumps(meta_obj, ensure_ascii=False, separators=(",", ":")) + ("\n" if has_newline else "")
                after_bytes = "".join(lines).encode("utf-8")
                after_sha = _sha256_bytes(after_bytes)
                files_changed += 1

                backup_path = backup_files_dir / _backup_relative_path(rollout_path, codex_home_resolved)
                manifest["files"].append(
                    {
                        "thread_id": thread_id,
                        "path": str(rollout_path),
                        "backup_path": str(backup_path),
                        "provider_before": str(row.get("model_provider", "")),
                        "provider_after": target_provider,
                        "sha_before": before_sha,
                        "sha_after": after_sha,
                        "changed_keys": changed_keys,
                    }
                )
                if not dry_run:
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    backup_path.write_bytes(before_bytes)
                    rollout_path.write_bytes(after_bytes)

            before_sql: dict[str, Any] = {}
            after_sql: dict[str, Any] = {}
            if row.get("model_provider") != target_provider:
                before_sql["model_provider"] = row.get("model_provider")
                after_sql["model_provider"] = target_provider

            if template_align and template_row is not None:
                for col in SQL_ALIGN_CANDIDATES:
                    if col not in row or col not in template_row:
                        continue
                    tval = template_row.get(col)
                    if row.get(col) != tval:
                        before_sql[col] = row.get(col)
                        after_sql[col] = tval

            if after_sql:
                manifest["sqlite_rows"].append(
                    {
                        "thread_id": thread_id,
                        "before": before_sql,
                        "after": after_sql,
                    }
                )
                sql_rows_to_update.append(
                    {
                        "thread_id": thread_id,
                        "after": after_sql,
                    }
                )

        if not dry_run and sql_rows_to_update:
            con.execute("BEGIN")
            try:
                _update_threads_rows(con, sql_rows_to_update)
                con.commit()
            except Exception:
                con.rollback()
                raise

        manifest_path = run_dir / "manifest.json"
        _save_manifest(manifest_path, manifest)

        return ShimApplyResult(
            run_id=effective_run_id,
            manifest_path=manifest_path,
            changed_files=files_changed,
            changed_rows=len(sql_rows_to_update),
            candidate_threads=len(candidate_rows),
            template_thread_id=str(template_row.get("id", "")) if template_row else "",
            template_align=template_align,
            dry_run=dry_run,
        )


def _resolve_manifest_for_restore(cwd: Path, run_id: str | None) -> Path:
    shim_root = _shim_root_for_cwd(cwd.resolve())
    if run_id:
        manifest_path = shim_root / run_id / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"manifest not found for run_id={run_id}: {manifest_path}")
        return manifest_path

    for path in _list_manifest_paths(shim_root):
        content = _load_manifest(path)
        if content.get("status") == "applied" and not content.get("restored_at"):
            return path
    raise FileNotFoundError(f"no pending applied shim runs found under {shim_root}")


def restore_provider_shim(
    *,
    cwd: Path,
    run_id: str | None = None,
    force: bool = False,
) -> ShimRestoreResult:
    manifest_path = _resolve_manifest_for_restore(cwd.resolve(), run_id)
    manifest = _load_manifest(manifest_path)
    files = manifest.get("files", [])
    sqlite_rows = manifest.get("sqlite_rows", [])
    state_db_path = Path(str(manifest.get("state_db_path", "")))

    restored_files = 0
    restored_rows = 0
    skipped_file_conflicts = 0
    skipped_row_conflicts = 0

    for entry in files:
        target_path = Path(str(entry["path"]))
        backup_path = Path(str(entry["backup_path"]))
        expected_after = str(entry.get("sha_after", ""))
        if not backup_path.exists():
            skipped_file_conflicts += 1
            continue
        if target_path.exists() and not force:
            current_sha = _sha256_file(target_path)
            if expected_after and current_sha != expected_after:
                skipped_file_conflicts += 1
                continue
        backup_bytes = backup_path.read_bytes()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(backup_bytes)
        restored_files += 1

    if sqlite_rows and state_db_path.exists():
        with sqlite3.connect(str(state_db_path), timeout=10) as con:
            con.row_factory = sqlite3.Row
            con.execute("BEGIN")
            try:
                for row in sqlite_rows:
                    thread_id = str(row["thread_id"])
                    before = dict(row.get("before", {}))
                    after = dict(row.get("after", {}))
                    if not before:
                        continue
                    if not force and after:
                        columns = list(after.keys())
                        select_sql = f"SELECT {', '.join(columns)} FROM threads WHERE id = ?"
                        cur = con.execute(select_sql, (thread_id,))
                        current = cur.fetchone()
                        if current is None:
                            skipped_row_conflicts += 1
                            continue
                        mismatch = any(current[col] != after[col] for col in columns)
                        if mismatch:
                            skipped_row_conflicts += 1
                            continue

                    set_clause = ", ".join(f"{k}=?" for k in before.keys())
                    values = list(before.values()) + [thread_id]
                    con.execute(f"UPDATE threads SET {set_clause} WHERE id = ?", values)
                    restored_rows += 1
                con.commit()
            except Exception:
                con.rollback()
                raise

    manifest["restored_at"] = _utc_now_iso()
    manifest["status"] = "restored"
    manifest["restore_summary"] = {
        "restored_files": restored_files,
        "restored_rows": restored_rows,
        "skipped_file_conflicts": skipped_file_conflicts,
        "skipped_row_conflicts": skipped_row_conflicts,
        "force": force,
    }
    _save_manifest(manifest_path, manifest)

    return ShimRestoreResult(
        run_id=str(manifest.get("run_id", manifest_path.parent.name)),
        manifest_path=manifest_path,
        restored_files=restored_files,
        restored_rows=restored_rows,
        skipped_file_conflicts=skipped_file_conflicts,
        skipped_row_conflicts=skipped_row_conflicts,
    )
