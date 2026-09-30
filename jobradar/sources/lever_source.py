from __future__ import annotations

from ..domain.jobs.job_posting import JobPosting
from ..lib.http_client import HttpClient
from ..shared.utils.date_utils import to_iso
from .source_parsing import to_number, work_type_from

PERIODS = {"per-hour-wage": "hour", "per-month-salary": "month"}


class LeverSource:
    name = "lever"

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch_board(self, slug: str) -> list[JobPosting]:
        data = self.http.get_json(f"https://api.lever.co/v0/postings/{slug}", mode="json")
        return [self._posting(slug, item) for item in data]

    @staticmethod
    def _posting(slug: str, item: dict) -> JobPosting:
        categories = item.get("categories") or {}
        salary = item.get("salaryRange") or {}
        return JobPosting(
            source="lever", ext_id=item["id"], title=item["text"], company=slug, url=item["hostedUrl"],
            description="\n".join(filter(None, [item.get("descriptionPlain"), item.get("additionalPlain")])),
            location=", ".join(categories.get("allLocations") or [categories.get("location") or ""]),
            employment_type=categories.get("commitment") or "",
            salary_min=to_number(salary.get("min")), salary_max=to_number(salary.get("max")),
            currency=salary.get("currency") or "", salary_period=PERIODS.get(salary.get("interval"), "year"),
            remote=(item.get("workplaceType") == "remote") if item.get("workplaceType") else None,
            work_type=work_type_from(item.get("workplaceType")),
            posted_at=to_iso(item.get("createdAt")),
        )
