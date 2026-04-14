import argparse
import base64
import importlib.metadata
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from .adapters.claude_projects import import_claude_projects
from .adapters.codex_rollout import import_codex_rollouts
from .consistency import build_git_consistency_section
from .installer import install_home_plugin
from .models import BridgeSession, BridgeTurn
from .resume import build_resume_context
from .shim import apply_provider_shim, list_shim_runs, restore_provider_shim
from .storage import BridgeStore


DEFAULT_DB_PATH = Path(".bridge/session-bridge.sqlite")


def _store_from_args(args: argparse.Namespace) -> BridgeStore:
    return BridgeStore(Path(args.db_path))


def _resolve_cli_version() -> str:
    try:
        return importlib.metadata.version("session-bridge")
    except importlib.metadata.PackageNotFoundError:
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        if pyproject.exists():
            pattern = re.compile(r'^version\s*=\s*"([^"]+)"\s*$')
            for line in pyproject.read_text(encoding="utf-8").splitlines():
                match = pattern.match(line.strip())
                if match:
                    return match.group(1)
        return "0.0.0+dev"


def _resolve_project_codex_root(project_root: Path, codex_dir: str) -> Path:
    raw = Path(codex_dir).expanduser()
    if raw.is_absolute():
        return raw.resolve()
    return (project_root / raw).resolve()


def _detect_model_provider_from_config(codex_home: Path) -> str:
    config_path = codex_home.expanduser().resolve() / "config.toml"
    if not config_path.exists():
        return ""

    text = config_path.read_text(encoding="utf-8", errors="replace")
    try:
        import tomllib  # Python 3.11+

        parsed = tomllib.loads(text)
        value = parsed.get("model_provider")
        if isinstance(value, str) and value.strip():
            return value.strip()
    except Exception:
        pass

    pattern = re.compile(r'^model_provider\s*=\s*["\']([^"\']+)["\']\s*$')
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("["):
            continue
        match = pattern.match(line)
        if match:
            candidate = match.group(1).strip()
            if candidate:
                return candidate
    return ""


def _resolve_target_provider(target_provider: str, codex_home: Path) -> str:
    explicit = str(target_provider or "").strip()
    if explicit:
        return explicit

    detected = _detect_model_provider_from_config(codex_home)
    if detected:
        return detected

    config_path = codex_home.expanduser().resolve() / "config.toml"
    raise SystemExit(
        "Unable to determine target provider. "
        f"Set --target-provider explicitly or configure model_provider in {config_path}"
    )


def _discover_codex_session_roots(codex_root: Path) -> list[Path]:
    if not codex_root.exists():
        return []

    roots: set[Path] = set()
    if codex_root.is_dir() and codex_root.name == "sessions":
        roots.add(codex_root.resolve())
    roots.update(p.resolve() for p in codex_root.rglob("sessions") if p.is_dir())

    valid_roots: list[Path] = []
    for candidate in sorted(roots):
        try:
            next(candidate.rglob("rollout-*.jsonl"))
            valid_roots.append(candidate)
        except StopIteration:
            continue
    return valid_roots


def _slug(text: str) -> str:
    out = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip()).strip("-").lower()
    return out or "x"


def _provider_label_for_sessions_root(base: str, codex_root: Path, sessions_root: Path) -> str:
    try:
        rel = sessions_root.resolve().relative_to(codex_root.resolve())
    except ValueError:
        return base

    account_parts = [_slug(part) for part in rel.parts[:-1] if part.strip()]
    if not account_parts:
        return base
    return f"{base}-{'-'.join(account_parts)}"


def _auto_import_codex_from_root(
    store: BridgeStore,
    project_root: str,
    codex_root: Path,
    provider_label_base: str,
    limit: int,
) -> None:
    project_path = Path(project_root).resolve()
    session_roots = _discover_codex_session_roots(codex_root)
    if not session_roots:
        return

    for sessions_root in session_roots:
        provider_label = _provider_label_for_sessions_root(provider_label_base, codex_root, sessions_root)
        import_codex_rollouts(
            store=store,
            sessions_root=sessions_root,
            provider_label=provider_label,
            project_root_filter=str(project_path),
            limit=limit,
        )


def _auto_import_codex_sources(
    store: BridgeStore,
    project_root: str,
    scan_project_codex: bool = True,
    project_codex_dir: str = ".codex",
    project_codex_limit: int = 200,
    scan_home_codex: bool = True,
    home_codex_dir: str = "~/.codex",
    home_codex_limit: int = 2000,
) -> None:
    project_path = Path(project_root).resolve()

    if scan_project_codex:
        project_codex_root = _resolve_project_codex_root(project_path, project_codex_dir)
        _auto_import_codex_from_root(
            store=store,
            project_root=str(project_path),
            codex_root=project_codex_root,
            provider_label_base="codex-project",
            limit=project_codex_limit,
        )

    if scan_home_codex:
        home_codex_root = Path(home_codex_dir).expanduser().resolve()
        _auto_import_codex_from_root(
            store=store,
            project_root=str(project_path),
            codex_root=home_codex_root,
            provider_label_base="codex-home",
            limit=home_codex_limit,
        )


def cmd_init(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    print(f"Bridge store ready: {store.db_path}")
    return 0


def cmd_version(_: argparse.Namespace) -> int:
    print(_resolve_cli_version())
    return 0


def cmd_help(args: argparse.Namespace) -> int:
    parser = build_parser()
    target = str(getattr(args, "command", "") or "").strip()
    if not target:
        parser.print_help()
        return 0
    try:
        parser.parse_args([target, "--help"])
    except SystemExit as exc:
        code = int(exc.code) if isinstance(exc.code, int) else 1
        return code
    return 0


def cmd_sync_demo(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    session = BridgeSession.new(
        provider=args.provider,
        provider_session_id=args.provider_session_id,
        project_root=str(Path(args.project_root).resolve()),
        title=args.title,
        summary=args.summary,
        git_branch=args.git_branch or "",
        git_commit=args.git_commit or "",
    )
    store.upsert_session(session)

    for turn_raw in args.turn:
        role, sep, content = turn_raw.partition(":")
        if not sep:
            raise SystemExit(f"Invalid --turn format: {turn_raw!r}. Expected role:content")
        store.add_turn(BridgeTurn.new(session.id, role.strip(), content.strip()))

    print(f"Synced session: {session.id}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    project_root = str(Path(args.project_root).resolve())
    _auto_import_codex_sources(
        store=store,
        project_root=project_root,
        scan_project_codex=not bool(getattr(args, "no_scan_project_codex", False)),
        project_codex_dir=str(getattr(args, "project_codex_dir", ".codex")),
        project_codex_limit=int(getattr(args, "project_codex_limit", 200)),
        scan_home_codex=not bool(getattr(args, "no_scan_home_codex", False)),
        home_codex_dir=str(getattr(args, "home_codex_dir", "~/.codex")),
        home_codex_limit=int(getattr(args, "home_codex_limit", 2000)),
    )
    sessions = store.list_sessions(
        project_root=project_root,
        limit=args.limit,
        provider_filter=args.provider,
    )
    if not sessions:
        print(f"No bridge sessions for {project_root}")
        return 0

    for s in sessions:
        print(
            f"{s.id} | {s.updated_at} | {s.provider} | {s.title} "
            f"| branch={s.git_branch or '-'} commit={s.git_commit[:10] or '-'}"
        )
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    session = store.get_session(args.session_id)
    if session is None:
        raise SystemExit(f"Session not found: {args.session_id}")

    return _print_resume(
        store,
        session.id,
        args.max_turns,
        args.no_consistency_check,
        copy_output=bool(getattr(args, "copy", False)),
    )


def _copy_to_clipboard(text: str) -> tuple[bool, str]:
    commands = [
        ["pbcopy"],  # macOS
        ["wl-copy"],  # Wayland
        ["xclip", "-selection", "clipboard"],  # X11
        ["xsel", "--clipboard", "--input"],  # X11
        ["clip.exe"],  # Windows
        ["clip"],  # Windows (fallback alias)
    ]

    payload = text.encode("utf-8")
    for command in commands:
        executable = command[0]
        if shutil.which(executable) is None:
            continue
        try:
            subprocess.run(
                command,
                input=payload,
                check=True,
                timeout=5,
            )
            return True, executable
        except (OSError, subprocess.SubprocessError):
            continue

    if _copy_via_osc52(text):
        return True, "osc52"

    return False, ""


def _copy_via_osc52(text: str) -> bool:
    if os.getenv("SESSION_BRIDGE_DISABLE_OSC52", "").strip().lower() in {"1", "true", "yes"}:
        return False
    if not sys.stdout.isatty():
        return False

    payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
    max_bytes = int(os.getenv("SESSION_BRIDGE_OSC52_MAX_B64", "200000"))
    if len(payload) > max_bytes:
        return False

    sequence = f"\033]52;c;{payload}\a"
    if os.getenv("TMUX"):
        sequence = f"\033Ptmux;\033{sequence}\033\\"
    elif os.getenv("TERM", "").startswith("screen"):
        sequence = f"\033P{sequence}\033\\"

    try:
        sys.stdout.write(sequence)
        sys.stdout.flush()
        return True
    except OSError:
        return False


def _print_resume(
    store: BridgeStore,
    session_id: str,
    max_turns: int,
    no_consistency_check: bool,
    copy_output: bool = False,
) -> int:
    session = store.get_session(session_id)
    if session is None:
        raise SystemExit(f"Session not found: {session_id}")

    turns = store.list_turns(session_id, limit=max_turns)
    context = build_resume_context(session, turns)
    if not no_consistency_check:
        context = f"{context}\n\n{build_git_consistency_section(session)}"

    if copy_output:
        copied, command_name = _copy_to_clipboard(context)
        if copied:
            print(
                f"Resume context copied to clipboard via '{command_name}'. "
                "Open a new Codex session and paste to continue."
            )
            print(
                f"Session: {session.id} | turns_included={len(turns)} | "
                f"chars={len(context)}"
            )
            return 0
        print(
            "Clipboard copy failed; printing full resume context below. "
            "Install one of: pbcopy, wl-copy, xclip, xsel, or enable OSC52-capable terminal clipboard.",
            file=sys.stderr,
        )

    print(context)
    return 0


def cmd_resume_latest(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    project_root = str(Path(args.project_root).resolve())
    _auto_import_codex_sources(
        store=store,
        project_root=project_root,
        scan_project_codex=not bool(getattr(args, "no_scan_project_codex", False)),
        project_codex_dir=str(getattr(args, "project_codex_dir", ".codex")),
        project_codex_limit=int(getattr(args, "project_codex_limit", 200)),
        scan_home_codex=not bool(getattr(args, "no_scan_home_codex", False)),
        home_codex_dir=str(getattr(args, "home_codex_dir", "~/.codex")),
        home_codex_limit=int(getattr(args, "home_codex_limit", 2000)),
    )
    session = store.get_latest_session(project_root=project_root, provider_filter=args.provider)
    if session is None:
        hint = f" provider filter={args.provider!r}" if args.provider else ""
        raise SystemExit(f"No sessions found for project={project_root}{hint}")
    return _print_resume(
        store,
        session.id,
        args.max_turns,
        args.no_consistency_check,
        copy_output=bool(getattr(args, "copy", True)),
    )


def cmd_import_codex(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    project_root_filter = None if args.all_projects else str(Path(args.project_root).resolve())
    stats = import_codex_rollouts(
        store=store,
        sessions_root=Path(args.sessions_root),
        provider_label=args.provider_label,
        project_root_filter=project_root_filter,
        limit=args.limit,
    )
    print(
        "Import finished: "
        f"scanned={stats.scanned} imported={stats.imported} "
        f"skipped_project={stats.skipped_project} skipped_invalid={stats.skipped_invalid}"
    )
    return 0


def cmd_import_claude(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    project_root_filter = None if args.all_projects else str(Path(args.project_root).resolve())
    stats = import_claude_projects(
        store=store,
        projects_root=Path(args.projects_root),
        provider_label=args.provider_label,
        project_root_filter=project_root_filter,
        limit=args.limit,
    )
    print(
        "Import finished: "
        f"scanned={stats.scanned} imported={stats.imported} "
        f"skipped_project={stats.skipped_project} skipped_invalid={stats.skipped_invalid}"
    )
    return 0


def cmd_import_all(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    project_root_filter = None if args.all_projects else str(Path(args.project_root).resolve())

    codex_stats = import_codex_rollouts(
        store=store,
        sessions_root=Path(args.codex_sessions_root),
        provider_label=args.codex_provider_label,
        project_root_filter=project_root_filter,
        limit=args.codex_limit,
    )
    claude_stats = import_claude_projects(
        store=store,
        projects_root=Path(args.claude_projects_root),
        provider_label=args.claude_provider_label,
        project_root_filter=project_root_filter,
        limit=args.claude_limit,
    )

    print(
        "Codex import: "
        f"scanned={codex_stats.scanned} imported={codex_stats.imported} "
        f"skipped_project={codex_stats.skipped_project} skipped_invalid={codex_stats.skipped_invalid}"
    )
    print(
        "Claude import: "
        f"scanned={claude_stats.scanned} imported={claude_stats.imported} "
        f"skipped_project={claude_stats.skipped_project} skipped_invalid={claude_stats.skipped_invalid}"
    )
    print(
        "Total imported sessions: "
        f"{codex_stats.imported + claude_stats.imported}"
    )
    return 0


def cmd_copy_local(args: argparse.Namespace) -> int:
    remote_project_root = str(getattr(args, "remote_project_root", ".") or ".")
    remote_bin = str(getattr(args, "remote_bin", "session-bridge") or "session-bridge")
    remote_db_path = str(getattr(args, "remote_db_path", "") or "").strip()

    remote_parts: list[str] = [remote_bin]
    if remote_db_path:
        remote_parts.extend(["--db-path", remote_db_path])
    remote_parts.extend(
        [
            "resume-latest",
            "--project-root",
            ".",
            "--no-copy",
            "--max-turns",
            str(args.max_turns),
        ]
    )
    if args.provider:
        remote_parts.extend(["--provider", args.provider])
    if bool(getattr(args, "no_consistency_check", False)):
        remote_parts.append("--no-consistency-check")
    if bool(getattr(args, "no_scan_project_codex", False)):
        remote_parts.append("--no-scan-project-codex")
    if bool(getattr(args, "no_scan_home_codex", False)):
        remote_parts.append("--no-scan-home-codex")

    remote_command = " ".join(shlex.quote(part) for part in remote_parts)
    ssh_command = f"cd {shlex.quote(remote_project_root)} && {remote_command}"
    result = subprocess.run(
        [str(args.ssh_bin), "-T", str(args.host), ssh_command],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(
            f"Remote command failed via SSH target={args.host} exit_code={result.returncode}",
            file=sys.stderr,
        )
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)
        return result.returncode

    content = result.stdout
    if not content.strip():
        print("Remote command succeeded but produced empty output.", file=sys.stderr)
        return 1

    copied, method = _copy_to_clipboard(content)
    if copied:
        print(
            f"Remote resume context copied to local clipboard via '{method}'. "
            f"source={args.host}:{remote_project_root}"
        )
        print(f"chars={len(content)}")
        return 0

    print(
        "Local clipboard copy failed; printing remote resume context below.",
        file=sys.stderr,
    )
    print(content)
    return 0


def cmd_shim_apply(args: argparse.Namespace) -> int:
    cwd = Path(args.cwd).expanduser().resolve()
    codex_home = Path(args.codex_home)
    target_provider = _resolve_target_provider(str(getattr(args, "target_provider", "")), codex_home)
    result = apply_provider_shim(
        cwd=cwd,
        target_provider=target_provider,
        codex_home=codex_home,
        run_id=str(args.run_id).strip() or None,
        template_align=bool(args.template_align),
        dry_run=bool(args.dry_run),
    )
    print(
        "Shim apply finished: "
        f"run_id={result.run_id} dry_run={result.dry_run} "
        f"candidate_threads={result.candidate_threads} changed_files={result.changed_files} "
        f"changed_rows={result.changed_rows} template_align={result.template_align}"
    )
    if result.template_thread_id:
        print(f"template_thread_id={result.template_thread_id}")
    print(f"manifest={result.manifest_path}")
    return 0


def cmd_shim_restore(args: argparse.Namespace) -> int:
    cwd = Path(args.cwd).expanduser().resolve()
    result = restore_provider_shim(
        cwd=cwd,
        run_id=str(args.run_id).strip() or None,
        force=bool(args.force),
    )
    print(
        "Shim restore finished: "
        f"run_id={result.run_id} restored_files={result.restored_files} "
        f"restored_rows={result.restored_rows} "
        f"skipped_file_conflicts={result.skipped_file_conflicts} "
        f"skipped_row_conflicts={result.skipped_row_conflicts}"
    )
    print(f"manifest={result.manifest_path}")
    return 0


def cmd_shim_status(args: argparse.Namespace) -> int:
    cwd = Path(args.cwd).expanduser().resolve()
    runs = list_shim_runs(cwd=cwd, limit=int(args.limit))
    if not runs:
        print(f"No shim runs for {cwd}")
        return 0

    for run in runs:
        print(
            f"{run['run_id']} | {run['status']} | {run['created_at']} | "
            f"target={run['target_provider']} | files={run['changed_files']} rows={run['changed_rows']}"
        )
    return 0


def _normalize_shim_run_command(command: list[str]) -> list[str]:
    cmd = list(command or [])
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    return cmd


def cmd_shim_run(args: argparse.Namespace) -> int:
    cwd = Path(args.cwd).expanduser().resolve()
    codex_home = Path(args.codex_home)
    target_provider = _resolve_target_provider(str(getattr(args, "target_provider", "")), codex_home)
    result = apply_provider_shim(
        cwd=cwd,
        target_provider=target_provider,
        codex_home=codex_home,
        run_id=str(args.run_id).strip() or None,
        template_align=bool(args.template_align),
        dry_run=False,
    )
    print(
        "Shim apply finished: "
        f"run_id={result.run_id} candidate_threads={result.candidate_threads} "
        f"changed_files={result.changed_files} changed_rows={result.changed_rows}"
    )

    wrapped_command = _normalize_shim_run_command(list(getattr(args, "command", []) or []))
    if not wrapped_command:
        wrapped_command = ["codex"]
    print(f"Executing under shim: {' '.join(shlex.quote(part) for part in wrapped_command)}")

    command_exit_code = 0
    try:
        try:
            command_exit_code = subprocess.run(
                wrapped_command,
                cwd=str(cwd),
            ).returncode
        except OSError as exc:
            print(f"Wrapped command failed to start: {exc}", file=sys.stderr)
            command_exit_code = 127
    finally:
        try:
            restored = restore_provider_shim(
                cwd=cwd,
                run_id=result.run_id,
                force=bool(args.force_restore),
            )
            print(
                "Shim restore finished: "
                f"run_id={restored.run_id} restored_files={restored.restored_files} "
                f"restored_rows={restored.restored_rows} "
                f"skipped_file_conflicts={restored.skipped_file_conflicts} "
                f"skipped_row_conflicts={restored.skipped_row_conflicts}"
            )
        except Exception as exc:
            print(
                "Shim restore failed. Manual restore may be required: "
                f"run_id={result.run_id} error={exc}",
                file=sys.stderr,
            )
            if command_exit_code == 0:
                return 1
    return command_exit_code


def cmd_install_plugin(args: argparse.Namespace) -> int:
    result = install_home_plugin(
        plugin_source=args.plugin_source,
        plugins_home=args.plugins_home,
        marketplace_path=args.marketplace_path,
    )
    print(f"Plugin installed: {result.plugin_name}")
    print(f"- source: {result.plugin_source}")
    print(f"- target: {result.plugin_target} ({result.link_action})")
    print(f"- marketplace: {result.marketplace_path} ({result.marketplace_action})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bridge", description="Codex session bridge CLI")
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="Path to SQLite store (default: .bridge/session-bridge.sqlite)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_init = subparsers.add_parser("init", help="Initialize local bridge database")
    p_init.set_defaults(func=cmd_init)

    p_help = subparsers.add_parser("help", help="Show top-level or command-specific help")
    p_help.add_argument("command", nargs="?", help="Optional command name (for example: resume-latest)")
    p_help.set_defaults(func=cmd_help)

    p_version = subparsers.add_parser("version", help="Print current session-bridge version")
    p_version.set_defaults(func=cmd_version)

    p_sync = subparsers.add_parser(
        "sync-demo",
        help="Insert a demo provider session (temporary command until real adapters are wired)",
    )
    p_sync.add_argument("--provider", required=True, help="Provider name, e.g. vendor-a")
    p_sync.add_argument("--provider-session-id", required=True, help="Provider-native session id")
    p_sync.add_argument("--project-root", default=".", help="Project root path")
    p_sync.add_argument("--title", required=True, help="Session title")
    p_sync.add_argument("--summary", default="", help="Session summary")
    p_sync.add_argument("--git-branch", default="", help="Git branch snapshot")
    p_sync.add_argument("--git-commit", default="", help="Git commit snapshot")
    p_sync.add_argument(
        "--turn",
        action="append",
        default=[],
        help="Conversation turn in role:content format; can be repeated",
    )
    p_sync.set_defaults(func=cmd_sync_demo)

    p_list = subparsers.add_parser("list", help="List latest bridge sessions for project root")
    p_list.add_argument("--project-root", default=".", help="Project root path")
    p_list.add_argument("--limit", type=int, default=10, help="Maximum sessions to display")
    p_list.add_argument(
        "--provider",
        default="",
        help="Optional case-insensitive provider filter (substring match)",
    )
    p_list.add_argument(
        "--project-codex-dir",
        default=".codex",
        help="Project-local Codex history directory to scan before listing (default: .codex)",
    )
    p_list.add_argument(
        "--project-codex-limit",
        type=int,
        default=200,
        help="Maximum rollout files to scan per discovered project Codex sessions root",
    )
    p_list.add_argument(
        "--no-scan-project-codex",
        action="store_true",
        help="Disable auto-import from project-local Codex directory before listing",
    )
    p_list.add_argument(
        "--home-codex-dir",
        default="~/.codex",
        help="Home Codex directory to scan before listing (default: ~/.codex)",
    )
    p_list.add_argument(
        "--home-codex-limit",
        type=int,
        default=2000,
        help="Maximum rollout files to scan per discovered home Codex sessions root",
    )
    p_list.add_argument(
        "--no-scan-home-codex",
        action="store_true",
        help="Disable auto-import from home Codex directory before listing",
    )
    p_list.set_defaults(func=cmd_list)

    p_resume = subparsers.add_parser("resume", help="Build resume context from bridge session")
    p_resume.add_argument("session_id", help="Bridge session id")
    p_resume.add_argument("--max-turns", type=int, default=20, help="Recent turns to include")
    p_resume.add_argument(
        "--copy",
        action="store_true",
        help="Copy generated resume context to system clipboard and print a short continuation hint",
    )
    p_resume.add_argument(
        "--no-consistency-check",
        action="store_true",
        help="Skip git branch/commit consistency check section",
    )
    p_resume.set_defaults(func=cmd_resume)

    p_resume_latest = subparsers.add_parser(
        "resume-latest",
        help="Resume the latest session for a project (optionally filtered by provider)",
    )
    p_resume_latest.add_argument("--project-root", default=".", help="Project root path")
    p_resume_latest.add_argument(
        "--provider",
        default="",
        help="Optional case-insensitive provider filter (substring match)",
    )
    p_resume_latest.add_argument(
        "--project-codex-dir",
        default=".codex",
        help="Project-local Codex history directory to scan before resolving latest session (default: .codex)",
    )
    p_resume_latest.add_argument(
        "--project-codex-limit",
        type=int,
        default=200,
        help="Maximum rollout files to scan per discovered project Codex sessions root",
    )
    p_resume_latest.add_argument(
        "--no-scan-project-codex",
        action="store_true",
        help="Disable auto-import from project-local Codex directory before resolving latest session",
    )
    p_resume_latest.add_argument(
        "--home-codex-dir",
        default="~/.codex",
        help="Home Codex directory to scan before resolving latest session (default: ~/.codex)",
    )
    p_resume_latest.add_argument(
        "--home-codex-limit",
        type=int,
        default=2000,
        help="Maximum rollout files to scan per discovered home Codex sessions root",
    )
    p_resume_latest.add_argument(
        "--no-scan-home-codex",
        action="store_true",
        help="Disable auto-import from home Codex directory before resolving latest session",
    )
    p_resume_latest.add_argument("--max-turns", type=int, default=20, help="Recent turns to include")
    copy_group = p_resume_latest.add_mutually_exclusive_group()
    copy_group.add_argument(
        "--copy",
        dest="copy",
        action="store_true",
        help="Copy generated resume context to system clipboard (default behavior)",
    )
    copy_group.add_argument(
        "--no-copy",
        dest="copy",
        action="store_false",
        help="Print full resume context to terminal instead of copying to clipboard",
    )
    p_resume_latest.set_defaults(copy=True)
    p_resume_latest.add_argument(
        "--no-consistency-check",
        action="store_true",
        help="Skip git branch/commit consistency check section",
    )
    p_resume_latest.set_defaults(func=cmd_resume_latest)

    p_import = subparsers.add_parser(
        "import-codex",
        help="Import real Codex rollout sessions from ~/.codex/sessions into bridge store",
    )
    p_import.add_argument(
        "--sessions-root",
        default="~/.codex/sessions",
        help="Path to Codex sessions root directory",
    )
    p_import.add_argument(
        "--provider-label",
        default="codex",
        help="Provider label namespace (e.g. codex-openai-a, codex-openai-b)",
    )
    p_import.add_argument(
        "--project-root",
        default=".",
        help="Only import sessions where logged cwd matches this project path",
    )
    p_import.add_argument(
        "--all-projects",
        action="store_true",
        help="Import sessions from all project roots instead of filtering",
    )
    p_import.add_argument("--limit", type=int, default=200, help="Maximum rollout files to scan")
    p_import.set_defaults(func=cmd_import_codex)

    p_import_claude = subparsers.add_parser(
        "import-claude",
        help="Import Claude project sessions from ~/.claude/projects into bridge store",
    )
    p_import_claude.add_argument(
        "--projects-root",
        default="~/.claude/projects",
        help="Path to Claude projects root directory",
    )
    p_import_claude.add_argument(
        "--provider-label",
        default="claude-code",
        help="Provider label namespace (e.g. claude-main, claude-alt)",
    )
    p_import_claude.add_argument(
        "--project-root",
        default=".",
        help="Only import sessions where logged cwd matches this project path",
    )
    p_import_claude.add_argument(
        "--all-projects",
        action="store_true",
        help="Import sessions from all project roots instead of filtering",
    )
    p_import_claude.add_argument("--limit", type=int, default=200, help="Maximum JSONL files to scan")
    p_import_claude.set_defaults(func=cmd_import_claude)

    p_import_all = subparsers.add_parser(
        "import-all",
        help="Import both Codex rollout logs and Claude project logs into bridge store",
    )
    p_import_all.add_argument(
        "--project-root",
        default=".",
        help="Only import sessions where logged cwd matches this project path",
    )
    p_import_all.add_argument(
        "--all-projects",
        action="store_true",
        help="Import sessions from all project roots instead of filtering",
    )
    p_import_all.add_argument(
        "--codex-sessions-root",
        default="~/.codex/sessions",
        help="Path to Codex sessions root directory",
    )
    p_import_all.add_argument(
        "--claude-projects-root",
        default="~/.claude/projects",
        help="Path to Claude projects root directory",
    )
    p_import_all.add_argument(
        "--codex-provider-label",
        default="codex",
        help="Provider label namespace for Codex data",
    )
    p_import_all.add_argument(
        "--claude-provider-label",
        default="claude-code",
        help="Provider label namespace for Claude data",
    )
    p_import_all.add_argument(
        "--codex-limit",
        type=int,
        default=200,
        help="Maximum Codex rollout files to scan",
    )
    p_import_all.add_argument(
        "--claude-limit",
        type=int,
        default=200,
        help="Maximum Claude JSONL files to scan",
    )
    p_import_all.set_defaults(func=cmd_import_all)

    p_copy_local = subparsers.add_parser(
        "copy-local",
        help="Run remote resume-latest over SSH and copy output into local clipboard",
    )
    p_copy_local.add_argument(
        "--host",
        required=True,
        help="SSH target (for example: jetson or user@jetson)",
    )
    p_copy_local.add_argument(
        "--remote-project-root",
        default=".",
        help="Remote project root directory (command runs as: cd <dir> && ...)",
    )
    p_copy_local.add_argument(
        "--provider",
        default="",
        help="Optional provider filter passed to remote resume-latest",
    )
    p_copy_local.add_argument(
        "--max-turns",
        type=int,
        default=100,
        help="Recent turns to include for remote resume-latest",
    )
    p_copy_local.add_argument(
        "--no-consistency-check",
        action="store_true",
        help="Pass through to remote resume-latest",
    )
    p_copy_local.add_argument(
        "--no-scan-project-codex",
        action="store_true",
        help="Pass through to remote resume-latest",
    )
    p_copy_local.add_argument(
        "--no-scan-home-codex",
        action="store_true",
        help="Pass through to remote resume-latest",
    )
    p_copy_local.add_argument(
        "--remote-db-path",
        default="",
        help="Optional remote SQLite db path passed as global --db-path",
    )
    p_copy_local.add_argument(
        "--remote-bin",
        default="session-bridge",
        help="Remote session-bridge executable name/path",
    )
    p_copy_local.add_argument(
        "--ssh-bin",
        default="ssh",
        help="Local SSH executable to invoke",
    )
    p_copy_local.set_defaults(func=cmd_copy_local)

    p_shim = subparsers.add_parser(
        "shim",
        help="Temporarily align Codex thread model_provider for cross-provider /resume compatibility",
    )
    shim_subparsers = p_shim.add_subparsers(dest="shim_command", required=True)

    p_shim_apply = shim_subparsers.add_parser(
        "apply",
        help="Apply provider shim for one project (backs up JSONL and SQLite row values)",
    )
    p_shim_apply.add_argument("--cwd", default=".", help="Project cwd to target (default: .)")
    p_shim_apply.add_argument(
        "--target-provider",
        default="",
        help=(
            "Provider value to rewrite candidate threads to. "
            "Default: auto-detect from <codex-home>/config.toml model_provider"
        ),
    )
    p_shim_apply.add_argument(
        "--codex-home",
        default="~/.codex",
        help="Codex home directory containing state_5.sqlite and sessions (default: ~/.codex)",
    )
    p_shim_apply.add_argument("--run-id", default="", help="Optional explicit shim run id")
    p_shim_apply.add_argument(
        "--template-align",
        action="store_true",
        help="Also align compatible payload/SQLite fields to latest target-provider thread shape",
    )
    p_shim_apply.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and persist manifest only; do not mutate rollout files or SQLite",
    )
    p_shim_apply.set_defaults(func=cmd_shim_apply)

    p_shim_restore = shim_subparsers.add_parser(
        "restore",
        help="Restore one shim run from backup manifest (latest pending run by default)",
    )
    p_shim_restore.add_argument("--cwd", default=".", help="Project cwd to target (default: .)")
    p_shim_restore.add_argument("--run-id", default="", help="Shim run id to restore (optional)")
    p_shim_restore.add_argument(
        "--force",
        action="store_true",
        help="Force restore even if current files/rows no longer match expected shim-applied values",
    )
    p_shim_restore.set_defaults(func=cmd_shim_restore)

    p_shim_status = shim_subparsers.add_parser(
        "status",
        help="List recent shim runs for current project",
    )
    p_shim_status.add_argument("--cwd", default=".", help="Project cwd to inspect (default: .)")
    p_shim_status.add_argument("--limit", type=int, default=20, help="Maximum shim runs to show")
    p_shim_status.set_defaults(func=cmd_shim_status)

    p_shim_run = shim_subparsers.add_parser(
        "run",
        help="Apply shim, run a command (default: codex), then auto-restore",
    )
    p_shim_run.add_argument("--cwd", default=".", help="Project cwd to target (default: .)")
    p_shim_run.add_argument(
        "--target-provider",
        default="",
        help=(
            "Provider value to rewrite candidate threads to during wrapped command execution. "
            "Default: auto-detect from <codex-home>/config.toml model_provider"
        ),
    )
    p_shim_run.add_argument(
        "--codex-home",
        default="~/.codex",
        help="Codex home directory containing state_5.sqlite and sessions (default: ~/.codex)",
    )
    p_shim_run.add_argument("--run-id", default="", help="Optional explicit shim run id")
    p_shim_run.add_argument(
        "--template-align",
        action="store_true",
        help="Also align compatible payload/SQLite fields to latest target-provider thread shape",
    )
    p_shim_run.add_argument(
        "--force-restore",
        action="store_true",
        help="Force restore even if file/row conflict is detected at restore time",
    )
    p_shim_run.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Wrapped command to execute after apply. Use '-- <command ...>' to avoid parser ambiguity.",
    )
    p_shim_run.set_defaults(func=cmd_shim_run)

    p_install = subparsers.add_parser(
        "install-plugin",
        help="Install this plugin into home marketplace (~/.agents/plugins/marketplace.json)",
    )
    p_install.add_argument(
        "--plugin-source",
        default=".",
        help="Path to plugin source directory containing .codex-plugin/plugin.json",
    )
    p_install.add_argument(
        "--plugins-home",
        default="~/plugins",
        help="Directory where plugin symlink should be created",
    )
    p_install.add_argument(
        "--marketplace-path",
        default="~/.agents/plugins/marketplace.json",
        help="Marketplace file path to create/update",
    )
    p_install.set_defaults(func=cmd_install_plugin)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
