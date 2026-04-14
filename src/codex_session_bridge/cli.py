import argparse
from pathlib import Path

from .adapters.codex_rollout import import_codex_rollouts
from .models import BridgeSession, BridgeTurn
from .resume import build_resume_context
from .storage import BridgeStore


DEFAULT_DB_PATH = Path(".bridge/session-bridge.sqlite")


def _store_from_args(args: argparse.Namespace) -> BridgeStore:
    return BridgeStore(Path(args.db_path))


def cmd_init(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    print(f"Bridge store ready: {store.db_path}")
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
    sessions = store.list_sessions(project_root=project_root, limit=args.limit)
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

    turns = store.list_turns(args.session_id, limit=args.max_turns)
    context = build_resume_context(session, turns)
    print(context)
    return 0


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
    p_list.set_defaults(func=cmd_list)

    p_resume = subparsers.add_parser("resume", help="Build resume context from bridge session")
    p_resume.add_argument("session_id", help="Bridge session id")
    p_resume.add_argument("--max-turns", type=int, default=20, help="Recent turns to include")
    p_resume.set_defaults(func=cmd_resume)

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

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
