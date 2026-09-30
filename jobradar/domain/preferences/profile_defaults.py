"""Defaults merged into every profile, so settings added after the first release appear."""

from ...shared.constants.work_types import WORK_TYPES

DEFAULTS = {
    # Philippine job sites, searched directly (added after the first release, so on by default).
    "sources": {"jobstreet": True, "onlinejobs": True, "linkedin": True},
    "email_alerts": {
        "enabled": True,
        "lookback_days": 7,
        # IMAP "FROM" substrings per provider. Add more if your alerts come from another address.
        "senders": {
            "linkedin": ["jobalerts-noreply@linkedin.com", "jobs-noreply@linkedin.com"],
            "indeed": ["indeed.com"],
            "jobstreet": ["jobstreet"],
            "onlinejobs": ["onlinejobs.ph"],
        },
    },
    "automation": {
        "enabled": False,
        "interval_hours": 6,
        "tasks": ["alerts", "fetch", "updates"],   # add "score" to also spend tokens automatically
        "score_mode": "batch",                      # batch | now
    },
    "applications": {
        "sender_signature": "",
        "tone": "professional, warm, concise",
    },
}

# Older profiles used work_setup.remote: required | preferred | any.
LEGACY_REMOTE = {"required": ["remote"], "preferred": ["remote", "hybrid"]}


def merge_defaults(target: dict, defaults: dict):
    for key, value in defaults.items():
        if key not in target or target[key] is None:
            target[key] = value if not isinstance(value, dict) else {**value}
        elif isinstance(value, dict) and isinstance(target[key], dict):
            merge_defaults(target[key], value)


def normalize(profile: dict) -> dict:
    work_setup = profile.setdefault("work_setup", {})
    if "work_types" not in work_setup:
        work_setup["work_types"] = LEGACY_REMOTE.get(work_setup.get("remote"), list(WORK_TYPES))
    work_setup.pop("remote", None)
    work_setup.setdefault("onsite_locations", [])
    profile.setdefault("rate", {}).setdefault("fx_to_rate_currency", {})
    merge_defaults(profile, DEFAULTS)
    return profile
