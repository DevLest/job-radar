from __future__ import annotations

from ...lib.llm_client import model_of, prices

# Typical scoring call: ~1100 fresh input + ~650 cached input + ~600 output (incl. thinking) tokens.
FRESH_INPUT_TOKENS, CACHED_INPUT_TOKENS, OUTPUT_TOKENS = 1100, 650, 600
DEFAULT_MAX_JOBS_PER_RUN = 40


def estimate(profile: dict, n_jobs: int, batch: bool = False) -> float:
    """Rough spend for scoring n jobs, without calling the API."""
    price_in, price_out, price_cache = prices(model_of(profile))
    per_job = (FRESH_INPUT_TOKENS * price_in + CACHED_INPUT_TOKENS * price_cache + OUTPUT_TOKENS * price_out) / 1e6
    return per_job * n_jobs * (0.5 if batch else 1)


def max_jobs_per_run(profile: dict) -> int:
    return (profile.get("claude") or {}).get("max_jobs_per_run", DEFAULT_MAX_JOBS_PER_RUN)
