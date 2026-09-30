"""Free, deterministic filtering rules. Each rule rejects only on *clear* evidence and returns the
reason, or None; anything ambiguous is left for Claude. Add a rule by appending to RULES."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

from ...shared.constants.work_types import WORK_TYPES
from ...shared.utils.text_utils import has_word
from ..jobs.job import Job
from .pay_conversion import annual, to_rate_currency
from .text_signals import other_region, without_pesos

Rule = Callable[[Job, dict], "str | None"]
SKILL_WEIGHTS = ((3, "primary"), (1, "secondary"))
TITLE_BONUS = 2


def title_rule(job: Job, profile: dict) -> str | None:
    filters = profile.get("filters") or {}
    title = without_pesos(job.title).lower()
    include = filters.get("title_include") or []
    if include and not any(has_word(title, word) for word in include):
        return "title not in include list"
    for word in filters.get("title_exclude") or []:
        if has_word(title, word.strip()):
            return f"title excluded: {word.strip()}"
    return None


def age_rule(job: Job, profile: dict) -> str | None:
    max_age = (profile.get("filters") or {}).get("max_age_days")
    if max_age and job.posted_at:
        if datetime.fromisoformat(job.posted_at) < datetime.now(timezone.utc) - timedelta(days=max_age):
            return f"older than {max_age} days"
    return None


def work_setup_rule(job: Job, profile: dict) -> str | None:
    work_setup = profile.get("work_setup") or {}
    accepted = set(work_setup.get("work_types") or WORK_TYPES)
    work_type = job.work_type or ""
    if work_type and work_type not in accepted:
        return f"work type {work_type} not accepted"
    cities = [city.lower() for city in work_setup.get("onsite_locations") or []]
    location = (job.location or "").lower()
    if work_type in ("hybrid", "onsite"):
        if cities and not any(city in location for city in cities):
            return f"{work_type} outside your cities: {job.location[:50]}"
        return None
    return _remote_location(job, work_setup, accepted, cities, location)


def _remote_location(job: Job, work_setup: dict, accepted: set, cities: list[str], location: str) -> str | None:
    """Remote or unknown work type: is the job open to where you live?"""
    for word in work_setup.get("reject_locations") or []:
        if word.lower() in location:
            return f"location excluded: {word}"
    allowed = [place.lower() for place in work_setup.get("allowed_locations") or []]
    if accepted & {"hybrid", "onsite"}:
        allowed += cities
    strict = work_setup.get("strict_location")
    if strict and location.strip() and allowed and not any(has_word(location, place) for place in allowed):
        return f"location not allowed: {job.location[:60]}"
    region = strict and allowed and other_region(job.location or "", allowed)
    if region:
        return f"only for applicants in {region}: {job.location[:50]}"
    return None


def pay_rule(job: Job, profile: dict) -> str | None:
    """Only rejects when the posted maximum is clearly below your minimum."""
    rate = profile.get("rate") or {}
    if rate.get("minimum") and job.salary_max:
        theirs = annual(to_rate_currency(job.salary_max, job.currency, rate), job.salary_period)
        mine = annual(rate["minimum"], rate.get("per", "month"))
        if theirs and mine and theirs < mine:
            return f"pays below minimum ({job.salary_max:.0f} {job.currency}/{job.salary_period})"
    return None


RULES: list[Rule] = [title_rule, age_rule, work_setup_rule, pay_rule]


def keyword_score(job: Job, profile: dict) -> tuple[float, list[str]]:
    skills = profile.get("skills") or {}
    title = without_pesos(job.title).lower()
    body = " ".join([title, " ".join(job.tags), without_pesos(job.description)]).lower()
    score, hits = 0.0, []
    for weight, key in SKILL_WEIGHTS:
        for skill in skills.get(key) or []:
            if has_word(body, skill):
                # A skill in the title is a much stronger signal than one buried in the text.
                score += weight * (TITLE_BONUS if has_word(title, skill) else 1)
                hits.append(skill)
    return score, hits


def check(job: Job, profile: dict) -> tuple[str | None, float]:
    """(reject_reason or None, keyword_score)."""
    for rule in RULES:
        reason = rule(job, profile)
        if reason:
            return reason, 0
    score, _ = keyword_score(job, profile)
    if score < ((profile.get("filters") or {}).get("min_keyword_score") or 0):
        return f"keyword score {score:g} below threshold", score
    return None, score
