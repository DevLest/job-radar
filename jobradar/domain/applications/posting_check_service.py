"""Flags applications whose posting disappeared (HTTP 404/410). Free - no tokens."""

from __future__ import annotations

from typing import Callable

import httpx

from ...lib.http_client import HttpClient
from .application_event_repository import ApplicationEventRepository
from .application_repository import ApplicationRepository

# Big job sites block or fake 200s for bots, so "is the posting still up?" only works elsewhere.
NO_POSTING_CHECK = {"linkedin", "indeed", "jobstreet", "onlinejobs", "hackernews", "manual"}
GONE = (404, 410)
CLOSED_KIND = "posting_closed"


class PostingCheckService:
    def __init__(self, applications: ApplicationRepository, events: ApplicationEventRepository,
                 http_factory: Callable[[], HttpClient]):
        self.applications, self.events, self.http_factory = applications, events, http_factory

    def check(self, log=print):
        rows = self.applications.active_with_source()
        http = self.http_factory()
        try:
            for app, source in rows:
                if source in NO_POSTING_CHECK or self.events.has_kind(app.id, CLOSED_KIND):
                    continue
                try:
                    code = http.status_code(app.url)
                except httpx.HTTPError:
                    continue
                if code in GONE:
                    self.events.add(app.id, CLOSED_KIND, f"Job posting is no longer online (HTTP {code})")
                    log(f"  {app.company}: posting closed")
        finally:
            http.close()
