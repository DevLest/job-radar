from __future__ import annotations

from ..domain.jobs.job_posting import JobPosting
from ..lib.http_client import HttpClient
from ..shared.utils.date_utils import to_iso
from ..shared.utils.text_utils import strip_html
from .job_source import SourceQuery
from .source_parsing import to_number


class HimalayasSource:
    name = "himalayas"
    PERIODS = {"hourly": "hour", "monthly": "month"}

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch(self, query: SourceQuery) -> list[JobPosting]:
        results = {}
        for term in query.terms_or_all:
            data = self.http.get_json("https://himalayas.app/jobs/api/search", q=term)
            for item in data.get("jobs", []):
                locations = item.get("locationRestrictions") or []
                results[item["guid"]] = JobPosting(
                    source="himalayas", ext_id=item["guid"].rstrip("/").rsplit("/", 1)[-1],
                    title=item["title"], company=item["companyName"], url=item.get("applicationLink") or item["guid"],
                    description=strip_html(item.get("description")),
                    location="Worldwide" if not locations else ", ".join(locations),
                    tags=(item.get("categories") or []) + (item.get("seniority") or []),
                    salary_min=to_number(item.get("minSalary")), salary_max=to_number(item.get("maxSalary")),
                    salary_period=self.PERIODS.get(item.get("salaryPeriod"), "year"), currency=item.get("currency") or "",
                    employment_type=item.get("employmentType") or "", remote=True,
                    posted_at=to_iso(item.get("pubDate")),
                )
        return list(results.values())
