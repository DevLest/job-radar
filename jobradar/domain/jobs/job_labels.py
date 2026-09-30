"""Plain-language words for Claude's enum answers, and how each maps onto a 0-100 meter."""

VERDICT_WORDS = {"apply": "Great match", "maybe": "Could work", "skip": "Weak match", "error": "Couldn't rate"}

FIT_WORDS = {
    "rate_fit": {"meets_target": "Pays your target", "meets_minimum": "Meets your minimum",
                 "below_minimum": "Below your minimum", "not_stated": "Pay not listed"},
    "setup_fit": {"fits": "Work setup fits", "unclear": "Work setup unclear", "conflicts": "Work setup doesn't fit"},
    "seniority_fit": {"fits": "Right level for you", "under_qualified": "Asks for more experience",
                      "over_qualified": "You may be overqualified", "unclear": "Level unclear"},
}
GOOD_FITS = {"meets_target", "meets_minimum", "fits"}
BAD_FITS = {"below_minimum", "conflicts"}

METER_PERCENT = {
    "rate_fit": {"meets_target": 100, "meets_minimum": 70, "not_stated": 50, "below_minimum": 15},
    "setup_fit": {"fits": 100, "unclear": 50, "conflicts": 10},
    "seniority_fit": {"fits": 100, "unclear": 50, "over_qualified": 60, "under_qualified": 30},
}


def verdict_word(verdict: str | None) -> str:
    return VERDICT_WORDS.get(verdict, "")


def fit_word(kind: str, value: str) -> str:
    return FIT_WORDS[kind].get(value, value)


def fit_tone(value: str) -> str:
    return "ok" if value in GOOD_FITS else ("bad" if value in BAD_FITS else "")


def meter_tone(percent: int) -> str:
    return "green" if percent >= 70 else ("amber" if percent >= 40 else "red")
