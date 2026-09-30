from __future__ import annotations

import sqlite3
from dataclasses import fields

from ...lib.database import Database, placeholders
from ...shared.utils.date_utils import now_iso
from ...shared.utils.hash_utils import fingerprint
from ..jobs.job import Job
from .application import Application
from .application_status import ACTIVE

_FIELDS = {f.name for f in fields(Application)}


def _to_application(row: sqlite3.Row) -> Application:
    return Application(**{key: row[key] for key in row.keys() if key in _FIELDS})


class ApplicationRepository:
    def __init__(self, db: Database):
        self.db = db

    def get(self, app_id: int) -> Application | None:
        row = self.db.one("SELECT * FROM applications WHERE id=?", (app_id,))
        return _to_application(row) if row else None

    def for_job(self, job_id: str) -> Application | None:
        row = self.db.one("SELECT * FROM applications WHERE job_id=? ORDER BY id DESC LIMIT 1", (job_id,))
        return _to_application(row) if row else None

    def create_draft(self, job: Job) -> int:
        return self.db.execute(
            "INSERT INTO applications (job_id, fingerprint, company, title, url, status, created_at) "
            "VALUES (?,?,?,?,?,'drafted',?)",
            (job.id, fingerprint(job.company, job.title), job.company, job.title, job.url, now_iso()))

    def update(self, app_id: int, **values):
        assignments = ",".join(f"{name}=?" for name in values)
        self.db.execute(f"UPDATE applications SET {assignments} WHERE id=?", [*values.values(), app_id])

    def save(self, app: Application, *names: str):
        assignments = ",".join(f"{name}=?" for name in names)
        self.db.execute(f"UPDATE applications SET {assignments} WHERE id=?",
                        [*(getattr(app, name) for name in names), app.id])

    def save_draft_text(self, app_id: int, subject: str, body: str, suggested_to: str):
        """Keeps a recipient you already typed; otherwise uses the suggestion."""
        self.db.execute("UPDATE applications SET subject=?, body=?, to_email=COALESCE(NULLIF(to_email,''), ?) "
                        "WHERE id=?", (subject, body, suggested_to, app_id))

    def prior(self, job: Job) -> list[Application]:
        """Applications (other than drafts for this very job) to the same role or the same company."""
        company = (job.company or "").strip().lower()
        rows = self.db.query("SELECT * FROM applications WHERE status!='drafted' AND job_id!=? AND "
                             "(fingerprint=? OR (?!='' AND lower(company)=?)) ORDER BY applied_at DESC",
                             (job.id, fingerprint(job.company, job.title), company, company))
        return [_to_application(row) for row in rows]

    def applied_index(self) -> dict:
        """Lookup of sent applications by role fingerprint and by lower-cased company."""
        rows = self.db.query("SELECT job_id, fingerprint, lower(company) c, status, applied_at FROM applications "
                             "WHERE status!='drafted'")
        return {"fp": {row["fingerprint"]: row for row in rows}, "co": {row["c"]: row for row in rows if row["c"]}}

    def all(self) -> list[Application]:
        return [_to_application(row) for row in self.db.query("SELECT * FROM applications")]

    def active(self) -> list[Application]:
        rows = self.db.query(f"SELECT * FROM applications WHERE status IN ({placeholders(ACTIVE)})", ACTIVE)
        return [_to_application(row) for row in rows]

    def active_with_source(self) -> list[tuple[Application, str | None]]:
        rows = self.db.query("SELECT a.*, j.source FROM applications a LEFT JOIN jobs j ON j.id=a.job_id "
                             f"WHERE a.status IN ({placeholders(ACTIVE)}) AND a.url != ''", ACTIVE)
        return [(_to_application(row), row["source"]) for row in rows]

    def silent_since(self, before: str) -> list[Application]:
        rows = self.db.query("SELECT * FROM applications WHERE status='applied' AND applied_at < ? AND "
                             "(next_action IS NULL OR next_action='')", (before,))
        return [_to_application(row) for row in rows]

    def board_rows(self) -> list[sqlite3.Row]:
        return self.db.query(
            "SELECT a.*, j.score, j.verdict, (SELECT summary FROM app_events e WHERE e.application_id=a.id "
            "ORDER BY e.ts DESC, e.id DESC LIMIT 1) last_event "
            "FROM applications a LEFT JOIN jobs j ON j.id=a.job_id ORDER BY COALESCE(a.last_update, a.created_at) DESC")

    def needing_attention(self, limit: int = 5) -> list[Application]:
        rows = self.db.query("SELECT * FROM applications WHERE next_action!='' AND next_action IS NOT NULL "
                             "AND status NOT IN ('rejected','withdrawn','offer') ORDER BY last_update DESC LIMIT ?",
                             (limit,))
        return [_to_application(row) for row in rows]

    def count_active(self) -> int:
        return self.db.scalar(f"SELECT COUNT(*) FROM applications WHERE status IN ({placeholders(ACTIVE)})", ACTIVE)

    def count_sent(self) -> int:
        return self.db.scalar("SELECT COUNT(*) FROM applications WHERE status!='drafted'")

    def count_interviews(self) -> int:
        return self.db.scalar("SELECT COUNT(*) FROM applications WHERE status IN ('interview','offer')")

    def status_counts(self) -> dict[str, int]:
        return {row["status"]: row["n"] for row in
                self.db.query("SELECT status, COUNT(*) n FROM applications GROUP BY status")}

