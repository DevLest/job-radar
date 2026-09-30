"""SQLite connection with the schema applied. Repositories are the only callers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .database_schema import MIGRATIONS, SCHEMA


class Database:
    def __init__(self, path: Path):
        self.conn = sqlite3.connect(path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")  # UI + background tasks read/write concurrently
        self.conn.executescript(SCHEMA)
        self._migrate()

    def _migrate(self):
        for table, columns in MIGRATIONS.items():
            existing = {row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})")}
            for column, declaration in columns.items():
                if column not in existing:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
        self.conn.commit()

    def query(self, sql: str, params=()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql: str, params=()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def scalar(self, sql: str, params=()):
        row = self.one(sql, params)
        return row[0] if row else None

    def execute(self, sql: str, params=(), commit: bool = True) -> int:
        cursor = self.conn.execute(sql, params)
        if commit:
            self.conn.commit()
        return cursor.lastrowid

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


def placeholders(values) -> str:
    return ",".join("?" * len(values))
