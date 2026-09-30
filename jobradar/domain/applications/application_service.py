"""Application lifecycle: create, edit the draft, move along the board, notes."""

from __future__ import annotations

from ...shared.utils.date_utils import now_iso
from ..jobs.job import Job
from ..jobs.job_repository import JobRepository
from .application import Application
from .application_event_repository import ApplicationEventRepository
from .application_repository import ApplicationRepository


class ApplicationService:
    def __init__(self, applications: ApplicationRepository, events: ApplicationEventRepository, jobs: JobRepository):
        self.applications, self.events, self.jobs = applications, events, jobs

    def get(self, app_id: int) -> Application | None:
        return self.applications.get(app_id)

    def for_job(self, job_id: str) -> Application | None:
        return self.applications.for_job(job_id)

    def prior(self, job: Job) -> list[Application]:
        return self.applications.prior(job)

    def ensure(self, job: Job) -> int:
        """The application row for a job, created as a draft if needed."""
        existing = self.applications.for_job(job.id)
        return existing.id if existing else self.applications.create_draft(job)

    def set_status(self, app_id: int, status: str, note: str = "", kind: str = "status"):
        app = self.applications.get(app_id)
        changed = app.move_to(status, now_iso())
        self.applications.save(app, *changed)
        if app.job_id:
            self.jobs.set_status(app.job_id, status)
        self.events.add(app_id, kind, Application.move_summary(status, note))

    def change_status(self, app_id: int, status: str, note: str = "", next_action: str | None = None):
        """User-driven move (any direction), optionally setting the next step."""
        if self.applications.get(app_id).status != status:
            self.set_status(app_id, status, note)
        if next_action is not None:
            self.applications.update(app_id, next_action=next_action)

    def save_draft(self, app_id: int, to_email: str, subject: str, body: str, notes: str | None = None):
        self.applications.update(app_id, to_email=to_email, subject=subject, body=body)
        if notes is not None:
            self.applications.update(app_id, notes=notes)

    def mark_applied(self, app_id: int, method: str = "website"):
        self.applications.update(app_id, method=method)
        self.set_status(app_id, "applied", f"via {method}")

    def applied_elsewhere(self, job_id: str, method: str, draft: dict | None) -> int:
        """'I've applied' on a job: keeps what you wrote in the form, then marks it applied."""
        app_id = self.ensure(self.jobs.get(job_id))
        if draft is not None:
            self.save_draft(app_id, draft["to_email"], draft["subject"], draft["body"])
        self.mark_applied(app_id, method)
        return app_id

    def add_note(self, app_id: int, note: str) -> bool:
        note = (note or "").strip()
        if note:
            self.events.add(app_id, "note", note)
        return bool(note)
