import subprocess
from dataclasses import dataclass
from pathlib import Path

from .models import BridgeSession


@dataclass(slots=True)
class GitState:
    ok: bool
    is_git_repo: bool
    branch: str = ""
    commit: str = ""
    dirty_files: int = 0
    error: str = ""


def _run_git(path: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", path, *args],
        check=False,
        text=True,
        capture_output=True,
    )


def detect_git_state(project_root: str) -> GitState:
    root = str(Path(project_root).resolve())
    probe = _run_git(root, "rev-parse", "--is-inside-work-tree")
    if probe.returncode != 0:
        return GitState(ok=True, is_git_repo=False)

    branch_out = _run_git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch_out.returncode != 0:
        branch_out = _run_git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    commit_out = _run_git(root, "rev-parse", "HEAD")
    status_out = _run_git(root, "status", "--porcelain")
    if status_out.returncode != 0:
        return GitState(
            ok=False,
            is_git_repo=True,
            error=(status_out.stderr or "git status failed").strip(),
        )

    branch = branch_out.stdout.strip() if branch_out.returncode == 0 else ""
    commit = commit_out.stdout.strip() if commit_out.returncode == 0 else ""
    dirty_files = len([line for line in status_out.stdout.splitlines() if line.strip()])
    return GitState(
        ok=True,
        is_git_repo=True,
        branch=branch,
        commit=commit,
        dirty_files=dirty_files,
    )


def build_git_consistency_section(session: BridgeSession) -> str:
    state = detect_git_state(session.project_root)
    lines = ["## Repository Consistency"]
    lines.append(f"- workspace_path: {session.project_root}")

    if not state.ok:
        lines.append(f"- check_status: error ({state.error or 'unknown git error'})")
        return "\n".join(lines)

    if not state.is_git_repo:
        lines.append("- check_status: skipped (not a git repository)")
        return "\n".join(lines)

    session_branch = session.git_branch or "(unknown)"
    session_commit = session.git_commit or "(unknown)"
    current_branch = state.branch or "(unknown)"
    current_commit = state.commit or "(unknown)"

    branch_match = (
        "unknown" if session_branch == "(unknown)" else ("yes" if session_branch == current_branch else "no")
    )
    commit_match = (
        "unknown" if session_commit == "(unknown)" else ("yes" if session_commit == current_commit else "no")
    )

    lines.extend(
        [
            f"- session_branch: {session_branch}",
            f"- current_branch: {current_branch}",
            f"- branch_match: {branch_match}",
            f"- session_commit: {session_commit}",
            f"- current_commit: {current_commit}",
            f"- commit_match: {commit_match}",
            f"- working_tree_dirty_files: {state.dirty_files}",
        ]
    )

    if branch_match == "no" or commit_match == "no":
        lines.append("- warning: current repository state differs from the imported session snapshot.")

    return "\n".join(lines)
