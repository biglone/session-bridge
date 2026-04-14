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
    model: str
    title: str
    summary: str
    created_at: str
    updated_at: str
    git_branch: str
    turns: list[ParsedTurn]


def canonicalize_path(path_str: str) -> str:
    return str(Path(path_str).expanduser().resolve())


def _compact(text: str, max_len: int) -> str:
    text = " ".join(text.strip().split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


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


def _extract_user_text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()

    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type in {"text", "input_text"}:
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    return "\n\n".join(parts).strip()


def _extract_assistant_text(message: dict) -> tuple[str, str]:
    content = message.get("content")
    model = str(message.get("model") or "").strip()
    if isinstance(content, str):
        return content.strip(), model

    if not isinstance(content, list):
        return "", model

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type in {"text", "output_text"}:
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    return "\n\n".join(parts).strip(), model


def parse_claude_project_file(file_path: Path) -> ParsedSession | None:
    session_id = ""
    project_root = ""
    created_at = ""
    updated_at = ""
    git_branch = ""
    model = ""
    turns: list[ParsedTurn] = []

    try:
        with file_path.open("r", encoding="utf-8", errors="replace") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                ts = str(obj.get("timestamp") or "")
                if ts:
                    if not created_at:
                        created_at = ts
                    updated_at = ts

                sid = str(obj.get("sessionId") or "")
                if sid and not session_id:
                    session_id = sid

                cwd = str(obj.get("cwd") or "")
                if cwd and not project_root:
                    project_root = cwd

                branch = str(obj.get("gitBranch") or "")
                if branch and not git_branch:
                    git_branch = branch

                rec_type = str(obj.get("type") or "")
                if rec_type == "user":
                    message = obj.get("message")
                    if not isinstance(message, dict):
                        continue
                    text = _cleanup_user_text(_extract_user_text(message))
                    if text:
                        text = sanitize_text(text)
                        turns.append(ParsedTurn(role="user", content=text, created_at=ts))
                elif rec_type == "assistant":
                    message = obj.get("message")
                    if not isinstance(message, dict):
                        continue
                    text, found_model = _extract_assistant_text(message)
                    if found_model and not model:
                        model = found_model
                    if text:
                        text = sanitize_text(text)
                        turns.append(ParsedTurn(role="assistant", content=text, created_at=ts))
    except (OSError, json.JSONDecodeError):
        return None

    if not session_id or not project_root or not turns:
        return None

    user_turns = [t.content for t in turns if t.role == "user"]
    assistant_turns = [t.content for t in turns if t.role == "assistant"]
    title_source = user_turns[0] if user_turns else file_path.stem
    summary_source = assistant_turns[-1] if assistant_turns else title_source

    title = _compact(title_source, 80)
    summary = _compact(summary_source, 240)
    if not created_at:
        return None
    if not updated_at:
        updated_at = created_at

    return ParsedSession(
        provider_session_id=session_id,
        project_root=canonicalize_path(project_root),
        model=model or "unknown",
        title=title,
        summary=summary,
        created_at=created_at,
        updated_at=updated_at,
        git_branch=git_branch,
        turns=turns,
    )


def import_claude_projects(
    store: BridgeStore,
    projects_root: Path,
    provider_label: str,
    project_root_filter: str | None = None,
    limit: int = 100,
) -> ImportStats:
    stats = ImportStats()
    root = projects_root.expanduser().resolve()
    if not root.exists():
        return stats

    files = sorted(root.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if limit > 0:
        files = files[:limit]

    normalized_filter = canonicalize_path(project_root_filter) if project_root_filter else None

    for file_path in files:
        stats.scanned += 1
        parsed = parse_claude_project_file(file_path)
        if parsed is None:
            stats.skipped_invalid += 1
            continue

        if normalized_filter and parsed.project_root != normalized_filter:
            stats.skipped_project += 1
            continue

        provider = f"{provider_label}:{parsed.model}"
        session = BridgeSession.from_provider(
            provider=provider,
            provider_session_id=parsed.provider_session_id,
            project_root=parsed.project_root,
            title=parsed.title,
            summary=parsed.summary,
            created_at=parsed.created_at,
            updated_at=parsed.updated_at,
            git_branch=parsed.git_branch,
            git_commit="",
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
