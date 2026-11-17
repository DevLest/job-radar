from __future__ import annotations

from ..domain.jobs.job_posting import JobPosting
from ..lib.http_client import HttpClient
from ..shared.utils.date_utils import to_iso
from ..shared.utils.text_utils import strip_html
from .job_source import SourceQuery
from .source_parsing import keep_result, to_number

SEARCH_URL = "https://www.kalibrr.com/kjs/job_board/search"
PAGE_SIZE = 100


class KalibrrSource:
    """Kalibrr's public job search, Philippine jobs only. Unlike the other local sites it returns the
    full posting with structured pay and work arrangement, so these jobs are scored on complete info."""
    name = "kalibrr"

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch(self, query: SourceQuery) -> list[JobPosting]:
        results = {}
        for term in query.terms_or_all:
            data = self.http.get_json(SEARCH_URL, limit=PAGE_SIZE, offset=0, text=term, country="Philippines")
            for item in data.get("jobs", []):
                posting = self._posting(item)
                if posting.work_type in query.work_types:
                    keep_result(results, term, posting)
        return list(results.values())

    @staticmethod
    def _posting(item: dict) -> JobPosting:
        work_type = "remote" if item.get("is_work_from_home") else "hybrid" if item.get("is_hybrid") else "onsite"
        address = ((item.get("google_location") or {}).get("address_components") or {})
        location = ", ".join(part for part in (address.get("city"), address.get("region")) if part)
        company = item.get("company") or {}
        shown = item.get("salary_shown")
        return JobPosting(
            source="kalibrr", ext_id=str(item["id"]), title=item.get("name", ""),
            company=item.get("company_name") or company.get("name", ""),
            url=f"https://www.kalibrr.com/c/{company.get('code', '')}/jobs/{item['id']}/{item.get('slug', '')}",
            description=strip_html((item.get("description") or "") + "\n" + (item.get("qualifications") or "")),
            location=f"{location}, Philippines" if location else "Philippines",
            tags=[item["function"]] if item.get("function") else [],
            salary_min=to_number(item.get("base_salary")) if shown else None,
            salary_max=to_number(item.get("maximum_salary")) if shown else None,
            salary_period=item.get("salary_interval") or "month", currency=item.get("salary_currency") or "PHP",
            employment_type=item.get("tenure") or "", remote=work_type == "remote", work_type=work_type,
            posted_at=to_iso(item.get("activation_date")),
        )
