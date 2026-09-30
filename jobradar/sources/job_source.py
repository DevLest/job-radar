"""Job-source contracts. A source makes no LLM calls: it returns normalized JobPostings.
Add a source by writing a class that satisfies one of these protocols and registering it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..domain.jobs.job_posting import JobPosting
from ..lib.http_client import HttpClient
from ..shared.constants.work_types import WORK_TYPES

DEFAULT_MAX_AGE_DAYS = 30


@dataclass
class SourceQuery:
    terms: list[str] = field(default_factory=list)
    work_types: list[str] = field(default_factory=lambda: list(WORK_TYPES))
    max_age_days: int = DEFAULT_MAX_AGE_DAYS

    @property
    def terms_or_all(self) -> list[str]:
        return self.terms or [""]


class JobSource(Protocol):
    """A job board / feed searched with your search terms."""
    name: str

    def __init__(self, http: HttpClient): ...

    def fetch(self, query: SourceQuery) -> list[JobPosting]: ...


class CompanyBoardSource(Protocol):
    """An ATS careers board for one company (the slug from its careers link)."""
    name: str

    def __init__(self, http: HttpClient): ...

    def fetch_board(self, slug: str) -> list[JobPosting]: ...
