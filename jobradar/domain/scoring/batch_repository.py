from __future__ import annotations

from ...lib.database import Database
from ...shared.utils.date_utils import now_iso


class BatchRepository:
    """Message Batches submitted for scoring and not yet collected."""

    def __init__(self, db: Database):
        self.db = db

    def add(self, batch_id: str, model: str):
        self.db.execute("INSERT INTO batches (id, created, model) VALUES (?,?,?)", (batch_id, now_iso(), model))

    def pending_ids(self) -> list[str]:
        return [row["id"] for row in self.db.query("SELECT id FROM batches WHERE done=0")]

    def count_pending(self) -> int:
        return self.db.scalar("SELECT COUNT(*) FROM batches WHERE done=0")

    def has_pending(self) -> bool:
        return self.db.one("SELECT 1 FROM batches WHERE done=0") is not None

    def mark_done(self, batch_id: str):
        self.db.execute("UPDATE batches SET done=1 WHERE id=?", (batch_id,))
