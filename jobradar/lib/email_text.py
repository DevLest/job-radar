"""Email bodies -> compact text. Links become [text](Ln) with the real URL kept aside, so
tracking URLs (often 300+ chars each) don't cost tokens."""

from __future__ import annotations

import re
from email.message import EmailMessage
from html.parser import HTMLParser


class _HtmlText(HTMLParser):
    BLOCK = {"br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "table", "section"}
    SKIP = ("style", "script", "head", "title")
    JUNK = re.compile(r"(?i)unsubscribe|privacy|help|settings|preferences|terms|manage|view in browser|"
                      r"download|app store|google play|feedback|copyright")

    def __init__(self, keep_links: bool):
        super().__init__(convert_charrefs=True)
        self.keep_links, self.out, self.links = keep_links, [], []
        self._href, self._buffer, self._skip = None, [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif tag == "a":
            self._href, self._buffer = dict(attrs).get("href"), []
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag == "a" and self._href is not None:
            text = " ".join("".join(self._buffer).split())
            if text and self.keep_links and self._href.startswith("http") and not self.JUNK.search(text):
                self.links.append(self._href)
                self.out.append(f" [{text}](L{len(self.links)}) ")
            elif text:
                self.out.append(f" {text} ")
            self._href = None
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if self._skip:
            return
        (self._buffer if self._href is not None else self.out).append(data)


def html_to_text(html_source: str, keep_links: bool = False) -> tuple[str, list[str]]:
    parser = _HtmlText(keep_links)
    parser.feed(html_source)
    text = re.sub(r"[ \t ‌​]+", " ", "".join(parser.out))
    text = re.sub(r"\s*\n\s*", "\n", text).strip()
    return text, parser.links


def plain_with_links(text: str) -> tuple[str, list[str]]:
    links: list[str] = []

    def replace(match):
        links.append(match.group(0))
        return f"(L{len(links)})"
    return re.sub(r"https?://\S+", replace, text), links


def bodies(message: EmailMessage) -> tuple[str, str]:
    """(html, plain text) of a message; either may be empty."""
    html_part = message.get_body(preferencelist=("html",))
    text_part = message.get_body(preferencelist=("plain",))

    def content(part):
        return part.get_content() if part is not None else ""
    try:
        return content(html_part), content(text_part)
    except (LookupError, UnicodeDecodeError):
        return "", ""


def readable(message: EmailMessage, keep_links: bool = False) -> tuple[str, list[str]]:
    html_source, text = bodies(message)
    if html_source:
        return html_to_text(html_source, keep_links)
    return plain_with_links(text) if keep_links else (text, [])
