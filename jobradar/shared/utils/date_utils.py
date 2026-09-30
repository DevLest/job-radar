from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def to_iso(value) -> str | None:
    """Epoch seconds/ms, ISO-8601 or RFC-822 (RSS) -> ISO-8601 UTC, or None."""
    if value in (None, "", 0):
        return None
    try:
        if isinstance(value, (int, float)):
            seconds = value / 1000 if value > 10**11 else value
            return datetime.fromtimestamp(seconds, timezone.utc).isoformat()
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        try:
            return parsedate_to_datetime(str(value)).astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            return None


def time_ago(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso[:10]
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    days = (datetime.now(timezone.utc) - dt).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 30:
        return f"{days} days ago"
    return dt.strftime("%d %b %Y")
