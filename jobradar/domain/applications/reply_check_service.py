"""Finds employer replies in your inbox. Replies to an email sent from the app are matched by
Message-ID for free; other emails only go to Claude when they mention the company, arrived after
you applied, and were not seen before."""

from __future__ import annotations

from datetime import datetime, timedelta

from ...lib import mail_client
from ...lib.email_text import readable
from ...lib.llm_client import LlmClient, LLMError
from ...lib.mail_client import MailClient, Mailbox
from ...shared.utils.date_utils import now_iso
from ..alerts.seen_email_repository import SeenEmailRepository
from .application import Application
from .application_event_repository import ApplicationEventRepository
from .application_repository import ApplicationRepository
from .application_service import ApplicationService

EMAILS_PER_APPLICATION = 5
MIN_COMPANY_CHARS = 3
MAX_EMAIL_CHARS = 2500

SCHEMA = {
    "type": "object",
    "properties": {
        "related": {"type": "boolean", "description": "Is this email about this specific application?"},
        "status": {"type": "string", "enum": ["acknowledged", "assessment", "interview", "offer", "rejected",
                                              "info_request", "other"]},
        "summary": {"type": "string", "description": "One sentence"},
        "action_needed": {"type": "string", "description": "What the candidate should do next, or empty"},
    },
    "required": ["related", "status", "summary", "action_needed"],
    "additionalProperties": False,
}
SYSTEM = ("You triage emails for a job seeker. Decide if the email is about the given application "
          "(same company; job alerts, newsletters and marketing are NOT related) and what it means.")


class ReplyCheckService:
    def __init__(self, applications: ApplicationRepository, events: ApplicationEventRepository,
                 seen: SeenEmailRepository, mail: MailClient, llm: LlmClient, lifecycle: ApplicationService):
        self.applications, self.events, self.seen = applications, events, seen
        self.mail, self.llm, self.lifecycle = mail, llm, lifecycle

    def check(self, profile: dict, log=print):
        apps = self.applications.active()
        if not apps:
            log("  no active applications to check")
            return
        alert_senders = [n for needles in ((profile.get("email_alerts") or {}).get("senders") or {}).values()
                         for n in needles]
        me = self.mail.my_address().lower()
        with self.mail.inbox() as box:
            for app in apps:
                self._check_application(box, app, profile, alert_senders, me, log)
                self.applications.update(app.id, last_checked=now_iso())

    def _candidates(self, box: Mailbox, app: Application) -> list[bytes]:
        since = datetime.fromisoformat(app.applied_at or app.created_at) - timedelta(days=1)
        numbers = set()
        if app.sent_message_id:  # direct replies: exact and free
            numbers.update(box.search(f"(HEADER In-Reply-To {mail_client.quote(app.sent_message_id)})"))
        if app.company and len(app.company) >= MIN_COMPANY_CHARS:
            numbers.update(box.search(f"(SINCE {mail_client.imap_date(since)} TEXT {mail_client.quote(app.company)})"))
        return sorted(numbers, key=int, reverse=True)

    def _check_application(self, box: Mailbox, app: Application, profile: dict, alert_senders: list[str],
                           me: str, log):
        checked = 0
        for number in self._candidates(box, app):
            if checked >= EMAILS_PER_APPLICATION:
                break
            message = box.fetch(number)
            if message is None:
                continue
            mid = mail_client.message_id(message)
            sender = (message.get("From") or "").lower()
            seen_key = f"{app.id}|{mid}"
            if self.seen.seen(seen_key) or (me and me in sender) or any(n.lower() in sender for n in alert_senders):
                continue
            self.seen.mark(seen_key, "update", app.company or "")
            is_reply = bool(app.sent_message_id) and app.sent_message_id in (message.get("In-Reply-To") or "")
            checked += 1
            try:
                result = self._classify(profile, app, message)
            except LLMError as e:
                log(f"  could not classify email for {app.company}: {e}")
                continue
            if result["related"] or is_reply:
                self._apply(app, result, mid)
                log(f"  {app.company}: {result['status']} - {result['summary'][:80]}")

    def _classify(self, profile: dict, app: Application, message) -> dict:
        text, _ = readable(message)
        content = (f"APPLICATION: {app.title} at {app.company} (applied {(app.applied_at or '')[:10]})\n\n"
                   f"EMAIL FROM: {message.get('From', '')}\nSUBJECT: {message.get('Subject', '')}\n"
                   f"DATE: {message.get('Date', '')}\n\n{text[:MAX_EMAIL_CHARS]}")
        return self.llm.ask("updates", profile, SYSTEM, content, SCHEMA, max_tokens=2000)

    def _apply(self, app: Application, result: dict, mid: str):
        action = result["action_needed"]
        self.events.add(app.id, "email_in", result["summary"] + (f" -> {action}" if action else ""), mid)
        if action:
            self.applications.update(app.id, next_action=action)
        if app.accepts_automatic(result["status"]):
            self.lifecycle.set_status(app.id, result["status"], "from email", kind="auto")
        self.applications.update(app.id, last_update=now_iso())
