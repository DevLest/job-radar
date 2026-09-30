from __future__ import annotations

import html

from ..domain.jobs.job_posting import JobPosting
from ..lib.http_client import HttpClient
from ..shared.utils.date_utils import to_iso
from ..shared.utils.text_utils import strip_html
from .source_parsing import work_type_from


class GreenhouseSource:
    name = "greenhouse"

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch_board(self, slug: str) -> list[JobPosting]:
        data = self.http.get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", content="true")
        return [JobPosting(
            source="greenhouse", ext_id=f"{slug}-{item['id']}", title=item["title"],
            company=item.get("company_name") or slug, url=item["absolute_url"],
            description=strip_html(html.unescape(item.get("content") or "")),
            location=(item.get("location") or {}).get("name", ""),
            work_type=work_type_from((item.get("location") or {}).get("name", "")),
            posted_at=to_iso(item.get("first_published") or item.get("updated_at")),
        ) for item in data.get("jobs", [])]
