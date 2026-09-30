from __future__ import annotations

import xml.etree.ElementTree as ET

from ..domain.jobs.job_posting import JobPosting
from ..lib.http_client import HttpClient
from ..shared.utils.date_utils import to_iso
from ..shared.utils.text_utils import strip_html
from .job_source import SourceQuery

FEEDS = ["remote-programming-jobs", "remote-full-stack-programming-jobs",
         "remote-back-end-programming-jobs", "remote-front-end-programming-jobs"]


class WeWorkRemotelySource:
    name = "weworkremotely"

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch(self, query: SourceQuery) -> list[JobPosting]:
        results = {}
        for feed in FEEDS:
            rss = self.http.get_bytes(f"https://weworkremotely.com/categories/{feed}.rss")
            for item in ET.fromstring(rss).iter("item"):
                link = item.findtext("link") or ""
                results[link] = self._posting(item, link)
        return list(results.values())

    @staticmethod
    def _posting(item, link: str) -> JobPosting:
        raw_title = item.findtext("title") or ""
        company, _, title = raw_title.partition(": ")
        return JobPosting(
            source="weworkremotely", ext_id=link.rstrip("/").rsplit("/", 1)[-1],
            title=title or raw_title, company=company if title else "", url=link,
            description=strip_html(item.findtext("description")),
            location=item.findtext("region") or "", employment_type=item.findtext("type") or "",
            remote=True, posted_at=to_iso(item.findtext("pubDate")),
        )
