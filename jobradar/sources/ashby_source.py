from __future__ import annotations

from ..domain.jobs.job_posting import JobPosting
from ..lib.http_client import HttpClient
from ..shared.utils.date_utils import to_iso
from ..shared.utils.text_utils import strip_html
from .source_parsing import work_type_from


class AshbySource:
    name = "ashby"

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch_board(self, slug: str) -> list[JobPosting]:
        data = self.http.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", includeCompensation="true")
        return [self._posting(slug, item) for item in data.get("jobs", []) if item.get("isListed", True)]

    @staticmethod
    def _posting(slug: str, item: dict) -> JobPosting:
        compensation = (item.get("compensation") or {}).get("scrapeableCompensationSalarySummary") or ""
        locations = [item.get("location")] + [s.get("location") for s in item.get("secondaryLocations") or []]
        return JobPosting(
            source="ashby", ext_id=item["id"], title=item["title"], company=slug, url=item["jobUrl"],
            description=item.get("descriptionPlain") or strip_html(item.get("descriptionHtml")),
            location=", ".join(filter(None, locations)),
            salary_text=compensation, employment_type=item.get("employmentType") or "",
            remote=item.get("isRemote"),
            work_type=work_type_from(item.get("workplaceType")) or ("remote" if item.get("isRemote") else ""),
            posted_at=to_iso(item.get("publishedAt")),
        )
