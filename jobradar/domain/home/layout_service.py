"""What every page's frame shows: sidebar counts, AI spend, and which connections are set up."""

from __future__ import annotations

from dataclasses import dataclass

from ...lib.mail_client import MailClient
from ..applications.application_repository import ApplicationRepository
from ..cv.cv_repository import CvRepository
from ..jobs.job_repository import JobRepository
from ..preferences.profile_repository import ProfileRepository
from ..scoring.batch_repository import BatchRepository
from ..scoring.cost_estimator import estimate, max_jobs_per_run
from ..settings.settings_service import api_configured
from ..usage.usage_repository import UsageRepository


@dataclass
class NavSummary:
    matches: int
    active_apps: int
    spent: float
    queued: int
    cap: int
    est_max: float
    est_queued: float
    pending_batches: int

    @property
    def rate_now(self) -> int:
        return min(self.queued, self.cap)


@dataclass
class Configured:
    api: bool
    imap: bool
    smtp: bool
    cv: bool


class LayoutService:
    def __init__(self, jobs: JobRepository, applications: ApplicationRepository, usage: UsageRepository,
                 batches: BatchRepository, cvs: CvRepository, profiles: ProfileRepository, mail: MailClient):
        self.jobs, self.applications, self.usage, self.batches = jobs, applications, usage, batches
        self.cvs, self.profiles, self.mail = cvs, profiles, mail

    def nav(self) -> NavSummary:
        profile = self.profiles.load()
        cap = max_jobs_per_run(profile)
        queued = self.jobs.count_stage("queued")
        return NavSummary(matches=self.jobs.count_top_matches(), active_apps=self.applications.count_active(),
                          spent=self.usage.total_spent(), queued=queued, cap=cap, est_max=estimate(profile, cap),
                          est_queued=estimate(profile, min(queued, cap)), pending_batches=self.batches.count_pending())

    def configured(self) -> Configured:
        return Configured(api=api_configured(), imap=self.mail.imap_configured(), smtp=self.mail.smtp_configured(),
                          cv=self.cvs.active() is not None)
