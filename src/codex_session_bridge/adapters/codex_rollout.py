import json
from dataclasses import dataclass
from pathlib import Path

from ..models import BridgeSession, BridgeTurn
from ..redaction import sanitize_text
from ..storage import BridgeStore


@dataclass(slots=True)
class ImportStats:
    scanned: int = 0
    imported: int = 0
    skipped_project: int = 0
    skipped_invalid: int = 0


@dataclass(slots=True)
class ParsedTurn:
    role: str
    content: str
    created_at: str


@dataclass(slots=True)
class ParsedSession:
    provider_session_id: str
    project_root: str
    model_provider: str
    title: str
    summary: str
    created_at: str
    updated_at: str
    git_branch: str
    git_commit: str
    turns: list[ParsedTurn]


def canonicalize_path(path_str: str) -> str:
    return str(Path(path_str).expanduser().resolve())


def _extract_text_from_message_payload(payload: dict) -> str:
    chunks: list[str] = []
    for item in payload.get("content", []):
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            chunks.append(text.strip())
    return "\n\n".join(chunks).strip()


def _cleanup_user_text(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    if text.startswith("<environment_context>"):
        return ""
    if text.startswith("<user_shell_command>"):
        return ""
    if text.startswith("# AGENTS.md instructions"):
        return ""
    return text


def _compact(text: str, max_len: int) -> str:
    text = " ".join(text.strip().split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def parse_rollout_file(file_path: Path) -> ParsedSession | None:
    meta: dict = {}
    turns: list[ParsedTurn] = []
    fallback_turns: list[ParsedTurn] = []
    first_ts = ""
    last_ts = ""

    try:
        with file_path.open("r", encoding="utf-8", errors="replace") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                ts = str(obj.get("timestamp") or "")
                if ts:
                    if not first_ts:
                        first_ts = ts
                    last_ts = ts

                obj_type = obj.get("type")
                payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}

                if obj_type == "session_meta":
                    meta = payload
                    continue

                if obj_type == "event_msg":
                    kind = payload.get("type")
                    if kind == "user_message":
                        text = _cleanup_user_text(str(payload.get("message") or ""))
                        if text:
                            text = sanitize_text(text)
                            turns.append(ParsedTurn(role="user", content=text, created_at=ts))
                    elif kind == "agent_message":
                        text = str(payload.get("message") or "").strip()
                        if text:
                            text = sanitize_text(text)
                            turns.append(ParsedTurn(role="assistant", content=text, created_at=ts))
                    continue

                if obj_type == "response_item":
                    if payload.get("type") != "message":
                        continue
                    role = str(payload.get("role") or "").strip()
                    if role not in {"user", "assistant"}:
                        continue
                    text = _extract_text_from_message_payload(payload)
                    if role == "user":
                        text = _cleanup_user_text(text)
                    if text:
                        text = sanitize_text(text)
                        fallback_turns.append(ParsedTurn(role=role, content=text, created_at=ts))
    except (OSError, json.JSONDecodeError):
        return None

    provider_session_id = str(meta.get("id") or "").strip()
    project_root = str(meta.get("cwd") or "").strip()
    if not provider_session_id or not project_root:
        return None

    if not turns:
        turns = fallback_turns
    if not turns:
        return None

    user_turns = [t.content for t in turns if t.role == "user"]
    assistant_turns = [t.content for t in turns if t.role == "assistant"]

    if user_turns:
        title = _compact(user_turns[0], 80)
    else:
        title = file_path.stem
    summary_source = assistant_turns[-1] if assistant_turns else user_turns[0]
    summary = _compact(summary_source, 240)

    git_info = meta.get("git") if isinstance(meta.get("git"), dict) else {}
    git_branch = str(git_info.get("branch") or "")
    git_commit = str(git_info.get("commit_hash") or "")
    model_provider = str(meta.get("model_provider") or "unknown")

    created_at = str(meta.get("timestamp") or first_ts or "")
    updated_at = str(last_ts or created_at)
    if not created_at:
        return None

    return ParsedSession(
        provider_session_id=provider_session_id,
        project_root=canonicalize_path(project_root),
        model_provider=model_provider,
        title=title,
        summary=summary,
        created_at=created_at,
        updated_at=updated_at,
        git_branch=git_branch,
        git_commit=git_commit,
        turns=turns,
    )


def import_codex_rollouts(
    store: BridgeStore,
    sessions_root: Path,
    provider_label: str,
    project_root_filter: str | None = None,
    limit: int = 100,
) -> ImportStats:
    stats = ImportStats()
    root = sessions_root.expanduser().resolve()
    if not root.exists():
        return stats

    files = sorted(
        root.rglob("rollout-*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if limit > 0:
        files = files[:limit]

    normalized_filter = canonicalize_path(project_root_filter) if project_root_filter else None

    for file_path in files:
        stats.scanned += 1
        parsed = parse_rollout_file(file_path)
        if parsed is None:
            stats.skipped_invalid += 1
            continue

        if normalized_filter and parsed.project_root != normalized_filter:
            stats.skipped_project += 1
            continue

        provider = f"{provider_label}:{parsed.model_provider}"
        session = BridgeSession.from_provider(
            provider=provider,
            provider_session_id=parsed.provider_session_id,
            project_root=parsed.project_root,
            title=parsed.title,
            summary=parsed.summary,
            created_at=parsed.created_at,
            updated_at=parsed.updated_at,
            git_branch=parsed.git_branch,
            git_commit=parsed.git_commit,
        )
        store.upsert_session(session)

        bridge_turns = [
            BridgeTurn(
                session_id=session.id,
                role=t.role,
                content=t.content,
                created_at=t.created_at or parsed.updated_at,
            )
            for t in parsed.turns
        ]
        store.replace_turns(session.id, bridge_turns)
        stats.imported += 1

    return stats
