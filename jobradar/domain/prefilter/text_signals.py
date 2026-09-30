"""Text signals the free filter reads: peso amounts vs the PHP language, other-country restrictions."""

from __future__ import annotations

import re

from ...shared.utils.text_utils import has_word

# "PHP 25K", "Php 30,000", "25k PHP" are peso amounts, not the PHP language.
# An amount is 3+ digits, has a thousands comma, or ends in k - so "PHP 8" / "PHP7" stay the language.
PESO = re.compile(r"(?i)\bphp\s?(?:\d+(?:\.\d+)?\s?k\b|\d{1,3}(?:,\d{3})+|\d{3,})|"
                  r"\b(?:\d{1,3}(?:,\d{3})+|\d{3,}|\d+(?:\.\d+)?\s?k)\s?php\b")

# Locations that limit a remote job to other countries ("Remote (US)", "Remote - Europe").
# "US" is matched case-sensitively so words like "join us" don't count.
OTHER_REGIONS = re.compile(r"\bU\.?S\.?A?\b|\bUK\b|\bEU\b|\bEMEA\b|\bLATAM\b|\b(?:EST|PST|CST)\b")
OTHER_REGIONS_WORDS = ["united states", "north america", "northern america", "americas", "canada", "europe",
                       "european", "united kingdom", "latin america", "us time zones", "us timezones"]
GENERIC_LOCATION_WORDS = {"remote"}  # says nothing about *where* you may work from


def without_pesos(text: str) -> str:
    return PESO.sub(" ", text or "")


def other_region(location: str, allowed: list[str]) -> str | None:
    """The other-country restriction named in a remote job's location, unless the location
    also names somewhere you can work from (e.g. "Europe, APAC" is fine)."""
    lowered = location.lower()
    if any(has_word(lowered, place) for place in allowed if place not in GENERIC_LOCATION_WORDS):
        return None
    match = OTHER_REGIONS.search(location)
    if match:
        return match.group(0)
    return next((word for word in OTHER_REGIONS_WORDS if has_word(lowered, word)), None)
