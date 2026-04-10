"""Heartbeat memory — persistent state across cycles.

Simple SQLite-backed memory for the heartbeat loop.
Stores desires, judgments, plans, and execution results.
"""

from __future__ import annotations

import json
import sqlite3
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data/heartbeat/memory.db")


class HeartbeatMemory:
    """Persistent memory for the heartbeat loop."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS heartbeats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                topic TEXT,
                reason TEXT,
                plan TEXT,
                judgment_approved INTEGER,
                judgment_feedback TEXT,
                result_summary TEXT,
                result_details TEXT,
                raw_desire TEXT,
                raw_plan TEXT,
                raw_judgment TEXT,
                raw_result TEXT
            );

            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_heartbeats_timestamp
                ON heartbeats(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_heartbeats_action
                ON heartbeats(action);
        """)
        self._conn.commit()

    def save_heartbeat(
        self,
        action: str,
        topic: str | None = None,
        reason: str | None = None,
        plan: str | None = None,
        judgment_approved: bool | None = None,
        judgment_feedback: str | None = None,
        result_summary: str | None = None,
        result_details: str | None = None,
        raw_desire: str | None = None,
        raw_plan: str | None = None,
        raw_judgment: str | None = None,
        raw_result: str | None = None,
    ) -> int:
        """Save a heartbeat cycle to memory."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute(
            """INSERT INTO heartbeats
               (timestamp, action, topic, reason, plan,
                judgment_approved, judgment_feedback,
                result_summary, result_details,
                raw_desire, raw_plan, raw_judgment, raw_result)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (now, action, topic, reason, plan,
             1 if judgment_approved else 0 if judgment_approved is not None else None,
             judgment_feedback, result_summary, result_details,
             raw_desire, raw_plan, raw_judgment, raw_result),
        )
        self._conn.commit()
        logger.info("Saved heartbeat #%d: %s — %s", cursor.lastrowid, action, topic)
        return cursor.lastrowid

    def get_recent(self, hours: int = 24, limit: int = 20) -> list[dict]:
        """Get recent heartbeat records."""
        cutoff = datetime.now(timezone.utc).isoformat()
        rows = self._conn.execute(
            """SELECT timestamp, action, topic, reason, result_summary
               FROM heartbeats
               ORDER BY timestamp DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_last_heartbeat(self) -> str | None:
        """Get timestamp of the most recent heartbeat."""
        row = self._conn.execute(
            "SELECT timestamp FROM heartbeats ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        return row["timestamp"] if row else None

    def get_pending_tasks(self) -> list[dict]:
        """Get tasks that were planned but not yet completed."""
        rows = self._conn.execute(
            """SELECT timestamp, action, topic, reason, plan
               FROM heartbeats
               WHERE plan IS NOT NULL AND result_summary IS NULL
               ORDER BY timestamp DESC
               LIMIT 10""",
        ).fetchall()
        return [dict(r) for r in rows]

    def set_state(self, key: str, value: str) -> None:
        """Set a persistent state value."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """INSERT OR REPLACE INTO state (key, value, updated_at)
               VALUES (?, ?, ?)""",
            (key, value, now),
        )
        self._conn.commit()

    def get_state(self, key: str, default: str | None = None) -> str | None:
        """Get a persistent state value."""
        row = self._conn.execute(
            "SELECT value FROM state WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
