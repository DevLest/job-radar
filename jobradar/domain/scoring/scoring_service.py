"""Real-time scoring: one call per job, the first alone (it writes the prompt cache), the rest
in parallel reading it. Each job is scored at most once - only 'queued' jobs are picked."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

from ...lib.llm_client import LlmClient
from ..jobs.job import Job
from ..jobs.job_repository import JobRepository
from .cost_estimator import max_jobs_per_run
from .scoring_prompt import parse_result, request_params, system_blocks

PARALLEL_CALLS = 4


class ScoringService:
    def __init__(self, jobs: JobRepository, llm: LlmClient):
        self.jobs, self.llm = jobs, llm

    def pick(self, profile: dict, limit: int | None = None) -> list[Job]:
        return self.jobs.queued_for_scoring(limit or max_jobs_per_run(profile))

    def score_one(self, job_id: str, profile: dict) -> dict:
        """Rate a single job now (the 'Rate this job' button). Returns the result or {"error"}."""
        job = self.jobs.get(job_id)
        message = self.llm.create(request_params(job, profile, system_blocks(profile)))
        self.llm.record(message, "score")
        result = parse_result(message)
        self._save(job, result)
        return result

    def score_queued(self, profile: dict, limit: int | None = None, log=print):
        jobs = self.pick(profile, limit)
        if not jobs:
            log("  nothing queued for scoring")
            return
        system = system_blocks(profile)
        total = 0.0

        def call(job: Job):
            return self.llm.create(request_params(job, profile, system))

        def handle(job: Job, message):
            nonlocal total
            total += self.llm.record(message, "score")
            result = parse_result(message)
            self._save(job, result)
            log(f"  [{result.get('score', '--'):>3}] {result.get('verdict', result.get('error')):<6} "
                f"{job.title[:55]} @ {(job.company or '')[:25]}")

        first, rest = jobs[0], jobs[1:]
        try:
            handle(first, call(first))
        except anthropic.AuthenticationError:
            raise SystemExit("Anthropic API key missing/invalid - set it in Settings or ANTHROPIC_API_KEY.")
        with ThreadPoolExecutor(max_workers=PARALLEL_CALLS) as pool:
            futures = {pool.submit(call, job): job for job in rest}
            for future in as_completed(futures):
                job = futures[future]
                try:
                    handle(job, future.result())  # results are handled here, on this thread's DB connection
                except anthropic.RateLimitError:
                    log(f"  rate limited, left queued: {job.title[:60]}")
                except anthropic.APIStatusError as e:
                    log(f"  API error {e.status_code}, left queued: {job.title[:60]}")
                except anthropic.APIConnectionError:
                    log(f"  network error, left queued: {job.title[:60]}")
        log(f"  scored {len(jobs)} jobs, cost ~${total:.4f}")

    def _save(self, job: Job, result: dict):
        self.jobs.save(job, *job.record_score(result))
