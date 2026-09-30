"""The scoring request - the main token spender. One small structured-output call per job:
- the profile + rubric is a fixed system prompt, marked for prompt caching
- the job is sent as compact plain text, description capped
- the answer is a strict JSON schema, so output is short and always parseable"""

from __future__ import annotations

import copy

import yaml

from ...lib.llm_client import LlmClient, LLMError
from ..jobs.job import Job
from ..jobs.job_prompt_mapper import to_prompt_text

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
FILTER_ONLY_KEYS = ["strict_location", "allowed_locations", "reject_locations"]


def system_blocks(profile: dict) -> list[dict]:
    # Deterministic serialization -> byte-identical prefix every run -> cache hits.
    subset = copy.deepcopy({key: profile[key] for key in PROFILE_KEYS if key in profile})
    for key in FILTER_ONLY_KEYS:
        subset.get("work_setup", {}).pop(key, None)
    text = RUBRIC + yaml.safe_dump(subset, sort_keys=True, allow_unicode=True)
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def request_params(job: Job, profile: dict, system) -> dict:
    return LlmClient.params(profile, system, to_prompt_text(job, profile), SCHEMA)


def parse_result(message) -> dict:
    """Claude's assessment, or {"error": ...} - a failed rating is stored, not raised."""
    try:
        return LlmClient.parse(message)
    except LLMError as e:
        return {"error": str(e)}
