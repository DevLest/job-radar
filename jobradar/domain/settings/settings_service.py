"""Connections (API key, mailbox): stored only in .env and never sent to the AI."""

from __future__ import annotations

import os

from ...lib.env_file import EnvFile
from ...lib.llm_client import LlmClient
from ...lib.mail_client import MailClient

ENV_KEYS = ["ANTHROPIC_API_KEY", "IMAP_HOST", "IMAP_PORT", "IMAP_USER", "IMAP_PASSWORD", "IMAP_FOLDER",
            "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "FROM_NAME"]
SECRET_KEYS = {"ANTHROPIC_API_KEY", "IMAP_PASSWORD", "SMTP_PASSWORD"}
ENV_DEFAULTS = {"IMAP_HOST": "imap.gmail.com", "IMAP_PORT": "993", "IMAP_FOLDER": "INBOX",
                "SMTP_HOST": "smtp.gmail.com", "SMTP_PORT": "465"}


def api_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


class SettingsService:
    def __init__(self, env: EnvFile, mail: MailClient):
        self.env, self.mail = env, mail

    def values(self) -> dict[str, str]:
        return self.env.values()

    def save(self, submitted: dict[str, str]):
        """Blank secret fields mean 'keep the current value' (the UI never shows them)."""
        current = self.env.values()
        for key in ENV_KEYS:
            value = (submitted.get(key) or "").strip()
            if key in SECRET_KEYS and not value:
                continue
            current[key] = value
        self.env.write(current)
        LlmClient.reset()

    def test_mailbox(self) -> int:
        """Number of emails in the mailbox. Raises MailError."""
        with self.mail.inbox() as box:
            return len(box.search("ALL"))
