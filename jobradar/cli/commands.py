"""CLI commands that only report (stats, report, dry-run). The pipeline steps live in pipeline/."""

from __future__ import annotations

from collections import Counter

from ..container import Container
from ..domain.jobs.job_queries import TOP_MATCH
from ..domain.scoring.scoring_prompt import request_params, system_blocks
from ..lib.llm_client import prices
from ..shared.constants.paths import REPORTS_DIR

DRY_RUN_OUTPUT_TOKENS = 600  # incl. thinking
PREVIEW_CHARS = 1500


def report(c: Container, min_score: int):
    path = c.report.build(REPORTS_DIR, min_score)
    print(f"Report: {path}")
    top = c.jobs.find(TOP_MATCH, order="score DESC", limit=10)
    if top:
        print("\nTop matches to apply to:")
        for job in top:
            print(f"  {job.score:>3}  {job.title[:50]:<50} {(job.company or '')[:22]:<22} {job.url}")


def dry_run(c: Container, profile: dict, limit: int | None):
    jobs = c.scoring.pick(profile, limit)
    if not jobs:
        print("Nothing queued. Run `python run.py fetch` first.")
        return
    system = system_blocks(profile)
    params = request_params(jobs[0], profile, system)
    first = c.llm.count_tokens(params["model"], system, params["messages"][0]["content"])
    system_tokens = c.llm.count_tokens(params["model"], system, "x")
    price_in, price_out, price_cache = prices(params["model"])
    per_job = ((first - system_tokens) * price_in + system_tokens * price_cache + DRY_RUN_OUTPUT_TOKENS * price_out) / 1e6
    print(f"{len(jobs)} jobs would be scored with {params['model']}.")
    print(f"System prompt {system_tokens} tokens (cached), first job {first - system_tokens} tokens.")
    print(f"Estimated: ~${per_job:.4f}/job, ~${per_job * len(jobs):.3f} this run "
          f"(~${per_job * len(jobs) / 2:.3f} with --batch)\n")
    print("--- first job as sent ---\n" + params["messages"][0]["content"][:PREVIEW_CHARS])
    print("\n--- queue ---")
    for job in jobs:
        print(f"  kw={job.kw_score:>4g}  {job.title[:60]:<60} {(job.company or '')[:25]}")


def stats(c: Container):
    jobs = c.jobs.find()
    stages = Counter(job.stage for job in jobs)
    verdicts = Counter(job.verdict for job in jobs if job.stage == "scored")
    reasons = Counter((job.reject_reason or "").split(":")[0] for job in jobs if job.stage == "rejected")
    statuses = Counter(app.status for app in c.applications.all())
    totals = c.usage.totals()
    print("Funnel:", dict(stages))
    print("Verdicts:", dict(verdicts))
    print("Top reject reasons:", dict(reasons.most_common(6)))
    print("Applications:", dict(statuses) or "-")
    print(f"LLM calls: {totals['n']}, input {totals['i'] or 0:,} tok, output {totals['o'] or 0:,} tok, "
          f"cache reads {totals['c'] or 0:,} tok, total ~${totals['usd'] or 0:.4f}")
