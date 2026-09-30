from __future__ import annotations

import html

from ..domain.jobs.job_posting import JobPosting
from ..lib.http_client import HttpClient
from ..shared.utils.date_utils import to_iso
from ..shared.utils.text_utils import strip_html
from .job_source import SourceQuery
from .source_parsing import to_number


class JobicySource:
    name = "jobicy"

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch(self, query: SourceQuery) -> list[JobPosting]:
        results = {}
        for term in query.terms_or_all:
            params = {"count": 50}
            if term:
                params["tag"] = term
            data = self.http.get_json("https://jobicy.com/api/v2/remote-jobs", **params)
            for item in data.get("jobs", []):
                results[item["id"]] = JobPosting(
                    source="jobicy", ext_id=str(item["id"]), title=html.unescape(item["jobTitle"]),
                    company=item["companyName"], url=item["url"],
                    description=strip_html(item.get("jobDescription")), location=item.get("jobGeo") or "",
                    tags=(item.get("jobIndustry") or []) + [item.get("jobLevel") or ""],
                    salary_min=to_number(item.get("annualSalaryMin")), salary_max=to_number(item.get("annualSalaryMax")),
                    currency=item.get("salaryCurrency") or "",
                    employment_type=", ".join(item.get("jobType") or []), remote=True,
                    posted_at=to_iso(item.get("pubDate")),
                )
        return list(results.values())
