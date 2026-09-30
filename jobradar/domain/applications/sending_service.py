"""Sends an application email - only ever as the direct result of you clicking Send."""

from __future__ import annotations

from ...lib.mail_client import MailClient
from ..cv.cv_repository import CvRepository
from ..jobs.job_repository import JobRepository
from .application_event_repository import ApplicationEventRepository
from .application_repository import ApplicationRepository
from .application_service import ApplicationService
from .contact_emails import is_email


class SendRefused(ValueError):
    pass


class SendingService:
    def __init__(self, applications: ApplicationRepository, events: ApplicationEventRepository, jobs: JobRepository,
                 cvs: CvRepository, mail: MailClient, lifecycle: ApplicationService):
        self.applications, self.events, self.jobs = applications, events, jobs
        self.cvs, self.mail, self.lifecycle = cvs, mail, lifecycle

    def send_draft(self, app_id: int, draft: dict, attach_cv: bool, confirm_duplicate: bool) -> str:
        """Saves the form, checks it is safe to send, sends. Returns the recipient.
        Raises SendRefused, ValueError or MailError with a message for the user."""
        self.lifecycle.save_draft(app_id, draft["to_email"], draft["subject"], draft["body"])
        app = self.applications.get(app_id)
        job = self.jobs.get(app.job_id) if app.job_id else None
        if not app.is_draft:
            raise SendRefused("This application was already sent.")
        if job and self.applications.prior(job) and not confirm_duplicate:
            raise SendRefused("You already applied to this company - tick the confirmation box to send anyway.")
        self.send(app_id, attach_cv)
        return app.to_email

    def send(self, app_id: int, attach_cv: bool = True) -> str:
        app = self.applications.get(app_id)
        if not is_email(app.to_email):
            raise ValueError("Enter a valid recipient email address.")
        if not (app.subject and app.body):
            raise ValueError("Subject and message are required.")
        cv = self.cvs.active()
        message_id = self.mail.send(app.to_email.strip(), app.subject, app.body,
                                    cv.file if (attach_cv and cv) else None)
        self.applications.update(app_id, method="email", sent_message_id=message_id)
        self.events.add(app_id, "sent", f"Emailed {app.to_email}", message_id)
        self.lifecycle.set_status(app_id, "applied", "sent by email")
        return message_id
