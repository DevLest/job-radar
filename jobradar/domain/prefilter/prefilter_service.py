"""Runs the free filter over stored jobs. Typically removes 90%+ of fetched jobs before a
single token is spent. No LLM or network calls here - ever."""

from __future__ import annotations

from ..jobs.job_repository import JobRepository
from .prefilter_rules import check

FIELDS = ("stage", "reject_reason", "kw_score")


class PrefilterService:
    def __init__(self, jobs: JobRepository):
        self.jobs = jobs

    def run(self, profile: dict, stages: tuple[str, ...] = ("new",)) -> tuple[int, int]:
        """Returns (passed, rejected)."""
        passed = rejected = 0
        for job in self.jobs.in_stages(stages):
            reason, score = check(job, profile)
            if reason:
                job.reject(reason, score)
                rejected += 1
            else:
                job.queue(score)
                passed += 1
            self.jobs.save(job, *FIELDS)
        return passed, rejected
