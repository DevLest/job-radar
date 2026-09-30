import hashlib
import re


def short_hash(text: str, length: int = 16) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:length]


def fingerprint(company: str, title: str) -> str:
    """Same role posted on several boards -> same fingerprint -> scored once."""
    def normalize(value):
        return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()
    return short_hash(f"{normalize(company)}|{normalize(title)}")
