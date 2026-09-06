from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class RunRecord:
    id: int
    trigger: str
    scheduled_for: str | None
    market_session: str | None
    parent_run_id: int | None
    status: str
    attempts: int
    created_at: str
    started_at: str | None
    finished_at: str | None
    summary: str
    error: str


@dataclass(frozen=True)
class StepRecord:
    id: int
    run_id: int
    attempt: int
    name: str
    status: str
    started_at: str
    finished_at: str
    output: str


class ServiceStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trigger TEXT NOT NULL,
                    scheduled_for TEXT,
                    market_session TEXT,
                    parent_run_id INTEGER REFERENCES runs(id),
                    status TEXT NOT NULL DEFAULT 'queued',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    summary TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS runs_created_at_idx ON runs(created_at DESC);
                CREATE INDEX IF NOT EXISTS runs_schedule_idx ON runs(trigger, scheduled_for);
                CREATE TABLE IF NOT EXISTS steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL REFERENCES runs(id),
                    attempt INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    output TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS steps_run_idx ON steps(run_id, id);
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES('daily_time', '05:30')"
            )

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        with self._connect() as connection:
            row = connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return default if row is None else str(row["value"])

    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def create_run(
        self,
        *,
        trigger: str,
        scheduled_for: str | None,
        market_session: str | None,
        parent_run_id: int | None = None,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO runs(trigger, scheduled_for, market_session, parent_run_id, created_at)
                VALUES(?, ?, ?, ?, ?)
                """,
                (trigger, scheduled_for, market_session, parent_run_id, _now()),
            )
            return int(cursor.lastrowid)

    def get_run(self, run_id: int) -> RunRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return None if row is None else RunRecord(**dict(row))

    def list_runs(self, limit: int | None = 50, *, since: str | None = None) -> list[RunRecord]:
        query = "SELECT * FROM runs"
        parameters: list[str | int] = []
        if since is not None:
            query += " WHERE created_at >= ?"
            parameters.append(since)
        query += " ORDER BY id DESC"
        if limit is not None:
            query += " LIMIT ?"
            parameters.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [RunRecord(**dict(row)) for row in rows]

    def find_scheduled_run(self, scheduled_for: str) -> RunRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM runs
                WHERE trigger = 'scheduled' AND scheduled_for = ?
                ORDER BY id DESC LIMIT 1
                """,
                (scheduled_for,),
            ).fetchone()
        return None if row is None else RunRecord(**dict(row))

    def mark_running(self, run_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE runs SET status = 'running', started_at = ? WHERE id = ?",
                (_now(), run_id),
            )

    def increment_attempt(self, run_id: int) -> int:
        with self._connect() as connection:
            connection.execute("UPDATE runs SET attempts = attempts + 1 WHERE id = ?", (run_id,))
            row = connection.execute("SELECT attempts FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise ValueError(f"run {run_id} does not exist")
        return int(row["attempts"])

    def finish_run(
        self,
        run_id: int,
        status: str,
        *,
        summary: str = "",
        error: str = "",
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE runs
                SET status = ?, summary = ?, error = ?, finished_at = ?
                WHERE id = ?
                """,
                (status, summary, error, _now(), run_id),
            )

    def add_step(
        self,
        *,
        run_id: int,
        attempt: int,
        name: str,
        status: str,
        started_at: datetime,
        finished_at: datetime,
        output: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO steps(run_id, attempt, name, status, started_at, finished_at, output)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    attempt,
                    name,
                    status,
                    started_at.isoformat(),
                    finished_at.isoformat(),
                    output,
                ),
            )

    def list_steps(self, run_id: int) -> list[StepRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM steps WHERE run_id = ? ORDER BY id", (run_id,)
            ).fetchall()
        return [StepRecord(**dict(row)) for row in rows]

    def mark_interrupted_runs(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE runs
                SET status = 'failed', error = 'service restarted before completion', finished_at = ?
                WHERE status IN ('queued', 'running')
                """,
                (_now(),),
            )
