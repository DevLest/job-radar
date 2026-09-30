"""Pipeline steps shared by the CLI and the web UI, plus a tiny background task runner
and the auto-check scheduler used while the UI is open."""

from __future__ import annotations

import threading
import time
import traceback
from datetime import datetime, timedelta, timezone

from . import applications, email_alerts, mailer, prefilter, scorer, sources
from .db import DB
from .settings import DB_PATH, load_profile


def step_fetch(db, profile, log):
    log("Fetching job feeds...")
    jobs = sources.fetch_all(profile, log)
    new = db.insert_new(jobs)
    log(f"  {len(jobs)} fetched, {len(new)} new")
    step_filter(db, profile, log)


def step_alerts(db, profile, log):
    log("Reading job-alert emails...")
    if not mailer.imap_configured():
        log("  mailbox not configured (Settings page) - skipped")
        return
    jobs = email_alerts.ingest(db, profile, log)
    new = db.insert_new(jobs)
    log(f"  {len(jobs)} jobs in alerts, {len(new)} new")
    step_filter(db, profile, log)


def step_filter(db, profile, log, refilter: bool = False):
    stages = ("new", "rejected", "queued") if refilter else ("new",)
    passed, rejected = prefilter.run(db, profile, stages)
    log(f"  pre-filter: {passed} queued for scoring, {rejected} rejected (free)")


def step_score(db, profile, log, batch: bool = False, limit: int | None = None):
    log(f"Scoring with Claude ({'batch' if batch else 'real-time'})...")
    if batch:
        scorer.submit_batch(db, profile, limit, log)
        left = scorer.collect_batches(db, 0, log)
        if left:
            log("  batch submitted - results usually arrive within an hour; use 'Collect batch results'.")
    else:
        scorer.score_now(db, profile, limit, log=log)


def step_collect(db, profile, log):
    log("Collecting batch results...")
    left = scorer.collect_batches(db, 0, log)
    log(f"  {left} batch(es) still processing" if left else "  all batches collected")


def step_updates(db, profile, log):
    log("Checking applications for updates...")
    applications.check_updates(db, profile, log)
    log("  done")


STEPS = {
    "fetch": step_fetch,
    "alerts": step_alerts,
    "refilter": lambda db, p, log: step_filter(db, p, log, refilter=True),
    "score": step_score,
    "batch": lambda db, p, log: step_score(db, p, log, batch=True),
    "collect": step_collect,
    "updates": step_updates,
}
LABELS = {
    "alerts": "Checking your job-alert emails",
    "fetch": "Searching job websites",
    "refilter": "Updating your job list with your preferences",
    "score": "Rating new jobs with AI",
    "batch": "Sending new jobs to AI (half price, ready within ~1 hour)",
    "collect": "Collecting finished AI ratings",
    "updates": "Checking for replies from employers",
}

MATCHES_SQL = "SELECT COUNT(*) n FROM jobs WHERE stage='scored' AND verdict IN ('apply','maybe')"


class TaskRunner:
    """One background task at a time. The UI polls state(): step-by-step progress,
    a raw log for the curious, and a short summary when finished."""

    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.steps: list[dict] = []
        self.lines: list[str] = []
        self.summary: dict = {}
        self.finished_at = ""

    def log(self, line: str):
        self.lines.append(f"{datetime.now():%H:%M:%S} {line}")
        self.lines = self.lines[-400:]

    def start(self, names: list[str]) -> bool:
        with self.lock:
            if self.running:
                return False
            self.running, self.lines, self.summary, self.finished_at = True, [], {}, ""
            self.steps = [{"key": n, "label": LABELS.get(n, n), "status": "pending", "note": ""} for n in names]
        threading.Thread(target=self._run, daemon=True).start()
        return True

    def _run(self):
        db = DB(DB_PATH)
        try:
            profile = load_profile()
            before = db.one(MATCHES_SQL)["n"]
            new_jobs_before = db.one("SELECT COUNT(*) n FROM jobs")["n"]
            for step in self.steps:
                step["status"] = "running"
                try:
                    STEPS[step["key"]](db, profile, self.log)
                    step["status"] = "done"
                except SystemExit as e:
                    step["status"], step["note"] = "failed", str(e)
                    self.log(f"  stopped: {e}")
                except Exception as e:  # keep going with the next step
                    step["status"], step["note"] = "failed", str(e)
                    self.log(f"  {step['key']} failed: {e}")
                    traceback.print_exc()
            self.summary = {
                "new_matches": db.one(MATCHES_SQL)["n"] - before,
                "new_jobs": db.one("SELECT COUNT(*) n FROM jobs")["n"] - new_jobs_before,
                "waiting": db.one("SELECT COUNT(*) n FROM jobs WHERE stage='queued'")["n"],
                "pending_batches": db.one("SELECT COUNT(*) n FROM batches WHERE done=0")["n"],
                "failed": sum(s["status"] == "failed" for s in self.steps),
            }
        finally:
            self.log("Finished.")
            self.finished_at = datetime.now().isoformat(timespec="seconds")
            self.running = False
            db.conn.close()

    def state(self) -> dict:
        return {"running": self.running, "steps": self.steps, "log": self.lines,
                "summary": self.summary, "finished_at": self.finished_at}


runner = TaskRunner()


def auto_tasks(profile: dict) -> list[str]:
    a = profile.get("automation") or {}
    order = ["alerts", "fetch", "score", "updates"]
    tasks = [t for t in order if t in (a.get("tasks") or [])]
    if "score" in tasks and a.get("score_mode", "batch") == "batch":
        tasks[tasks.index("score")] = "batch"
        tasks.insert(0, "collect")
    return tasks


def scheduler_loop():
    """Runs the configured automatic tasks every N hours while the UI is running."""
    while True:
        try:
            profile = load_profile()
            a = profile.get("automation") or {}
            if a.get("enabled") and not runner.running:
                db = DB(DB_PATH)
                last = db.meta("last_auto_run")
                due = not last or datetime.fromisoformat(last) < datetime.now(timezone.utc) - timedelta(
                    hours=float(a.get("interval_hours", 6)))
                if due:
                    db.set_meta("last_auto_run", datetime.now(timezone.utc).isoformat())
                    runner.start(auto_tasks(profile))
                db.conn.close()
        except Exception:
            traceback.print_exc()
        time.sleep(60)
