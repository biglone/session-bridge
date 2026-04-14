import shutil
import subprocess
from pathlib import Path

from codex_session_bridge.consistency import build_git_consistency_section
from codex_session_bridge.models import BridgeSession


def _make_session(project_root: str, branch: str = "", commit: str = "") -> BridgeSession:
    return BridgeSession.from_provider(
        provider="vendor-x",
        provider_session_id="sid-1",
        project_root=project_root,
        title="title",
        summary="summary",
        created_at="2026-04-14T08:00:00Z",
        updated_at="2026-04-14T08:01:00Z",
        git_branch=branch,
        git_commit=commit,
    )


def test_consistency_section_for_non_git_directory(tmp_path: Path) -> None:
    session = _make_session(str(tmp_path.resolve()))
    section = build_git_consistency_section(session)
    assert "Repository Consistency" in section
    assert "not a git repository" in section


def test_consistency_section_for_git_repo_match(tmp_path: Path) -> None:
    if shutil.which("git") is None:
        return

    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "bridge-test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "bridge@test.local"], check=True)
    (repo / "a.txt").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True, text=True)

    branch = (
        subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        .stdout.strip()
    )
    commit = (
        subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        .stdout.strip()
    )

    session = _make_session(str(repo.resolve()), branch=branch, commit=commit)
    section = build_git_consistency_section(session)
    assert "branch_match: yes" in section
    assert "commit_match: yes" in section


def test_consistency_section_for_git_repo_without_commits(tmp_path: Path) -> None:
    if shutil.which("git") is None:
        return

    repo = tmp_path / "repo-empty"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True, text=True)

    session = _make_session(str(repo.resolve()), branch="main", commit="")
    section = build_git_consistency_section(session)
    assert "Repository Consistency" in section
    assert "check_status: error" not in section
    assert "commit_match: unknown" in section
