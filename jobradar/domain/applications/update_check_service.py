"""'Check application updates': replies in your inbox, closed postings, follow-up reminders."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ...lib.mail_client import MailClient
from .application_repository import ApplicationRepository
from .posting_check_service import PostingCheckService
from .reply_check_service import ReplyCheckService

FOLLOW_UP_AFTER_DAYS = 14
FOLLOW_UP_TEXT = "No reply in 14 days - consider a follow-up"


class UpdateCheckService:
    def __init__(self, replies: ReplyCheckService, postings: PostingCheckService,
                 applications: ApplicationRepository, mail: MailClient):
        self.replies, self.postings, self.applications, self.mail = replies, postings, applications, mail

    def check(self, profile: dict, log=print):
        if self.mail.imap_configured():
            self.replies.check(profile, log)
        else:
            log("  mailbox not configured - skipping reply check")
        self.postings.check(log)
        self.remind_follow_ups()

    def remind_follow_ups(self):
        before = (datetime.now(timezone.utc) - timedelta(days=FOLLOW_UP_AFTER_DAYS)).isoformat()
        for app in self.applications.silent_since(before):
            self.applications.update(app.id, next_action=FOLLOW_UP_TEXT)
