"""Parsing helpers shared by the sources: salaries, work types, numbers, search-result merging."""

from __future__ import annotations

import re

from ..domain.jobs.job_posting import JobPosting

SNIPPET_NOTE = "\n\n(From {site} search results - only a snippet is available; open the link for the full posting.)"
_WORK_TYPE_PATTERNS = (("hybrid", r"hybrid"), ("onsite", r"on-?site|in[- ]office"), ("remote", r"remote"))
_PERIOD_PATTERNS = (("hour", r"hour|/hr|\bhr\b"), ("day", r"(?:per|a|/)\s*day\b|daily"), ("week", r"week"),
                    ("year", r"year|annual|/yr"))


def work_type_from(text: str | None) -> str:
    """Single clear work type, or "" when unknown or mixed (e.g. "Onsite or Remote") -
    mixed postings are left for Claude instead of being filtered out."""
    lowered = (text or "").lower()
    found = {name for name, pattern in _WORK_TYPE_PATTERNS if re.search(pattern, lowered)}
    return found.pop() if len(found) == 1 else ""


def to_number(value) -> float | None:
    try:
        number = float(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def parse_salary(text: str, default_currency: str = "PHP") -> tuple[float | None, float | None, str, str]:
    """'₱40,000 – ₱60,000 per month', '$7 - $10 per hour', 'Up to Php112k' -> (min, max, period, currency).
    Returns (None, None, ...) when no amount is found."""
    lowered = (text or "").lower()
    amounts = [float(number.replace(",", "")) * (1000 if thousands else 1)
               for number, thousands in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*(k\b)?", lowered) if number.replace(",", "")]
    amounts = [amount for amount in amounts if amount > 0]
    if not amounts:
        return None, None, "month", ""
    currency = ("USD" if re.search(r"\$|usd", lowered) else "PHP" if re.search(r"₱|php|peso", lowered)
                else default_currency)
    period = next((name for name, pattern in _PERIOD_PATTERNS if re.search(pattern, lowered)), "month")
    low, high = min(amounts[:2]), max(amounts[:2])
    if re.search(r"up to|max", lowered):
        low = None
    return low, high, period, currency


def keep_result(results: dict, term: str, posting: JobPosting):
    """Adds a search result, remembering which search terms found it. The Philippine sites only
    show a snippet, so the site's own match on e.g. "laravel" (it searched the full posting) counts
    as that skill. "php" is not credited: on these sites it is also the peso currency code."""
    posting = results.setdefault(posting.ext_id, posting)
    if term and term.lower() != "php" and term not in posting.tags:
        posting.tags.append(term)
