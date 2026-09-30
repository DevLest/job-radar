from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ...lib.mail_client import MailClient
from ..applications.application import Application
from ..applications.application_event_repository import ApplicationEventRepository
from ..applications.application_mapper import to_event
from ..applications.application_repository import ApplicationRepository
from ..applications.application_view import EventView
from ..cv.cv_repository import CvRepository
from ..jobs.job_mapper import to_card
from ..jobs.job_queries import GOOD_MATCH
from ..jobs.job_repository import JobRepository
from ..jobs.job_view import JobCardView
from ..preferences.preferences_service import PreferencesService
from ..settings.settings_service import api_configured

TOP_JOBS = 6


@dataclass
class SetupStep:
    done: bool
    title: str
    icon: str
    text: str
    endpoint: str  # "" = the Find jobs dialog
    cta: str


@dataclass
class HomeStats:
    matches: int
    new_week: int
    applied: int
    interviews: int
    seen: int


@dataclass
class HomePage:
    setup: list[SetupStep]
    top: list[JobCardView]
    attention: list[Application]
    activity: list[EventView]
    stats: HomeStats

    @property
    def setup_done(self) -> int:
        return sum(step.done for step in self.setup)

    @property
    def setup_percent(self) -> float:
        return round(self.setup_done / len(self.setup) * 100, 0)

    @property
    def next_step(self) -> int:
        return next((i for i, step in enumerate(self.setup) if not step.done), -1)


class HomeService:
    def __init__(self, jobs: JobRepository, applications: ApplicationRepository, events: ApplicationEventRepository,
                 cvs: CvRepository, preferences: PreferencesService, mail: MailClient):
        self.jobs, self.applications, self.events = jobs, applications, events
        self.cvs, self.preferences, self.mail = cvs, preferences, mail

    def setup_steps(self) -> list[SetupStep]:
        return [
            SetupStep(api_configured(), "Add your AI key", "key", "Needed to rate jobs and write applications.",
                      "settings.page", "Open Settings"),
            SetupStep(self.cvs.active() is not None, "Upload your CV", "file",
                      "The AI learns your skills from it and uses it for applications.", "cv.page", "Upload CV"),
            SetupStep(self.preferences.were_saved(), "Set your pay & work style", "wallet",
                      "Minimum pay, remote / hybrid / on-site, and your cities.", "preferences.page", "Set preferences"),
            SetupStep(self.mail.imap_configured(), "Connect your email (optional)", "mail",
                      "Reads LinkedIn / Indeed / JobStreet / OnlineJobs.ph alerts and employer replies.",
                      "settings.page", "Connect email"),
            SetupStep(self.jobs.count() > 0, "Find your first jobs", "sparkles", "Click 'Find jobs' at the top right.",
                      "", "Find jobs"),
        ]

    def page(self) -> HomePage:
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        index = self.applications.applied_index()
        top = self.jobs.find(f"{GOOD_MATCH} AND status=''", order="score DESC, posted_at DESC", limit=TOP_JOBS)
        stats = HomeStats(matches=self.jobs.count_top_matches(), new_week=self.jobs.count_good_matches(since=week_ago),
                          applied=self.applications.count_sent(), interviews=self.applications.count_interviews(),
                          seen=self.jobs.count())
        return HomePage(setup=self.setup_steps(), top=[to_card(job, index) for job in top],
                        attention=self.applications.needing_attention(),
                        activity=[to_event(row) for row in self.events.recent_with_company()], stats=stats)
