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
from pathlib import Path
from typing import Iterator


class MailError(Exception):
    pass


def imap_date(dt: datetime) -> str:
    return dt.strftime("%d-%b-%Y")


def quote(term: str) -> str:
    """IMAP search strings: ASCII only, no quotes/backslashes."""
    return '"' + re.sub(r'["\\]', "", term.encode("ascii", "ignore").decode()).strip() + '"'


def message_id(message: EmailMessage) -> str:
    mid = (message.get("Message-ID") or "").strip()
    return mid or f"<nomid-{hash((message.get('From'), message.get('Date'), message.get('Subject')))}>"


def message_date(message: EmailMessage) -> datetime | None:
    try:
        return parsedate_to_datetime(message.get("Date"))
    except (TypeError, ValueError):
        return None


class Mailbox:
    """An open, read-only IMAP folder."""

    def __init__(self, imap: imaplib.IMAP4):
        self.imap = imap

    def search(self, criteria: str) -> list[bytes]:
        status, data = self.imap.search(None, criteria)
        return data[0].split() if status == "OK" and data and data[0] else []

    def fetch(self, number: bytes) -> EmailMessage | None:
        status, data = self.imap.fetch(number, "(BODY.PEEK[])")
        if status != "OK" or not data or not isinstance(data[0], tuple):
            return None
        return email.message_from_bytes(data[0][1], policy=email.policy.default)


class MailClient:
    @staticmethod
    def imap_configured() -> bool:
        return bool(os.environ.get("IMAP_USER") and os.environ.get("IMAP_PASSWORD"))

    @staticmethod
    def smtp_configured() -> bool:
        return bool((os.environ.get("SMTP_USER") or os.environ.get("IMAP_USER"))
                    and (os.environ.get("SMTP_PASSWORD") or os.environ.get("IMAP_PASSWORD")))

    @staticmethod
    def my_address() -> str:
        return os.environ.get("SMTP_USER") or os.environ.get("IMAP_USER") or ""

    @contextmanager
    def inbox(self) -> Iterator[Mailbox]:
        if not self.imap_configured():
            raise MailError("Mailbox not configured - add IMAP settings on the Settings page.")
        try:
            imap = imaplib.IMAP4_SSL(os.environ.get("IMAP_HOST", "imap.gmail.com"), int(os.environ.get("IMAP_PORT", 993)))
            imap.login(os.environ["IMAP_USER"], os.environ["IMAP_PASSWORD"])
        except (imaplib.IMAP4.error, OSError) as e:
            raise MailError(f"IMAP login failed: {e}") from e
        try:
            imap.select(f'"{os.environ.get("IMAP_FOLDER", "INBOX")}"', readonly=True)
            yield Mailbox(imap)
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def send(self, to: str, subject: str, body: str, attachment: Path | None = None) -> str:
        """Send one email. Returns its Message-ID (stored so replies can be matched for free)."""
        if not self.smtp_configured():
            raise MailError("Sending not configured - add SMTP settings on the Settings page.")
        user = os.environ.get("SMTP_USER") or os.environ["IMAP_USER"]
        password = os.environ.get("SMTP_PASSWORD") or os.environ["IMAP_PASSWORD"]
        message = self._compose(user, to, subject, body, attachment)
        host, port = os.environ.get("SMTP_HOST", "smtp.gmail.com"), int(os.environ.get("SMTP_PORT", 465))
        try:
            if port == 465:
                with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
                    smtp.login(user, password)
                    smtp.send_message(message)
            else:
                with smtplib.SMTP(host, port, timeout=30) as smtp:
                    smtp.starttls()
                    smtp.login(user, password)
                    smtp.send_message(message)
        except (smtplib.SMTPException, OSError) as e:
            raise MailError(f"Sending failed: {e}") from e
        return message["Message-ID"]

    @staticmethod
    def _compose(user: str, to: str, subject: str, body: str, attachment: Path | None) -> EmailMessage:
        message = EmailMessage()
        message["From"] = formataddr((os.environ.get("FROM_NAME", ""), user))
        message["To"] = to
        message["Subject"] = subject
        message["Message-ID"] = make_msgid(domain=user.split("@")[-1])
        message.set_content(body)
        if attachment and attachment.exists():
            content_type = mimetypes.guess_type(attachment.name)[0] or "application/octet-stream"
            maintype, subtype = content_type.split("/", 1)
            message.add_attachment(attachment.read_bytes(), maintype=maintype, subtype=subtype,
                                   filename=attachment.name)
        return message
