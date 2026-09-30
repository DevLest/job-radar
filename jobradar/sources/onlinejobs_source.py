from __future__ import annotations

import re

from ..domain.jobs.job_posting import JobPosting
from ..lib.http_client import HttpClient
from ..shared.utils.date_utils import to_iso
from ..shared.utils.text_utils import strip_html
from .job_source import SourceQuery
from .source_parsing import SNIPPET_NOTE, keep_result, parse_salary

SEARCH_URL = "https://www.onlinejobs.ph/jobseekers/jobsearch"
CARD_SEPARATOR = "<!-- Start -->"


class OnlineJobsSource:
    """OnlineJobs.ph only lists remote jobs from employers hiring Filipinos."""
    name = "onlinejobs"

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch(self, query: SourceQuery) -> list[JobPosting]:
        results = {}
        for term in query.terms_or_all:
            page = self.http.get_page(SEARCH_URL, jobkeyword=term)
            for card in page.split(CARD_SEPARATOR)[1:]:
                posting = self._posting(card)
                if posting:
                    keep_result(results, term, posting)
        return list(results.values())

    @staticmethod
    def _posting(card: str) -> JobPosting | None:
        link = re.search(r'href="(/jobseekers/job/[^"]+?-(\d+))"', card)
        title = re.search(r"<h4[^>]*>(.*?)<span", card, re.S)
        if not (link and title):
            return None
        kind = re.search(r'<span class="badge[^"]*">([^<]+)</span>', card)
        pay = re.search(r'icon-round-dollar.*?<dd class="col">(.*?)</dd>', card, re.S)
        description = re.search(r'<div class="desc[^"]*">(.*?)<a href', card, re.S)
        posted = re.search(r'data-temp-2="([^"]+)"', card)
        pay_text = strip_html(pay.group(1)) if pay else ""
        low, high, period, currency = parse_salary(pay_text)
        return JobPosting(
            source="onlinejobs", ext_id=link.group(2), title=strip_html(title.group(1)),
            company="",  # employers are hidden until you open the posting
            url="https://www.onlinejobs.ph" + link.group(1),
            description=strip_html(description.group(1) if description else "") + SNIPPET_NOTE.format(site="OnlineJobs.ph"),
            location="Philippines (remote)", tags=re.findall(r"class='badge'>([^<]+)<", card),
            salary_text=pay_text if pay_text.upper() != "TBD" else "", salary_min=low, salary_max=high,
            salary_period=period, currency=currency,
            employment_type="" if not kind or kind.group(1).strip() == "Any" else kind.group(1).strip(),
            remote=True, work_type="remote",
            posted_at=to_iso(posted.group(1).replace(" ", "T")) if posted else None,
        )
