"""SQLite audit metadata; prompt bodies and model replies are never persisted."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .detector import Verdict


class AuditStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    request_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    role TEXT NOT NULL,
                    action TEXT NOT NULL,
                    engines TEXT NOT NULL,
                    rule_ids TEXT NOT NULL,
                    similarity REAL,
                    char_count INTEGER NOT NULL
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def add(self, request_id: str, source: str, provider: str, verdict: Verdict) -> None:
        with self._connect() as db:
            db.execute(
                """INSERT INTO events
                (request_id, source, provider, role, action, engines, rule_ids, similarity, char_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    request_id,
                    source,
                    provider,
                    verdict.role,
                    verdict.action,
                    json.dumps(verdict.engines),
                    json.dumps(verdict.rule_ids),
                    verdict.similarity,
                    verdict.char_count,
                ),
            )

    def recent(self, limit: int = 100) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            {
                **dict(row),
                "engines": json.loads(row["engines"]),
                "rule_ids": json.loads(row["rule_ids"]),
            }
            for row in rows
        ]

    def counts(self) -> dict[str, int]:
        with self._connect() as db:
            rows = db.execute("SELECT action, COUNT(*) AS n FROM events GROUP BY action").fetchall()
        return {row["action"]: row["n"] for row in rows}
