"""Pipeline steps shared by the CLI, the web UI and the scheduler. Orchestration only - each
step calls services and logs what happened."""

from __future__ import annotations

from typing import Callable

from ..container import Container

Log = Callable[[str], None]


class PipelineSteps:
    def __init__(self, container: Container):
        self.c = container

    def fetch(self, profile: dict, log: Log):
        log("Fetching job feeds...")
        postings = self.c.feed_collector.fetch_all(profile, log)
        new = self.c.jobs.insert_new(postings)
        log(f"  {len(postings)} fetched, {len(new)} new")
        self.filter(profile, log)

    def alerts(self, profile: dict, log: Log):
        log("Reading job-alert emails...")
        if not self.c.mail.imap_configured():
            log("  mailbox not configured (Settings page) - skipped")
            return
        postings = self.c.alert_service.ingest(profile, log)
        new = self.c.jobs.insert_new(postings)
        log(f"  {len(postings)} jobs in alerts, {len(new)} new")
        self.filter(profile, log)

    def filter(self, profile: dict, log: Log, refilter: bool = False):
        stages = ("new", "rejected", "queued") if refilter else ("new",)
        passed, rejected = self.c.prefilter.run(profile, stages)
        log(f"  pre-filter: {passed} queued for scoring, {rejected} rejected (free)")

    def score(self, profile: dict, log: Log, batch: bool = False, limit: int | None = None):
        log(f"Scoring with Claude ({'batch' if batch else 'real-time'})...")
        if batch:
            self.c.batch_scoring.submit(profile, limit, log)
            if self.c.batch_scoring.collect(0, log):
                log("  batch submitted - results usually arrive within an hour; use 'Collect batch results'.")
        else:
            self.c.scoring.score_queued(profile, limit, log=log)

    def collect(self, profile: dict, log: Log):
        log("Collecting batch results...")
        left = self.c.batch_scoring.collect(0, log)
        log(f"  {left} batch(es) still processing" if left else "  all batches collected")

    def updates(self, profile: dict, log: Log):
        log("Checking applications for updates...")
        self.c.update_checks.check(profile, log)
        log("  done")

    def by_name(self) -> dict[str, Callable[[dict, Log], None]]:
        return {
            "fetch": self.fetch,
            "alerts": self.alerts,
            "refilter": lambda profile, log: self.filter(profile, log, refilter=True),
            "score": self.score,
            "batch": lambda profile, log: self.score(profile, log, batch=True),
            "collect": self.collect,
            "updates": self.updates,
        }


STEP_NAMES = ["fetch", "alerts", "refilter", "score", "batch", "collect", "updates"]
LABELS = {
    "alerts": "Checking your job-alert emails",
    "fetch": "Searching job websites",
    "refilter": "Updating your job list with your preferences",
    "score": "Rating new jobs with AI",
    "batch": "Sending new jobs to AI (half price, ready within ~1 hour)",
    "collect": "Collecting finished AI ratings",
    "updates": "Checking for replies from employers",
}
