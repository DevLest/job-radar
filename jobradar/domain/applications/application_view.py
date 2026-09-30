from __future__ import annotations

from dataclasses import dataclass

from .application import Application


@dataclass
class EventView:
    ts: str
    kind: str
    kind_label: str
    icon: str
    summary: str
    company: str | None = None


@dataclass
class TrackStep:
    status: str
    label: str
    reached: bool
    current: bool


@dataclass
class StatusOption:
    value: str
    label: str


@dataclass
class BoardCard:
    id: int
    company: str | None
    title: str | None
    status: str
    score: int | None
    verdict: str | None
    verdict_word: str
    applied_at: str | None
    created_at: str | None
    last_event: str
    next_action: str | None


@dataclass
class BoardColumn:
    key: str
    title: str
    icon: str
    cards: list[BoardCard]

    @property
    def is_drafts(self) -> bool:
        return self.key == "drafted"


@dataclass
class BoardPage:
    columns: list[BoardColumn]
    total: int
    status_options: list[StatusOption]


@dataclass
class ApplicationPage:
    application: Application
    status_label: str
    job_id: str | None
    track: list[TrackStep]
    events: list[EventView]
    is_closed: bool
