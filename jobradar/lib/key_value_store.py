from __future__ import annotations

from .database import Database


class KeyValueStore:
    """Small app-level flags (e.g. 'prefs_saved', 'last_auto_run') in the meta table."""

    def __init__(self, db: Database):
        self.db = db

    def get(self, key: str, default: str = "") -> str:
        row = self.db.one("SELECT value FROM meta WHERE key=?", (key,))
        return row["value"] if row else default

    def set(self, key: str, value: str):
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, value))
