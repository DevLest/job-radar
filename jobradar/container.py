"""Composition root: builds repositories, clients and services and wires them together (DIP).
One Container per request / background task, because a SQLite connection belongs to one thread."""

from __future__ import annotations

from functools import cached_property
from pathlib import Path

from .domain.alerts.alert_extractor import AlertExtractor
from .domain.alerts.alert_service import AlertService
from .domain.alerts.seen_email_repository import SeenEmailRepository
from .domain.applications.application_event_repository import ApplicationEventRepository
from .domain.applications.application_repository import ApplicationRepository
from .domain.applications.application_service import ApplicationService
from .domain.applications.draft_service import DraftService
from .domain.applications.posting_check_service import PostingCheckService
from .domain.applications.reply_check_service import ReplyCheckService
from .domain.applications.sending_service import SendingService
from .domain.applications.update_check_service import UpdateCheckService
from .domain.cv.cv_files import CvFileStore
from .domain.cv.cv_repository import CvRepository
from .domain.cv.cv_service import CvService
from .domain.home.home_service import HomeService
from .domain.home.layout_service import LayoutService
from .domain.jobs.job_repository import JobRepository
from .domain.jobs.job_service import JobService
from .domain.prefilter.prefilter_service import PrefilterService
from .domain.preferences.preferences_service import PreferencesService
from .domain.preferences.profile_repository import ProfileRepository
from .domain.report.report_builder import ReportBuilder
from .domain.scoring.batch_repository import BatchRepository
from .domain.scoring.batch_scoring_service import BatchScoringService
from .domain.scoring.scoring_service import ScoringService
from .domain.settings.settings_service import ENV_DEFAULTS, ENV_KEYS, SettingsService
from .domain.usage.usage_repository import UsageRepository
from .domain.usage.usage_service import UsageService
from .lib.database import Database
from .lib.env_file import EnvFile
from .lib.http_client import HttpClient
from .lib.key_value_store import KeyValueStore
from .lib.llm_client import LlmClient
from .lib.mail_client import MailClient
from .shared.constants import paths
from .sources.feed_collector import FeedCollector

POSTING_CHECK_USER_AGENT = "job-radar/0.1"


def env_file() -> EnvFile:
    return EnvFile(paths.ENV_PATH, ENV_KEYS, ENV_DEFAULTS)


class Container:
    def __init__(self, db_path: Path = paths.DB_PATH):
        self.db_path = db_path

    # --- infrastructure ---
    @cached_property
    def db(self) -> Database:
        return Database(self.db_path)

    @cached_property
    def llm(self) -> LlmClient:
        return LlmClient(on_usage=self.usage.log)

    @cached_property
    def mail(self) -> MailClient:
        return MailClient()

    @cached_property
    def meta(self) -> KeyValueStore:
        return KeyValueStore(self.db)

    @cached_property
    def profiles(self) -> ProfileRepository:
        return ProfileRepository(paths.PROFILE_PATH, paths.PROFILE_EXAMPLE_PATH)

    # --- repositories ---
    @cached_property
    def jobs(self) -> JobRepository:
        return JobRepository(self.db)

    @cached_property
    def applications(self) -> ApplicationRepository:
        return ApplicationRepository(self.db)

    @cached_property
    def events(self) -> ApplicationEventRepository:
        return ApplicationEventRepository(self.db)

    @cached_property
    def cvs(self) -> CvRepository:
        return CvRepository(self.db)

    @cached_property
    def usage(self) -> UsageRepository:
        return UsageRepository(self.db)

    @cached_property
    def batches(self) -> BatchRepository:
        return BatchRepository(self.db)

    @cached_property
    def seen_emails(self) -> SeenEmailRepository:
        return SeenEmailRepository(self.db)

    # --- services ---
    @cached_property
    def job_service(self) -> JobService:
        return JobService(self.jobs, self.applications, self.events)

    @cached_property
    def prefilter(self) -> PrefilterService:
        return PrefilterService(self.jobs)

    @cached_property
    def scoring(self) -> ScoringService:
        return ScoringService(self.jobs, self.llm)

    @cached_property
    def batch_scoring(self) -> BatchScoringService:
        return BatchScoringService(self.jobs, self.batches, self.llm, self.scoring)

    @cached_property
    def feed_collector(self) -> FeedCollector:
        return FeedCollector(HttpClient)

    @cached_property
    def alert_service(self) -> AlertService:
        return AlertService(self.mail, AlertExtractor(self.llm), self.seen_emails)

    @cached_property
    def application_service(self) -> ApplicationService:
        return ApplicationService(self.applications, self.events, self.jobs)

    @cached_property
    def drafts(self) -> DraftService:
        return DraftService(self.llm, self.cvs, self.applications, self.events, self.application_service)

    @cached_property
    def sending(self) -> SendingService:
        return SendingService(self.applications, self.events, self.jobs, self.cvs, self.mail, self.application_service)

    @cached_property
    def update_checks(self) -> UpdateCheckService:
        replies = ReplyCheckService(self.applications, self.events, self.seen_emails, self.mail, self.llm,
                                    self.application_service)
        postings = PostingCheckService(self.applications, self.events,
                                       lambda: HttpClient(timeout=20, user_agent=POSTING_CHECK_USER_AGENT))
        return UpdateCheckService(replies, postings, self.applications, self.mail)

    @cached_property
    def cv_service(self) -> CvService:
        return CvService(self.cvs, CvFileStore(paths.CV_DIR), self.llm, self.profiles)

    @cached_property
    def preferences(self) -> PreferencesService:
        return PreferencesService(self.profiles, self.meta)

    @cached_property
    def settings(self) -> SettingsService:
        return SettingsService(env_file(), self.mail)

    @cached_property
    def home(self) -> HomeService:
        return HomeService(self.jobs, self.applications, self.events, self.cvs, self.preferences, self.mail)

    @cached_property
    def layout(self) -> LayoutService:
        return LayoutService(self.jobs, self.applications, self.usage, self.batches, self.cvs, self.profiles,
                             self.mail)

    @cached_property
    def usage_service(self) -> UsageService:
        return UsageService(self.usage, self.jobs)

    @cached_property
    def report(self) -> ReportBuilder:
        return ReportBuilder(self.jobs)

    def close(self):
        if "db" in self.__dict__:
            self.db.close()
