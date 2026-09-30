from __future__ import annotations

from ..domain.jobs.job_posting import JobPosting
from ..lib.http_client import HttpClient
from ..shared.utils.date_utils import to_iso
from ..shared.utils.text_utils import strip_html
from .job_source import SourceQuery
from .source_parsing import work_type_from


class ArbeitnowSource:
    """Mostly EU on-site jobs (off by default)."""
    name = "arbeitnow"

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch(self, query: SourceQuery) -> list[JobPosting]:
        data = self.http.get_json("https://www.arbeitnow.com/api/job-board-api")
        return [JobPosting(
            source="arbeitnow", ext_id=item["slug"], title=item["title"], company=item["company_name"],
            url=item["url"], description=strip_html(item.get("description")), location=item.get("location") or "",
            tags=item.get("tags") or [], employment_type=", ".join(item.get("job_types") or []),
            remote=bool(item.get("remote")),
            work_type="remote" if item.get("remote") else work_type_from(item.get("location")),
            posted_at=to_iso(item.get("created_at")),
        ) for item in data.get("data", [])]
