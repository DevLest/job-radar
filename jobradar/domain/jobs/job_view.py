"""View models handed to templates / JSON. Templates only render these."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Chip:
    label: str
    tone: str = ""


@dataclass
class Meter:
    label: str
    percent: int
    word: str
    tone: str


@dataclass
class AppliedBadge:
    same_role_applied_at: str | None = None  # ISO date when you applied to this exact role
    at_company: bool = False


@dataclass
class JobCardView:
    id: str
    title: str
    company: str
    location_short: str
    posted_at: str | None
    source: str
    url: str
    work_type: str
    score: int | None
    verdict: str | None
    verdict_word: str
    pay_short: str
    fit_chips: list[Chip]
    top_skills: list[str]
    summary: str
    reject_reason: str | None
    is_hidden: bool
    can_rate: bool
    applied: AppliedBadge
    search_text: str


@dataclass
class JobTab:
    key: str
    label: str
    count: int


@dataclass
class JobListPage:
    cards: list[JobCardView]
    tabs: list[JobTab]
    tab: str
    search: str
    work_type: str
    source: str
    sort: str
    sources: list[str]
    truncated: bool


@dataclass
class JobDetailView:
    id: str
    title: str
    company: str
    location: str
    posted_at: str | None
    source: str
    url: str
    work_type: str
    employment_type: str
    score: int | None
    verdict: str | None
    verdict_word: str
    status: str
    reject_reason: str | None
    pay: str
    description: str
    description_collapsible: bool
    error: str | None
    summary: str
    meters: list[Meter] = field(default_factory=list)
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)

    @property
    def is_rated(self) -> bool:
        return self.score is not None

    @property
    def is_hidden(self) -> bool:
        return self.status == "ignored"
