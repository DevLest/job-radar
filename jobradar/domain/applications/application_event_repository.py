from __future__ import annotations

import sqlite3

from ...lib.database import Database
from ...shared.utils.date_utils import now_iso


class ApplicationEventRepository:
    """The timeline of an application: drafts, sends, status moves, notes, emails in."""

    def __init__(self, db: Database):
        self.db = db

    def add(self, app_id: int, kind: str, summary: str, message_id: str | None = None):
        self.db.execute("INSERT INTO app_events (application_id, ts, kind, summary, message_id) VALUES (?,?,?,?,?)",
                        (app_id, now_iso(), kind, summary, message_id))

    def for_application(self, app_id: int) -> list[sqlite3.Row]:
        return self.db.query("SELECT * FROM app_events WHERE application_id=? ORDER BY ts DESC, id DESC", (app_id,))

    def has_kind(self, app_id: int, kind: str) -> bool:
        return self.db.one("SELECT 1 FROM app_events WHERE application_id=? AND kind=?", (app_id, kind)) is not None

    def recent_with_company(self, limit: int = 8) -> list[sqlite3.Row]:
        return self.db.query("SELECT e.*, a.company, a.title FROM app_events e JOIN applications a "
                             "ON a.id=e.application_id ORDER BY e.ts DESC, e.id DESC LIMIT ?", (limit,))
