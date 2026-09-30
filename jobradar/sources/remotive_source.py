from __future__ import annotations

from ..domain.jobs.job_posting import JobPosting
from ..lib.http_client import HttpClient
from ..shared.utils.date_utils import to_iso
from ..shared.utils.text_utils import strip_html
from .job_source import SourceQuery


class RemotiveSource:
    """Remotive asks callers to keep volume low; one request per search term."""
    name = "remotive"

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch(self, query: SourceQuery) -> list[JobPosting]:
        results = {}
        for term in query.terms_or_all:
            data = self.http.get_json("https://remotive.com/api/remote-jobs", search=term, limit=100)
            for item in data.get("jobs", []):
                results[item["id"]] = JobPosting(
                    source="remotive", ext_id=str(item["id"]), title=item["title"],
                    company=item["company_name"], url=item["url"],
                    description=strip_html(item.get("description")),
                    location=item.get("candidate_required_location") or "",
                    tags=item.get("tags") or [], salary_text=item.get("salary") or "",
                    employment_type=item.get("job_type") or "", remote=True,
                    posted_at=to_iso(item.get("publication_date")),
                )
        return list(results.values())
