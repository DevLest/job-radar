from __future__ import annotations

import re
import time

from ..domain.jobs.job_posting import JobPosting
from ..lib.http_client import HttpClient
from ..shared.utils.date_utils import to_iso
from ..shared.utils.text_utils import strip_html
from .job_source import SourceQuery
from .source_parsing import SNIPPET_NOTE, keep_result, parse_salary

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
WORK_TYPE_CODES = {"onsite": "1", "remote": "2", "hybrid": "3"}
PAUSE_SECONDS = 1.5  # between requests, to stay polite


class LinkedInSource:
    """LinkedIn's logged-out job search for jobs open to candidates in the Philippines (remote ones
    include foreign companies hiring there). One request per search term and work type."""
    name = "linkedin"

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch(self, query: SourceQuery) -> list[JobPosting]:
        results = {}
        for term in query.terms_or_all:
            for work_type in query.work_types:
                page = self.http.get_page(SEARCH_URL, keywords=term, location="Philippines",
                                          f_WT=WORK_TYPE_CODES[work_type], f_TPR=f"r{query.max_age_days * 86400}",
                                          start=0)
                time.sleep(PAUSE_SECONDS)
                for card in page.split("<li>")[1:]:
                    posting = self._posting(card, work_type)
                    if posting:
                        keep_result(results, term, posting)
        return list(results.values())

    @staticmethod
    def _posting(card: str, work_type: str) -> JobPosting | None:
        job_id = re.search(r"urn:li:jobPosting:(\d+)", card)
        title = re.search(r'base-search-card__title">(.*?)</h3>', card, re.S)
        if not (job_id and title):
            return None
        company = re.search(r'base-search-card__subtitle">(.*?)</h4>', card, re.S)
        location_match = re.search(r'job-search-card__location">(.*?)</span>', card, re.S)
        pay = re.search(r'job-search-card__salary-info">(.*?)</span>', card, re.S)
        date = re.search(r'<time[^>]*datetime="([^"]+)"', card)
        pay_text = strip_html(pay.group(1)) if pay else ""
        low, high, period, currency = parse_salary(pay_text)
        location = strip_html(location_match.group(1)) if location_match else "Philippines"
        return JobPosting(
            source="linkedin", ext_id=job_id.group(1), title=strip_html(title.group(1)),
            company=strip_html(company.group(1)) if company else "",
            url=f"https://www.linkedin.com/jobs/view/{job_id.group(1)}",
            description=SNIPPET_NOTE.format(site="LinkedIn").strip(),
            location=location if "philippines" in location.lower() else location + ", Philippines",
            salary_text=pay_text, salary_min=low, salary_max=high, salary_period=period, currency=currency,
            remote=work_type == "remote", work_type=work_type, posted_at=to_iso(date.group(1)) if date else None,
        )
