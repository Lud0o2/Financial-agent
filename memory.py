"""Local conversation storage for the dashboard. Investor OS markdown remains canonical."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3


DATABASE = Path(__file__).resolve().parent / "data" / "memory.db"


def _connection() -> sqlite3.Connection:
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE)
    connection.execute(
        """CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL
        )"""
    )
    return connection


def add_message(role: str, content: str) -> None:
    with _connection() as connection:
        connection.execute(
            "INSERT INTO messages (created_at, role, content) VALUES (?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), role, content),
        )


def recent_messages(limit: int = 12) -> list[dict[str, str]]:
    with _connection() as connection:
        rows = connection.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [{"role": role, "content": content} for role, content in reversed(rows)]


def clear_messages() -> None:
    with _connection() as connection:
        connection.execute("DELETE FROM messages")
