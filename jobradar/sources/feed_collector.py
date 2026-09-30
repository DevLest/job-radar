"""Runs every enabled source. International remote boards use their public JSON/RSS feeds; the
Philippine sites are read from their public, logged-out search pages - never your account."""

from __future__ import annotations

from typing import Callable

from ..domain.jobs.job_posting import JobPosting
from ..lib.http_client import HttpClient
from .job_source import DEFAULT_MAX_AGE_DAYS, SourceQuery
from .source_registry import BOARD_SOURCES, FEED_SOURCES


def query_from(profile: dict) -> SourceQuery:
    query = SourceQuery(terms=(profile.get("sources") or {}).get("search_terms") or [],
                        max_age_days=(profile.get("filters") or {}).get("max_age_days") or DEFAULT_MAX_AGE_DAYS)
    work_types = (profile.get("work_setup") or {}).get("work_types")
    if work_types:
        query.work_types = work_types
    return query


class FeedCollector:
    def __init__(self, http_factory: Callable[[], HttpClient]):
        self.http_factory = http_factory

    def fetch_all(self, profile: dict, log=print) -> list[JobPosting]:
        http = self.http_factory()
        try:
            return self._feeds(http, profile, log) + self._boards(http, profile, log)
        finally:
            http.close()

    @staticmethod
    def _feeds(http: HttpClient, profile: dict, log) -> list[JobPosting]:
        enabled, query, postings = profile.get("sources") or {}, query_from(profile), []
        for source_class in FEED_SOURCES:
            if not enabled.get(source_class.name, False):
                continue
            try:
                found = source_class(http).fetch(query)
                log(f"  {source_class.name:<15} {len(found):>5} jobs")
                postings += found
            except Exception as e:  # one broken source must not stop the run
                log(f"  {source_class.name:<15} FAILED: {e}")
        return postings

    @staticmethod
    def _boards(http: HttpClient, profile: dict, log) -> list[JobPosting]:
        postings = []
        for source_class in BOARD_SOURCES:
            for slug in (profile.get("companies") or {}).get(source_class.name) or []:
                try:
                    found = source_class(http).fetch_board(slug)
                    log(f"  {source_class.name}:{slug:<10} {len(found):>5} jobs")
                    postings += found
                except Exception as e:
                    log(f"  {source_class.name}:{slug:<10} FAILED: {e}")
        return postings
