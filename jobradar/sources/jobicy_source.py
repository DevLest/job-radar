from __future__ import annotations

import html

from ..domain.jobs.job_posting import JobPosting
from ..lib.http_client import HttpClient
from ..shared.utils.date_utils import to_iso
from ..shared.utils.text_utils import strip_html
from .job_source import SourceQuery
from .source_parsing import to_number

API_URL = "https://jobicy.com/api/v2/remote-jobs"
# Jobicy's geo filter returns jobs open to the Philippines: "Anywhere", "APAC" and PH-only roles.
# Its tag filter is an exact tag match ("laravel" finds nothing), so one geo request is both
# more complete and cheaper; the free keyword filter then picks the jobs that fit your skills.
GEO = "philippines"


class JobicySource:
    name = "jobicy"

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch(self, query: SourceQuery) -> list[JobPosting]:
        data = self.http.get_json(API_URL, count=100, geo=GEO)
        return [JobPosting(
            source="jobicy", ext_id=str(item["id"]), title=html.unescape(item["jobTitle"]),
            company=item["companyName"], url=item["url"],
            description=strip_html(item.get("jobDescription")), location=item.get("jobGeo") or "",
            tags=(item.get("jobIndustry") or []) + [item.get("jobLevel") or ""],
            salary_min=to_number(item.get("annualSalaryMin")), salary_max=to_number(item.get("annualSalaryMax")),
            currency=item.get("salaryCurrency") or "",
            employment_type=", ".join(item.get("jobType") or []), remote=True,
            posted_at=to_iso(item.get("pubDate")),
        ) for item in data.get("jobs", [])]
