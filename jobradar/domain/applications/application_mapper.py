from __future__ import annotations

import sqlite3

from ..jobs.job_labels import verdict_word
from .application import Application
from .application_status import BOARD, CLOSED, EVENT_ICONS, EVENT_LABELS, LABELS, STATUSES, TRACK
from .application_view import (ApplicationPage, BoardCard, BoardColumn, BoardPage, EventView, StatusOption,
                               TrackStep)

LAST_EVENT_CHARS = 90


def to_event(row: sqlite3.Row) -> EventView:
    kind = row["kind"]
    company = row["company"] if "company" in row.keys() else None
    return EventView(ts=row["ts"], kind=kind, kind_label=EVENT_LABELS.get(kind, kind),
                     icon=EVENT_ICONS.get(kind, "check"), summary=row["summary"], company=company)


def track(app: Application) -> list[TrackStep]:
    position = TRACK.index(app.status) if app.status in TRACK else -1
    return [TrackStep(status, LABELS[status], position >= index, position == index)
            for index, status in enumerate(TRACK)]


def to_page(app: Application, events: list[sqlite3.Row]) -> ApplicationPage:
    return ApplicationPage(application=app, status_label=LABELS[app.status], job_id=app.job_id, track=track(app),
                           events=[to_event(row) for row in events], is_closed=app.status in CLOSED)


def _card(row: sqlite3.Row) -> BoardCard:
    return BoardCard(id=row["id"], company=row["company"], title=row["title"], status=row["status"],
                     score=row["score"], verdict=row["verdict"], verdict_word=verdict_word(row["verdict"]),
                     applied_at=row["applied_at"],
                     created_at=row["created_at"], last_event=(row["last_event"] or "")[:LAST_EVENT_CHARS],
                     next_action=row["next_action"])


def to_board(rows: list[sqlite3.Row]) -> BoardPage:
    cards = [_card(row) for row in rows]
    columns = [BoardColumn(key, title, icon, [card for card in cards if card.status in statuses])
               for key, title, statuses, icon in BOARD]
    options = [StatusOption(status, LABELS[status]) for status in STATUSES if status != "drafted"]
    return BoardPage(columns=columns, total=len(rows), status_options=options)
