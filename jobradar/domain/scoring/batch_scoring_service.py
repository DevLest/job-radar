"""Batch scoring via the Message Batches API: half price, results usually within an hour."""

from __future__ import annotations

import time

from ...lib.llm_client import LlmClient, model_of
from ...shared.utils.hash_utils import short_hash
from ..jobs.job_repository import JobRepository
from .batch_repository import BatchRepository
from .scoring_prompt import parse_result, request_params, system_blocks
from .scoring_service import ScoringService

POLL_SECONDS = 30


def custom_id(job_id: str) -> str:
    return "j" + short_hash(job_id, 24)


class BatchScoringService:
    def __init__(self, jobs: JobRepository, batches: BatchRepository, llm: LlmClient, scoring: ScoringService):
        self.jobs, self.batches, self.llm, self.scoring = jobs, batches, llm, scoring

    def submit(self, profile: dict, limit: int | None = None, log=print) -> str | None:
        jobs = self.scoring.pick(profile, limit)
        if not jobs:
            log("  nothing queued for scoring")
            return None
        system = system_blocks(profile)
        batch_id = self.llm.submit_batch({custom_id(job.id): request_params(job, profile, system) for job in jobs})
        self.batches.add(batch_id, model_of(profile))
        for job in jobs:
            job.mark_batched(batch_id)
            self.jobs.save(job, "stage", "batch_id")
        log(f"  submitted batch {batch_id} with {len(jobs)} jobs")
        return batch_id

    def collect(self, wait_minutes: float = 0, log=print) -> int:
        """Collect finished batches. Returns how many are still pending."""
        pending = self.batches.pending_ids()
        if not pending:
            return 0
        deadline = time.time() + wait_minutes * 60
        while pending:
            for batch_id in list(pending):
                if not self.llm.batch_ended(batch_id):
                    continue
                total = self._collect_one(batch_id)
                self.batches.mark_done(batch_id)
                pending.remove(batch_id)
                log(f"  batch {batch_id} collected, cost ~${total:.4f}")
            if not pending or time.time() > deadline:
                break
            log(f"  waiting on {len(pending)} batch(es)...")
            time.sleep(POLL_SECONDS)
        return len(pending)

    def _collect_one(self, batch_id: str) -> float:
        by_custom_id = {custom_id(job.id): job for job in self.jobs.in_batch(batch_id)}
        total = 0.0
        for entry in self.llm.batch_results(batch_id):
            job = by_custom_id.get(entry.custom_id)
            if not job:
                continue
            if entry.result.type == "succeeded":
                message = entry.result.message
                total += self.llm.record(message, "score", batch=True)
                self.jobs.save(job, *job.record_score(parse_result(message)))
            else:  # errored / expired / canceled -> back in the queue for the next run
                job.requeue()
                self.jobs.save(job, "stage", "batch_id")
        return total
