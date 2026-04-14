import sqlite3
from pathlib import Path
from typing import Iterable

from .models import BridgeSession, BridgeTurn


class BridgeStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    provider_session_id TEXT NOT NULL,
                    project_root TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    git_branch TEXT NOT NULL DEFAULT '',
                    git_commit TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_project_updated
                    ON sessions(project_root, updated_at DESC);

                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_turns_session_created
                    ON turns(session_id, created_at ASC);
                """
            )

    def upsert_session(self, session: BridgeSession) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    id, provider, provider_session_id, project_root, title, summary,
                    created_at, updated_at, git_branch, git_commit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    provider = excluded.provider,
                    provider_session_id = excluded.provider_session_id,
                    project_root = excluded.project_root,
                    title = excluded.title,
                    summary = excluded.summary,
                    updated_at = excluded.updated_at,
                    git_branch = excluded.git_branch,
                    git_commit = excluded.git_commit
                """,
                (
                    session.id,
                    session.provider,
                    session.provider_session_id,
                    session.project_root,
                    session.title,
                    session.summary,
                    session.created_at,
                    session.updated_at,
                    session.git_branch,
                    session.git_commit,
                ),
            )

    def add_turn(self, turn: BridgeTurn) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO turns (session_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (turn.session_id, turn.role, turn.content, turn.created_at),
            )

    def list_sessions(self, project_root: str, limit: int = 10) -> list[BridgeSession]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, provider, provider_session_id, project_root, title, summary,
                       created_at, updated_at, git_branch, git_commit
                FROM sessions
                WHERE project_root = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (project_root, limit),
            ).fetchall()
        return [self._row_to_session(r) for r in rows]

    def get_session(self, session_id: str) -> BridgeSession | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, provider, provider_session_id, project_root, title, summary,
                       created_at, updated_at, git_branch, git_commit
                FROM sessions
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def list_turns(self, session_id: str, limit: int = 30) -> list[BridgeTurn]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT session_id, role, content, created_at
                FROM turns
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [BridgeTurn(**dict(row)) for row in reversed(rows)]

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> BridgeSession:
        return BridgeSession(**dict(row))

    def add_turns(self, turns: Iterable[BridgeTurn]) -> None:
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO turns (session_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                ((t.session_id, t.role, t.content, t.created_at) for t in turns),
            )
