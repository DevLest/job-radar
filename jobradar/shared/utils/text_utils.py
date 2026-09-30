from __future__ import annotations

import html
import re


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "- ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def has_word(text: str, word: str) -> bool:
    """Whole-word match that also works for words like 'c++' or 'node.js'."""
    return re.search(rf"(?<![a-z0-9]){re.escape(word.lower())}(?![a-z0-9])", text) is not None


def unique(items) -> list:
    return list(dict.fromkeys(items))
