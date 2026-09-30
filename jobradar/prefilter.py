"""Free, deterministic filtering. Typically removes 90%+ of fetched jobs before a
single token is spent. Rules only reject on *clear* evidence; anything ambiguous
is left for Claude."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

PER_YEAR = {"hour": 2080, "day": 260, "week": 52, "month": 12, "year": 1}


def annual(amount: float | None, per: str) -> float | None:
    return None if amount is None else amount * PER_YEAR.get(per or "year", 1)


def to_rate_currency(amount: float | None, currency: str, rate: dict) -> float | None:
    """Convert a posted salary into the currency of your rate, using rate.fx_to_rate_currency.
    Returns None when the conversion is unknown (the job is then left for Claude to judge)."""
    if amount is None:
        return None
    mine = (rate.get("currency") or "USD").upper()
    cur = (currency or "").upper()
    if cur == mine:
        return amount
    fx = {k.upper(): v for k, v in (rate.get("fx_to_rate_currency") or {}).items()}
    return amount * fx[cur] if cur in fx else None


def _has(text: str, word: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(word.lower())}(?![a-z0-9])", text) is not None


# Locations that limit a remote job to other countries ("Remote (US)", "Remote - Europe").
# "US" is matched case-sensitively so words like "join us" don't count.
OTHER_REGIONS = re.compile(r"\bU\.?S\.?A?\b|\bUK\b|\bEU\b|\bEMEA\b|\bLATAM\b|\b(?:EST|PST|CST)\b")
OTHER_REGIONS_WORDS = ["united states", "north america", "northern america", "americas", "canada", "europe",
                       "european", "united kingdom", "latin america", "us time zones", "us timezones"]
GENERIC_LOCATION_WORDS = {"remote"}  # says nothing about *where* you may work from


def other_region(location: str, allowed: list[str]) -> str | None:
    """The other-country restriction named in a remote job's location, unless the location
    also names somewhere you can work from (e.g. "Europe, APAC" is fine)."""
    low = location.lower()
    if any(_has(low, a) for a in allowed if a not in GENERIC_LOCATION_WORDS):
        return None
    m = OTHER_REGIONS.search(location)
    if m:
        return m.group(0)
    return next((w for w in OTHER_REGIONS_WORDS if _has(low, w)), None)


# "PHP 25K", "Php 30,000", "25k PHP" are peso amounts, not the PHP language.
# An amount is 3+ digits, has a thousands comma, or ends in k - so "PHP 8" / "PHP7" stay the language.
PESO = re.compile(r"(?i)\bphp\s?(?:\d+(?:\.\d+)?\s?k\b|\d{1,3}(?:,\d{3})+|\d{3,})|"
                  r"\b(?:\d{1,3}(?:,\d{3})+|\d{3,}|\d+(?:\.\d+)?\s?k)\s?php\b")


def no_pesos(text: str) -> str:
    return PESO.sub(" ", text or "")


def keyword_score(row, profile: dict) -> tuple[float, list[str]]:
    skills = profile.get("skills") or {}
    title = no_pesos(row["title"]).lower()
    body = " ".join([title, " ".join(json.loads(row["tags"] or "[]")), no_pesos(row["description"])]).lower()
    score, hits = 0.0, []
    for weight, key in ((3, "primary"), (1, "secondary")):
        for s in skills.get(key) or []:
            if _has(body, s):
                # A skill in the title is a much stronger signal than one buried in the text.
                score += weight * (2 if _has(title, s) else 1)
                hits.append(s)
    return score, hits


def check(row, profile: dict) -> tuple[str | None, float]:
    """Returns (reject_reason or None, keyword_score)."""
    f = profile.get("filters") or {}
    ws = profile.get("work_setup") or {}
    rate = profile.get("rate") or {}
    title = no_pesos(row["title"]).lower()
    loc = (row["location"] or "").lower()

    inc = f.get("title_include") or []
    if inc and not any(_has(title, w) for w in inc):
        return "title not in include list", 0
    for w in f.get("title_exclude") or []:
        if _has(title, w.strip()):
            return f"title excluded: {w.strip()}", 0

    max_age = f.get("max_age_days")
    if max_age and row["posted_at"]:
        if datetime.fromisoformat(row["posted_at"]) < datetime.now(timezone.utc) - timedelta(days=max_age):
            return f"older than {max_age} days", 0

    # --- work type: remote / hybrid / onsite ---
    accepted = set(ws.get("work_types") or ["remote", "hybrid", "onsite"])
    wt = row["work_type"] or ""
    if wt and wt not in accepted:
        return f"work type {wt} not accepted", 0
    cities = [c.lower() for c in ws.get("onsite_locations") or []]
    if wt in ("hybrid", "onsite"):
        if cities and not any(c in loc for c in cities):
            return f"{wt} outside your cities: {row['location'][:50]}", 0
    else:  # remote or unknown
        for w in ws.get("reject_locations") or []:
            if w.lower() in loc:
                return f"location excluded: {w}", 0
        allowed = [a.lower() for a in ws.get("allowed_locations") or []]
        if accepted & {"hybrid", "onsite"}:
            allowed += cities
        if ws.get("strict_location") and loc.strip() and allowed and not any(_has(loc, a) for a in allowed):
            return f"location not allowed: {row['location'][:60]}", 0
        region = ws.get("strict_location") and allowed and other_region(row["location"] or "", allowed)
        if region:
            return f"only for applicants in {region}: {row['location'][:50]}", 0

    # --- pay: only reject when the posted max is clearly below your minimum ---
    if rate.get("minimum") and row["salary_max"]:
        theirs = annual(to_rate_currency(row["salary_max"], row["currency"], rate), row["salary_period"])
        mine = annual(rate["minimum"], rate.get("per", "month"))
        if theirs and mine and theirs < mine:
            return f"pays below minimum ({row['salary_max']:.0f} {row['currency']}/{row['salary_period']})", 0

    score, _ = keyword_score(row, profile)
    if score < (f.get("min_keyword_score") or 0):
        return f"keyword score {score:g} below threshold", score
    return None, score


def run(db, profile: dict, stages: tuple[str, ...] = ("new",)) -> tuple[int, int]:
    passed = rejected = 0
    marks = ",".join("?" * len(stages))
    for row in db.rows(f"stage IN ({marks})", stages):
        reason, score = check(row, profile)
        if reason:
            db.update(row["id"], stage="rejected", reject_reason=reason, kw_score=score)
            rejected += 1
        else:
            db.update(row["id"], stage="queued", reject_reason=None, kw_score=score)
            passed += 1
    return passed, rejected
