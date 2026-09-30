from __future__ import annotations

import sqlite3

from ...lib.database import Database
from ...shared.utils.date_utils import now_iso


class UsageRepository:
    """Every Claude call's tokens and cost, tagged with what it was for."""

    def __init__(self, db: Database):
        self.db = db

    def log(self, model: str, batch: bool, usage, cost: float, purpose: str = "score"):
        self.db.execute("INSERT INTO usage VALUES (?,?,?,?,?,?,?,?,?)", (
            now_iso(), model, int(batch), usage.input_tokens, usage.output_tokens,
            getattr(usage, "cache_read_input_tokens", 0) or 0,
            getattr(usage, "cache_creation_input_tokens", 0) or 0, cost, purpose))

    def total_spent(self) -> float:
        return self.db.scalar("SELECT COALESCE(SUM(cost_usd),0) FROM usage")

    def spent_since(self, since: str) -> float:
        return self.db.scalar("SELECT COALESCE(SUM(cost_usd),0) FROM usage WHERE ts>=?", (since,))

    def by_feature(self) -> list[sqlite3.Row]:
        return self.db.query("SELECT purpose, model, COUNT(*) calls, SUM(input_tokens) i, SUM(output_tokens) o, "
                             "SUM(cache_read) cr, SUM(cost_usd) usd FROM usage GROUP BY purpose, model "
                             "ORDER BY usd DESC")

    def totals(self) -> sqlite3.Row:
        return self.db.one("SELECT COUNT(*) n, SUM(input_tokens) i, SUM(output_tokens) o, SUM(cache_read) c, "
                           "SUM(cost_usd) usd FROM usage")
