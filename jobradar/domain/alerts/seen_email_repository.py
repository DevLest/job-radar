from __future__ import annotations

from ...lib.database import Database
from ...shared.utils.date_utils import now_iso


class SeenEmailRepository:
    """Emails already processed, so each one goes to Claude at most once."""

    def __init__(self, db: Database):
        self.db = db

    def seen(self, message_id: str) -> bool:
        return self.db.one("SELECT 1 FROM emails_seen WHERE message_id=?", (message_id,)) is not None

    def mark(self, message_id: str, kind: str, info: str = ""):
        self.db.execute("INSERT OR IGNORE INTO emails_seen VALUES (?,?,?,?)", (message_id, kind, now_iso(), info))
