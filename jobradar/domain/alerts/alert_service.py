"""Job-alert emails from LinkedIn, Indeed, JobStreet and OnlineJobs.ph -> job postings.

These sites forbid scraping, but they will happily email you alerts. We read those emails
(read-only), each one once, and have Claude list the jobs in it. Alerts only contain a snippet,
so scoring these jobs works on limited information."""

from __future__ import annotations

from datetime import datetime, timedelta

from ...lib import mail_client
from ...lib.llm_client import LLMError
from ...lib.mail_client import MailClient, Mailbox
from ..jobs.job_posting import JobPosting
from .alert_extractor import AlertExtractor
from .alert_links import provider_of
from .seen_email_repository import SeenEmailRepository

DEFAULT_LOOKBACK_DAYS = 7


class AlertService:
    def __init__(self, mail: MailClient, extractor: AlertExtractor, seen: SeenEmailRepository):
        self.mail, self.extractor, self.seen = mail, extractor, seen

    def ingest(self, profile: dict, log=print) -> list[JobPosting]:
        settings = profile.get("email_alerts") or {}
        if not settings.get("enabled", True):
            log("  email alerts disabled in profile")
            return []
        senders = settings.get("senders") or {}
        since = mail_client.imap_date(datetime.now() - timedelta(days=settings.get("lookback_days", DEFAULT_LOOKBACK_DAYS)))
        postings: list[JobPosting] = []
        with self.mail.inbox() as box:
            for provider, needles in senders.items():
                numbers = set()
                for needle in needles:
                    numbers.update(box.search(f"(SINCE {since} FROM {mail_client.quote(needle)})"))
                found = self._read_provider(box, profile, provider, senders, numbers, postings, log)
                log(f"  {provider:<11} {len(numbers):>3} emails -> {found} jobs")
        return postings

    def _read_provider(self, box: Mailbox, profile: dict, provider: str, senders: dict, numbers: set,
                       postings: list[JobPosting], log) -> int:
        found = 0
        for number in sorted(numbers, key=int):
            message = box.fetch(number)
            if message is None:
                continue
            mid = mail_client.message_id(message)
            if self.seen.seen(mid) or provider_of(message.get("From", ""), senders) != provider:
                continue
            try:
                got = self.extractor.extract(profile, provider, message)
            except LLMError as e:
                log(f"  {provider}: could not read '{message.get('Subject', '')[:50]}': {e}")
                continue
            self.seen.mark(mid, "alert", f"{provider}: {len(got)} jobs")
            postings += got
            found += len(got)
        return found
