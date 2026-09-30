from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, fields

from ...lib.database import Database, placeholders
from ...shared.utils.date_utils import now_iso
from ...shared.utils.hash_utils import fingerprint
from .job import Job
from .job_posting import JobPosting
from .job_queries import GOOD_MATCH, TOP_MATCH

_JOB_FIELDS = {f.name for f in fields(Job)}


def _to_job(row: sqlite3.Row) -> Job:
    data = {key: row[key] for key in row.keys() if key in _JOB_FIELDS}
    data["tags"] = json.loads(row["tags"] or "[]")
    data["analysis"] = json.loads(row["analysis"] or "{}")
    data["remote"] = None if row["remote"] is None else bool(row["remote"])
    return Job(**data)


def _column_value(job: Job, name: str):
    value = getattr(job, name)
    if name == "analysis":
        return json.dumps(value)
    if name == "tags":
        return json.dumps(value)
    if name == "remote":
        return None if value is None else int(value)
    return value


class JobRepository:
    def __init__(self, db: Database):
        self.db = db

    def insert_new(self, postings: list[JobPosting]) -> list[str]:
        """Insert unseen jobs; returns the ids that were new. Cross-source duplicates
        are stored with stage='duplicate' so they never reach the LLM."""
        new_ids = []
        for posting in postings:
            if self.db.one("SELECT 1 FROM jobs WHERE id=?", (posting.id,)):
                continue
            fp = fingerprint(posting.company, posting.title)
            duplicate = self.db.one("SELECT id FROM jobs WHERE fingerprint=? LIMIT 1", (fp,))
            row = asdict(posting)
            if not row["work_type"] and posting.remote is not None:
                row["work_type"] = "remote" if posting.remote else ""
            row.update(id=posting.id, fingerprint=fp, tags=json.dumps(posting.tags), first_seen=now_iso(),
                       remote=None if posting.remote is None else int(posting.remote),
                       stage="duplicate" if duplicate else "new",
                       reject_reason=f"duplicate of {duplicate['id']}" if duplicate else None)
            self.db.execute(f"INSERT INTO jobs ({','.join(row)}) VALUES ({placeholders(row)})",
                            list(row.values()), commit=False)
            if not duplicate:
                new_ids.append(posting.id)
        self.db.commit()
        return new_ids

    def get(self, job_id: str) -> Job | None:
        row = self.db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
        return _to_job(row) if row else None

    def find(self, where: str = "1", params=(), order: str | None = None, limit: int | None = None) -> list[Job]:
        """`where`/`order` must come from job_queries constants; values go in `params`."""
        sql = f"SELECT * FROM jobs WHERE {where}"
        if order:
            sql += f" ORDER BY {order}"
        if limit is not None:
            sql += " LIMIT ?"
            params = [*params, limit]
        return [_to_job(row) for row in self.db.query(sql, params)]

    def save(self, job: Job, *names: str):
        assignments = ",".join(f"{name}=?" for name in names)
        self.db.execute(f"UPDATE jobs SET {assignments} WHERE id=?",
                        [*(_column_value(job, name) for name in names), job.id])

    def set_status(self, job_id: str, status: str):
        self.db.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))

    def count(self, where: str = "1", params=()) -> int:
        return self.db.scalar(f"SELECT COUNT(*) FROM jobs WHERE {where}", params)

    def count_top_matches(self) -> int:
        return self.count(TOP_MATCH)

    def count_good_matches(self, since: str | None = None) -> int:
        if since:
            return self.count(f"{GOOD_MATCH} AND first_seen>=?", (since,))
        return self.count(GOOD_MATCH)

    def count_stage(self, stage: str) -> int:
        return self.count("stage=?", (stage,))

    def queued_for_scoring(self, limit: int) -> list[Job]:
        # Best keyword matches first, newest first - so the cap drops the weakest candidates.
        return self.find("stage='queued'", order="kw_score DESC, posted_at DESC", limit=limit)

    def in_stages(self, stages: tuple[str, ...]) -> list[Job]:
        return self.find(f"stage IN ({placeholders(stages)})", stages)

    def in_batch(self, batch_id: str) -> list[Job]:
        return self.find("batch_id=?", (batch_id,))

    def sources(self) -> list[str]:
        return [row["source"] for row in self.db.query("SELECT DISTINCT source FROM jobs ORDER BY source")]

    def stage_counts(self) -> dict[str, int]:
        return {row["stage"]: row["n"] for row in self.db.query("SELECT stage, COUNT(*) n FROM jobs GROUP BY stage")}

    def top_reject_reasons(self, limit: int = 8) -> list[tuple[str, int]]:
        rows = self.db.query("SELECT substr(reject_reason, 1, instr(reject_reason || ':', ':') - 1) r, COUNT(*) n "
                             "FROM jobs WHERE stage='rejected' GROUP BY r ORDER BY n DESC LIMIT ?", (limit,))
        return [(row["r"], row["n"]) for row in rows]
