"""Paths, profile.yaml load/save, and .env secrets (API key, mailbox passwords).
Secrets never go into profile.yaml, because parts of the profile are sent to Claude."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CV_DIR = DATA / "cv"
PROFILE = ROOT / "profile.yaml"
EXAMPLE = ROOT / "profile.example.yaml"
ENV = ROOT / ".env"
DB_PATH = ROOT / "jobs.db"

ENV_KEYS = ["ANTHROPIC_API_KEY", "IMAP_HOST", "IMAP_PORT", "IMAP_USER", "IMAP_PASSWORD", "IMAP_FOLDER",
            "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "FROM_NAME"]
SECRET_KEYS = {"ANTHROPIC_API_KEY", "IMAP_PASSWORD", "SMTP_PASSWORD"}
ENV_DEFAULTS = {"IMAP_HOST": "imap.gmail.com", "IMAP_PORT": "993", "IMAP_FOLDER": "INBOX",
                "SMTP_HOST": "smtp.gmail.com", "SMTP_PORT": "465"}

WORK_TYPES = ["remote", "hybrid", "onsite"]

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


def load_env():
    """Load .env into os.environ (without overriding variables already set in the shell)."""
    for k, v in ENV_DEFAULTS.items():
        os.environ.setdefault(k, v)
    if not ENV.exists():
        return
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def env_values() -> dict:
    return {k: os.environ.get(k, "") for k in ENV_KEYS}


def save_env(values: dict):
    """Blank secret fields mean 'keep the current value' (the UI never shows them)."""
    current = env_values()
    for k in ENV_KEYS:
        v = (values.get(k) or "").strip()
        if k in SECRET_KEYS and not v:
            continue
        current[k] = v
    ENV.write_text("".join(f"{k}={current[k]}\n" for k in ENV_KEYS if current[k]), encoding="utf-8")
    for k, v in current.items():
        if v:
            os.environ[k] = v


def _merge_defaults(target: dict, defaults: dict):
    for k, v in defaults.items():
        if k not in target or target[k] is None:
            target[k] = v if not isinstance(v, dict) else {**v}
        elif isinstance(v, dict) and isinstance(target[k], dict):
            _merge_defaults(target[k], v)


def normalize(profile: dict) -> dict:
    ws = profile.setdefault("work_setup", {})
    if "work_types" not in ws:  # older profiles used remote: required|preferred|any
        ws["work_types"] = {"required": ["remote"], "preferred": ["remote", "hybrid"]}.get(
            ws.get("remote"), list(WORK_TYPES))
    ws.pop("remote", None)
    ws.setdefault("onsite_locations", [])
    profile.setdefault("rate", {}).setdefault("fx_to_rate_currency", {})
    _merge_defaults(profile, DEFAULTS)
    return profile


def load_profile(path: Path = PROFILE) -> dict:
    if not path.exists():
        shutil.copy(EXAMPLE, path)
    return normalize(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


def save_profile(profile: dict, path: Path = PROFILE):
    path.write_text(yaml.safe_dump(profile, sort_keys=False, allow_unicode=True, width=110), encoding="utf-8")
