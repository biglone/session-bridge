from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class BridgeSession:
    id: str
    provider: str
    provider_session_id: str
    project_root: str
    title: str
    summary: str
    created_at: str
    updated_at: str
    git_branch: str = ""
    git_commit: str = ""

    @classmethod
    def new(
        cls,
        provider: str,
        provider_session_id: str,
        project_root: str,
        title: str,
        summary: str,
        git_branch: str = "",
        git_commit: str = "",
    ) -> "BridgeSession":
        now = utc_now_iso()
        return cls(
            id=str(uuid4()),
            provider=provider,
            provider_session_id=provider_session_id,
            project_root=project_root,
            title=title,
            summary=summary,
            created_at=now,
            updated_at=now,
            git_branch=git_branch,
            git_commit=git_commit,
        )


@dataclass(slots=True)
class BridgeTurn:
    session_id: str
    role: str
    content: str
    created_at: str

    @classmethod
    def new(cls, session_id: str, role: str, content: str) -> "BridgeTurn":
        return cls(
            session_id=session_id,
            role=role,
            content=content,
            created_at=utc_now_iso(),
        )
