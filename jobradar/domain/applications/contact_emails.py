from __future__ import annotations

import re

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
IMAGE_SUFFIXES = (".png", ".jpg")


def emails_in(text: str | None) -> list[str]:
    """Email addresses mentioned in a job posting (image file names excluded)."""
    found = EMAIL_RE.findall(text or "")
    return [e.rstrip(".") for e in dict.fromkeys(found) if not e.lower().endswith(IMAGE_SUFFIXES)]


def is_email(value: str | None) -> bool:
    return bool(value and EMAIL_RE.fullmatch(value.strip()))
