from __future__ import annotations

from dataclasses import dataclass

from ...shared.utils.hash_utils import short_hash
from ..applications.application import Application
from ..applications.application_event_repository import ApplicationEventRepository
from ..applications.application_mapper import to_event
from ..applications.application_repository import ApplicationRepository
from ..applications.application_view import EventView
from ..applications.contact_emails import emails_in
from .job_mapper import to_card, to_detail
from .job_posting import JobPosting, remote_flag
from .job_queries import JOB_TABS, LIST_LIMIT, JobListFilter
from .job_repository import JobRepository
from .job_view import JobDetailView, JobListPage, JobTab

RECENT_EVENTS = 5


@dataclass
class ManualJob:
    """A job you found yourself, as typed into the 'Add a job' form (raw values)."""
    title: str | None
    company: str | None
    url: str | None
    location: str | None
    work_type: str | None
    salary: str | None
    description: str | None

    def ext_id(self) -> str:
        return short_hash(f"{self.company}|{self.title}|{self.url}".lower())

    def to_posting(self) -> JobPosting:
        work_type = self.work_type or ""
        return JobPosting(source="manual", ext_id=self.ext_id(), title=(self.title or "").strip(),
                          company=(self.company or "").strip(), url=(self.url or "").strip(),
                          description=self.description or "", location=self.location or "",
                          salary_text=self.salary or "", work_type=work_type, remote=remote_flag(work_type))


@dataclass
class JobDetailPage:
    job: JobDetailView
    application: Application | None
    prior: list[Application]
    prior_same_role: bool
    events: list[EventView]


class JobError(ValueError):
    pass


class JobService:
    def __init__(self, jobs: JobRepository, applications: ApplicationRepository, events: ApplicationEventRepository):
        self.jobs, self.applications, self.events = jobs, applications, events

    def list_page(self, list_filter: JobListFilter) -> JobListPage:
        where, params = list_filter.where()
        jobs = self.jobs.find(where, params, order=list_filter.order(), limit=LIST_LIMIT)
        index = self.applications.applied_index()
        tabs = [JobTab(key, label, self.jobs.count(tab_where)) for key, label, tab_where in JOB_TABS]
        return JobListPage(cards=[to_card(job, index) for job in jobs], tabs=tabs, tab=list_filter.tab,
                           search=list_filter.search, work_type=list_filter.work_type, source=list_filter.source,
                           sort=list_filter.sort, sources=self.jobs.sources(), truncated=len(jobs) == LIST_LIMIT)

    def detail(self, job_id: str) -> JobDetailPage | None:
        job = self.jobs.get(job_id)
        if not job:
            return None
        application = self.applications.for_job(job_id)
        prior = self.applications.prior(job)
        events = self.events.for_application(application.id)[:RECENT_EVENTS] if application else []
        return JobDetailPage(job=to_detail(job, emails_in(job.description)), application=application, prior=prior,
                             prior_same_role=any(p.fingerprint == job.fingerprint for p in prior),
                             events=[to_event(row) for row in events])

    def add_manual(self, manual: ManualJob) -> str:
        if not (manual.title or "").strip():
            raise JobError("Please enter the job title")
        new_ids = self.jobs.insert_new([manual.to_posting()])
        if not new_ids:
            raise JobError("That job is already in your list")
        job = self.jobs.get(new_ids[0])
        job.pick_manually()
        self.jobs.save(job, "stage", "kw_score")
        return job.id

    def set_hidden(self, job_id: str, hidden: bool):
        job = self.jobs.get(job_id)
        if job:
            job.hide() if hidden else job.unhide()
            self.jobs.save(job, "status")
