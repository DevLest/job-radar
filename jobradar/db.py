"""SQLite store. The DB is what keeps token spend low: a job is scored at most once,
ever, no matter how many runs or sources it shows up in."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .sources import Job

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    fingerprint TEXT,
    source TEXT, ext_id TEXT, title TEXT, company TEXT, url TEXT, location TEXT,
    description TEXT, tags TEXT, salary_text TEXT, salary_min REAL, salary_max REAL,
    salary_period TEXT, currency TEXT, employment_type TEXT, remote INTEGER, work_type TEXT,
    posted_at TEXT, first_seen TEXT,
    stage TEXT DEFAULT 'new',      -- new | rejected | queued | batched | scored | duplicate
    reject_reason TEXT,
    batch_id TEXT,
    kw_score REAL,
    score INTEGER, verdict TEXT, analysis TEXT,
    status TEXT DEFAULT '',        -- mirrors the latest application status for this job
    notes TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS jobs_fp ON jobs(fingerprint);
CREATE INDEX IF NOT EXISTS jobs_stage ON jobs(stage);
CREATE TABLE IF NOT EXISTS usage (
    ts TEXT, model TEXT, batch INTEGER, input_tokens INTEGER, output_tokens INTEGER,
    cache_read INTEGER, cache_write INTEGER, cost_usd REAL, purpose TEXT DEFAULT 'score'
);
CREATE TABLE IF NOT EXISTS batches (id TEXT PRIMARY KEY, created TEXT, model TEXT, done INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT, fingerprint TEXT, company TEXT, title TEXT, url TEXT,
    status TEXT DEFAULT 'drafted', -- drafted | applied | acknowledged | assessment | interview | offer | rejected | withdrawn
    method TEXT,                   -- email | website | manual
    to_email TEXT, subject TEXT, body TEXT, sent_message_id TEXT,
    created_at TEXT, applied_at TEXT, last_checked TEXT, last_update TEXT,
    next_action TEXT DEFAULT '', notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS app_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER, ts TEXT, kind TEXT, summary TEXT, message_id TEXT
);
CREATE TABLE IF NOT EXISTS emails_seen (message_id TEXT PRIMARY KEY, kind TEXT, ts TEXT, info TEXT);
CREATE TABLE IF NOT EXISTS cvs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT, path TEXT, uploaded_at TEXT, text TEXT, analysis TEXT, active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

# Columns added after the first release; created on older databases automatically.
MIGRATIONS = {"jobs": {"work_type": "TEXT"}, "usage": {"purpose": "TEXT DEFAULT 'score'"}}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fingerprint(company: str, title: str) -> str:
    """Same role posted on several boards -> same fingerprint -> scored once."""
    norm = lambda s: re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()
    return hashlib.sha1(f"{norm(company)}|{norm(title)}".encode()).hexdigest()[:16]


class DB:
    def __init__(self, path: Path):
        self.conn = sqlite3.connect(path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")  # UI + background tasks read/write concurrently
        self.conn.executescript(SCHEMA)
        for table, cols in MIGRATIONS.items():
            have = {r["name"] for r in self.conn.execute(f"PRAGMA table_info({table})")}
            for col, decl in cols.items():
                if col not in have:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        self.conn.commit()

    def insert_new(self, jobs: list[Job]) -> list[str]:
        """Insert unseen jobs; returns the ids that were new. Cross-source duplicates
        are stored with stage='duplicate' so they never reach the LLM."""
        new_ids = []
        for j in jobs:
            if self.conn.execute("SELECT 1 FROM jobs WHERE id=?", (j.id,)).fetchone():
                continue
            fp = fingerprint(j.company, j.title)
            dup = self.conn.execute("SELECT id FROM jobs WHERE fingerprint=? LIMIT 1", (fp,)).fetchone()
            d = asdict(j)
            if not d["work_type"] and j.remote is not None:
                d["work_type"] = "remote" if j.remote else ""
            d.update(id=j.id, fingerprint=fp, tags=json.dumps(j.tags), first_seen=now(),
                     remote=None if j.remote is None else int(j.remote),
                     stage="duplicate" if dup else "new",
                     reject_reason=f"duplicate of {dup['id']}" if dup else None)
            cols = ",".join(d)
            self.conn.execute(f"INSERT INTO jobs ({cols}) VALUES ({','.join('?' * len(d))})", list(d.values()))
            if not dup:
                new_ids.append(j.id)
        self.conn.commit()
        return new_ids

    def rows(self, where: str = "1", params=()) -> list[sqlite3.Row]:
        return self.conn.execute(f"SELECT * FROM jobs WHERE {where}", params).fetchall()

    def job(self, job_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()

    def update(self, job_id: str, **fields):
        sets = ",".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE jobs SET {sets} WHERE id=?", [*fields.values(), job_id])
        self.conn.commit()

    def q(self, sql: str, params=()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql: str, params=()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def exec(self, sql: str, params=()) -> int:
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur.lastrowid

    def seen_email(self, message_id: str) -> bool:
        return self.one("SELECT 1 FROM emails_seen WHERE message_id=?", (message_id,)) is not None

    def mark_email(self, message_id: str, kind: str, info: str = ""):
        self.exec("INSERT OR IGNORE INTO emails_seen VALUES (?,?,?,?)", (message_id, kind, now(), info))

    def meta(self, key: str, default: str = "") -> str:
        r = self.one("SELECT value FROM meta WHERE key=?", (key,))
        return r["value"] if r else default

    def set_meta(self, key: str, value: str):
        self.exec("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, value))

    def log_usage(self, model: str, batch: bool, usage, cost: float, purpose: str = "score"):
        self.conn.execute("INSERT INTO usage VALUES (?,?,?,?,?,?,?,?,?)", (
            now(), model, int(batch), usage.input_tokens, usage.output_tokens,
            getattr(usage, "cache_read_input_tokens", 0) or 0,
            getattr(usage, "cache_creation_input_tokens", 0) or 0, cost, purpose))
        self.conn.commit()
