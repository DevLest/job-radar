from __future__ import annotations

from ..domain.jobs.job_posting import JobPosting
from ..lib.http_client import HttpClient
from ..shared.utils.date_utils import to_iso
from ..shared.utils.text_utils import strip_html
from .job_source import SourceQuery
from .source_parsing import to_number


class RemoteOkSource:
    name = "remoteok"

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch(self, query: SourceQuery) -> list[JobPosting]:
        data = self.http.get_json("https://remoteok.com/api")
        return [JobPosting(
            source="remoteok", ext_id=str(item["id"]), title=item.get("position", ""),
            company=(item.get("company") or "").strip(), url=item.get("url", ""),
            description=strip_html(item.get("description")), location=item.get("location") or "",
            tags=item.get("tags") or [], salary_min=to_number(item.get("salary_min")),
            salary_max=to_number(item.get("salary_max")), currency="USD" if to_number(item.get("salary_min")) else "",
            remote=True, posted_at=to_iso(item.get("date")),
        ) for item in data[1:]]  # element 0 is the legal notice
