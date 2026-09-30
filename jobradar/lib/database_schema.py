"""SQLite schema. The jobs table is what keeps token spend low: a job is scored at most once,
ever, no matter how many runs or sources it shows up in."""

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

# Columns added after the first release; created on older databases automatically. Additive only.
MIGRATIONS = {"jobs": {"work_type": "TEXT"}, "usage": {"purpose": "TEXT DEFAULT 'score'"}}
