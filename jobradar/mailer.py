"""IMAP (read alerts + replies) and SMTP (send applications). Credentials come from .env.
The mailbox is opened read-only and messages are fetched with BODY.PEEK, so nothing
is marked as read or changed in your inbox."""

from __future__ import annotations

import email
import email.policy
import imaplib
import mimetypes
import os
import re
import smtplib
from contextlib import contextmanager
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path


class MailError(Exception):
    pass


def imap_configured() -> bool:
    return bool(os.environ.get("IMAP_USER") and os.environ.get("IMAP_PASSWORD"))


def smtp_configured() -> bool:
    return bool((os.environ.get("SMTP_USER") or os.environ.get("IMAP_USER"))
                and (os.environ.get("SMTP_PASSWORD") or os.environ.get("IMAP_PASSWORD")))


def my_address() -> str:
    return os.environ.get("SMTP_USER") or os.environ.get("IMAP_USER") or ""


@contextmanager
def imap():
    if not imap_configured():
        raise MailError("Mailbox not configured - add IMAP settings on the Settings page.")
    try:
        m = imaplib.IMAP4_SSL(os.environ.get("IMAP_HOST", "imap.gmail.com"), int(os.environ.get("IMAP_PORT", 993)))
        m.login(os.environ["IMAP_USER"], os.environ["IMAP_PASSWORD"])
    except (imaplib.IMAP4.error, OSError) as e:
        raise MailError(f"IMAP login failed: {e}") from e
    try:
        m.select(f'"{os.environ.get("IMAP_FOLDER", "INBOX")}"', readonly=True)
        yield m
    finally:
        try:
            m.logout()
        except Exception:
            pass


def imap_date(dt: datetime) -> str:
    return dt.strftime("%d-%b-%Y")


def quote(term: str) -> str:
    """IMAP search strings: ASCII only, no quotes/backslashes."""
    return '"' + re.sub(r'["\\]', "", term.encode("ascii", "ignore").decode()).strip() + '"'


def search(m, criteria: str) -> list[bytes]:
    typ, data = m.search(None, criteria)
    return data[0].split() if typ == "OK" and data and data[0] else []


def fetch(m, num: bytes) -> EmailMessage | None:
    typ, data = m.fetch(num, "(BODY.PEEK[])")
    if typ != "OK" or not data or not isinstance(data[0], tuple):
        return None
    return email.message_from_bytes(data[0][1], policy=email.policy.default)


def message_id(msg: EmailMessage) -> str:
    mid = (msg.get("Message-ID") or "").strip()
    return mid or f"<nomid-{hash((msg.get('From'), msg.get('Date'), msg.get('Subject')))}>"


def message_date(msg: EmailMessage) -> datetime | None:
    try:
        return parsedate_to_datetime(msg.get("Date"))
    except (TypeError, ValueError):
        return None


def bodies(msg: EmailMessage) -> tuple[str, str]:
    """(html, plain text) of a message; either may be empty."""
    html_part = msg.get_body(preferencelist=("html",))
    text_part = msg.get_body(preferencelist=("plain",))
    get = lambda p: p.get_content() if p is not None else ""
    try:
        return get(html_part), get(text_part)
    except (LookupError, UnicodeDecodeError):
        return "", ""


class _Text(HTMLParser):
    """HTML -> readable text. Links become [text](Ln) with the real URL kept aside, so
    tracking URLs (often 300+ chars each) don't cost tokens."""
    BLOCK = {"br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "table", "section"}
    JUNK = re.compile(r"(?i)unsubscribe|privacy|help|settings|preferences|terms|manage|view in browser|"
                      r"download|app store|google play|feedback|copyright")

    def __init__(self, keep_links: bool):
        super().__init__(convert_charrefs=True)
        self.keep_links, self.out, self.links = keep_links, [], []
        self._href, self._buf, self._skip = None, [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "head", "title"):
            self._skip += 1
        elif tag == "a":
            self._href, self._buf = dict(attrs).get("href"), []
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script", "head", "title"):
            self._skip = max(0, self._skip - 1)
        elif tag == "a" and self._href is not None:
            text = " ".join("".join(self._buf).split())
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
        (self._buf if self._href is not None else self.out).append(data)


def html_to_text(html_src: str, keep_links: bool = False) -> tuple[str, list[str]]:
    p = _Text(keep_links)
    p.feed(html_src)
    text = re.sub(r"[ \t ‌​]+", " ", "".join(p.out))
    text = re.sub(r"\s*\n\s*", "\n", text).strip()
    return text, p.links


def plain_with_links(text: str) -> tuple[str, list[str]]:
    links: list[str] = []

    def sub(m):
        links.append(m.group(0))
        return f"(L{len(links)})"
    return re.sub(r"https?://\S+", sub, text), links


def readable(msg: EmailMessage, keep_links: bool = False) -> tuple[str, list[str]]:
    html_src, text = bodies(msg)
    if html_src:
        return html_to_text(html_src, keep_links)
    return plain_with_links(text) if keep_links else (text, [])


def send(to: str, subject: str, body: str, attachment: Path | None = None) -> str:
    """Send one email. Returns its Message-ID (stored so replies can be matched for free)."""
    if not smtp_configured():
        raise MailError("Sending not configured - add SMTP settings on the Settings page.")
    user = os.environ.get("SMTP_USER") or os.environ["IMAP_USER"]
    pw = os.environ.get("SMTP_PASSWORD") or os.environ["IMAP_PASSWORD"]
    msg = EmailMessage()
    msg["From"] = formataddr((os.environ.get("FROM_NAME", ""), user))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=user.split("@")[-1])
    msg.set_content(body)
    if attachment and attachment.exists():
        ctype = mimetypes.guess_type(attachment.name)[0] or "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        msg.add_attachment(attachment.read_bytes(), maintype=maintype, subtype=subtype, filename=attachment.name)
    host, port = os.environ.get("SMTP_HOST", "smtp.gmail.com"), int(os.environ.get("SMTP_PORT", 465))
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30) as s:
                s.login(user, pw)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls()
                s.login(user, pw)
                s.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        raise MailError(f"Sending failed: {e}") from e
    return msg["Message-ID"]
