"""Job scoring - the main token spender. One small structured-output call per job:
- the profile + rubric is a fixed system prompt, marked for prompt caching
- the job is sent as compact plain text, description capped
- the answer is a strict JSON schema, so output is short and always parseable
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic
import yaml

from . import llm
from .db import now
from .llm import cost

SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "description": "Overall fit 0-100"},
        "verdict": {"type": "string", "enum": ["apply", "maybe", "skip"]},
        "skills_match": {"type": "integer", "description": "0-100"},
        "rate_fit": {"type": "string", "enum": ["meets_target", "meets_minimum", "below_minimum", "not_stated"]},
        "setup_fit": {"type": "string", "enum": ["fits", "unclear", "conflicts"]},
        "seniority_fit": {"type": "string", "enum": ["fits", "under_qualified", "over_qualified", "unclear"]},
        "matched_skills": {"type": "array", "items": {"type": "string"}},
        "missing_skills": {"type": "array", "items": {"type": "string"}},
        "red_flags": {"type": "array", "items": {"type": "string"}},
        "salary_stated": {"type": "string", "description": "Pay as stated in the post, or empty"},
        "summary": {"type": "string", "description": "One sentence, max 30 words"},
    },
    "required": ["score", "verdict", "skills_match", "rate_fit", "setup_fit", "seniority_fit",
                 "matched_skills", "missing_skills", "red_flags", "salary_stated", "summary"],
    "additionalProperties": False,
}

RUBRIC = """You screen job postings for one candidate and return a strict JSON assessment.

Scoring (score, 0-100):
- 50% skills: required skills the candidate has (primary > secondary > learning). Missing a
  "must have" skill costs far more than missing a "nice to have".
- 20% work setup: work type (remote/hybrid/onsite) must be one the candidate accepts; hybrid/onsite
  only counts if it is in one of the candidate's onsite_locations; also location eligibility,
  employment type, timezone overlap.
- 20% pay: compare stated pay to the candidate's minimum and target (convert hourly/monthly/yearly;
  1 year = 12 months = 2080 hours; convert currency with rate.fx_to_rate_currency when given).
  If pay is not stated, use "not_stated" and score this part neutral.
- 10% seniority fit.
Any deal breaker, or setup_fit "conflicts", caps the score at 30 and forces verdict "skip".
verdict: "apply" if score >= 75, "maybe" if 50-74, otherwise "skip".

Be literal: judge only what the posting says. Do not assume remote-friendly or worldwide
hiring unless stated. red_flags: vague pay, unrealistic scope, "rockstar/ninja", unpaid tests,
crypto/MLM, missing company name. Keep lists short (max 6 items each).
Some jobs come from alert emails with only a short snippet: judge what is there, keep the score
at most 80 when key facts are missing, and start the summary with "Limited info:".

CANDIDATE PROFILE:
"""

PROFILE_KEYS = ["candidate", "skills", "rate", "work_setup", "deal_breakers"]
# Pre-filter-only settings: not useful to Claude, and leaving them out keeps the cached prompt stable.
_FILTER_ONLY = ["strict_location", "allowed_locations", "reject_locations"]


def system_blocks(profile: dict) -> list[dict]:
    # Deterministic serialization -> byte-identical prefix every run -> cache hits.
    subset = copy.deepcopy({k: profile[k] for k in PROFILE_KEYS if k in profile})
    for k in _FILTER_ONLY:
        subset.get("work_setup", {}).pop(k, None)
    text = RUBRIC + yaml.safe_dump(subset, sort_keys=True, allow_unicode=True)
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def job_text(row, profile: dict) -> str:
    cap = (profile.get("claude") or {}).get("max_description_chars", 3500)
    desc = row["description"] or ""
    if len(desc) > cap:
        desc = desc[:cap] + " [truncated]"
    loc = row["location"] or "not stated"
    if len(loc) > 200:  # long country allow-lists: keep the one that matters
        home = ((profile.get("candidate") or {}).get("based_in") or "").lower()
        n = loc.count(",") + 1
        loc = f"{n} countries, {'INCLUDING' if home and home in loc.lower() else 'NOT including'} {home or 'candidate country'}"
    salary = row["salary_text"] or ""
    if row["salary_min"] or row["salary_max"]:
        salary = f"{row['salary_min'] or '?'}-{row['salary_max'] or '?'} {row['currency'] or ''} per {row['salary_period']}"
    tags = ", ".join(t for t in json.loads(row["tags"] or "[]") if t)
    work_type = row["work_type"] or {1: "remote", 0: "not remote"}.get(row["remote"], "not stated")
    return (f"TITLE: {row['title']}\nCOMPANY: {row['company'] or 'not stated'}\nLOCATION: {loc}\n"
            f"WORK TYPE: {work_type}\nEMPLOYMENT: {row['employment_type'] or 'not stated'}\n"
            f"SALARY: {salary or 'not stated'}\nTAGS: {tags or '-'}\n\nDESCRIPTION:\n{desc}")


def request_params(row, profile: dict, system) -> dict:
    return llm.params(profile, system, job_text(row, profile), SCHEMA)


def parse(msg) -> dict:
    try:
        return llm.parse(msg)
    except llm.LLMError as e:
        return {"error": str(e)}


def _save(db, row_id: str, result: dict):
    if "error" in result:
        db.update(row_id, stage="scored", verdict="error", analysis=json.dumps(result))
    else:
        db.update(row_id, stage="scored", score=result["score"], verdict=result["verdict"],
                  analysis=json.dumps(result))


def pick(db, profile: dict, limit: int | None = None):
    cap = limit or (profile.get("claude") or {}).get("max_jobs_per_run", 40)
    # Best keyword matches first, newest first - so the cap drops the weakest candidates.
    return db.rows("stage='queued' ORDER BY kw_score DESC, posted_at DESC LIMIT ?", (cap,))


def estimate(profile: dict, n_jobs: int, batch: bool = False) -> float:
    """Rough spend for n jobs without calling the API (~1100 input + ~600 output tokens per job)."""
    model = (profile.get("claude") or {}).get("model", "claude-opus-5-5")
    pin, pout, pcache = llm.PRICES.get(model, llm.PRICES["claude-opus-5-5"])
    per_job = (1100 * pin + 650 * pcache + 600 * pout) / 1e6
    return per_job * n_jobs * (0.5 if batch else 1)


# --- real-time --------------------------------------------------------------

def score_now(db, profile: dict, limit: int | None = None, workers: int = 4, log=print):
    rows = pick(db, profile, limit)
    if not rows:
        log("  nothing queued for scoring")
        return
    system = system_blocks(profile)
    total = 0.0

    def call(row):
        return llm.create(request_params(row, profile, system))

    def handle(row, msg):
        nonlocal total
        c = cost(msg.model, msg.usage, False)
        total += c
        db.log_usage(msg.model, False, msg.usage, c, "score")
        result = parse(msg)
        _save(db, row["id"], result)
        log(f"  [{result.get('score', '--'):>3}] {result.get('verdict', result.get('error')):<6} "
            f"{row['title'][:55]} @ {(row['company'] or '')[:25]}")

    # First call alone writes the prompt cache; the rest run in parallel and read it.
    first, rest = rows[0], rows[1:]
    try:
        handle(first, call(first))
    except anthropic.AuthenticationError:
        raise SystemExit("Anthropic API key missing/invalid - set it in Settings or ANTHROPIC_API_KEY.")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(call, r): r for r in rest}
        for fut in as_completed(futures):
            row = futures[fut]
            try:
                handle(row, fut.result())
            except anthropic.RateLimitError:
                log(f"  rate limited, left queued: {row['title'][:60]}")
            except anthropic.APIStatusError as e:
                log(f"  API error {e.status_code}, left queued: {row['title'][:60]}")
            except anthropic.APIConnectionError:
                log(f"  network error, left queued: {row['title'][:60]}")
    log(f"  scored {len(rows)} jobs, cost ~${total:.4f}")


# --- batch (50% cheaper, async) ----------------------------------------------

def _cid(job_id: str) -> str:
    return "j" + hashlib.sha1(job_id.encode()).hexdigest()[:24]


def submit_batch(db, profile: dict, limit: int | None = None, log=print) -> str | None:
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    rows = pick(db, profile, limit)
    if not rows:
        log("  nothing queued for scoring")
        return None
    system = system_blocks(profile)
    batch = llm.client().messages.batches.create(requests=[
        Request(custom_id=_cid(r["id"]), params=MessageCreateParamsNonStreaming(**request_params(r, profile, system)))
        for r in rows])
    db.exec("INSERT INTO batches (id, created, model) VALUES (?,?,?)",
            (batch.id, now(), (profile.get("claude") or {}).get("model", "claude-opus-5-5")))
    for r in rows:
        db.update(r["id"], stage="batched", batch_id=batch.id)
    log(f"  submitted batch {batch.id} with {len(rows)} jobs")
    return batch.id


def collect_batches(db, wait_minutes: float = 0, log=print) -> int:
    """Collect finished batches. Returns how many are still pending."""
    pending = [r["id"] for r in db.q("SELECT id FROM batches WHERE done=0")]
    if not pending:
        return 0
    client = llm.client()
    deadline = time.time() + wait_minutes * 60
    while pending:
        for bid in list(pending):
            b = client.messages.batches.retrieve(bid)
            if b.processing_status != "ended":
                continue
            by_cid = {_cid(r["id"]): r for r in db.rows("batch_id=?", (bid,))}
            total = 0.0
            for res in client.messages.batches.results(bid):
                row = by_cid.get(res.custom_id)
                if not row:
                    continue
                if res.result.type == "succeeded":
                    msg = res.result.message
                    c = cost(msg.model, msg.usage, True)
                    total += c
                    db.log_usage(msg.model, True, msg.usage, c, "score")
                    _save(db, row["id"], parse(msg))
                else:  # errored / expired / canceled -> back in the queue for next run
                    db.update(row["id"], stage="queued", batch_id=None)
            db.exec("UPDATE batches SET done=1 WHERE id=?", (bid,))
            pending.remove(bid)
            log(f"  batch {bid} collected, cost ~${total:.4f}")
        if not pending or time.time() > deadline:
            break
        log(f"  waiting on {len(pending)} batch(es)...")
        time.sleep(30)
    return len(pending)
