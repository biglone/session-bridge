from .models import BridgeSession, BridgeTurn


def build_resume_context(session: BridgeSession, turns: list[BridgeTurn]) -> str:
    lines = [
        "# Session Resume Context",
        "",
        f"- bridge_session_id: {session.id}",
        f"- provider: {session.provider}",
        f"- provider_session_id: {session.provider_session_id}",
        f"- project_root: {session.project_root}",
        f"- title: {session.title}",
        f"- summary: {session.summary}",
        f"- git_branch: {session.git_branch or '(unknown)'}",
        f"- git_commit: {session.git_commit or '(unknown)'}",
        "",
        "## Recent Turns",
    ]

    for turn in turns:
        lines.append(f"[{turn.created_at}] {turn.role}: {turn.content}")

    return "\n".join(lines)
