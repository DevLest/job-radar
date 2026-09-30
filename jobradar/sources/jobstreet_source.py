from __future__ import annotations

from ..domain.jobs.job_posting import JobPosting
from ..lib.http_client import HttpClient
from ..shared.utils.date_utils import to_iso
from .job_source import SourceQuery
from .source_parsing import SNIPPET_NOTE, keep_result, parse_salary, work_type_from

SEARCH_URL = "https://ph.jobstreet.com/api/jobsearch/v5/search"
# JobStreet's work-arrangement filter codes. It leaves on-site jobs unlabeled.
ARRANGEMENT_CODES = (("onsite", "1"), ("hybrid", "2"), ("remote", "3"))


class JobStreetSource:
    name = "jobstreet"

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch(self, query: SourceQuery) -> list[JobPosting]:
        # Only ask for the ways of working you accept.
        arrangements = ",".join(code for work_type, code in ARRANGEMENT_CODES if work_type in query.work_types)
        results = {}
        for term in query.terms_or_all:
            data = self.http.get_json(SEARCH_URL, siteKey="PH-Main", keywords=term, page=1, pageSize=100,
                                      sortmode="ListedDate", locale="en-PH", workarrangement=arrangements)
            for item in data.get("data", []):
                keep_result(results, term, self._posting(item))
        return list(results.values())

    @staticmethod
    def _posting(item: dict) -> JobPosting:
        low, high, period, currency = parse_salary(item.get("salaryLabel") or "")
        arrangement = (item.get("workArrangements") or {}).get("displayText") or ""
        locations = [location.get("label", "") for location in item.get("locations") or []]
        return JobPosting(
            source="jobstreet", ext_id=str(item["id"]), title=item.get("title", ""),
            company=item.get("companyName") or (item.get("advertiser") or {}).get("description", ""),
            url=f"https://ph.jobstreet.com/job/{item['id']}",
            description=(item.get("teaser") or "") + "\n" + "\n".join(item.get("bulletPoints") or [])
                        + SNIPPET_NOTE.format(site="JobStreet"),
            location=", ".join(locations + ["Philippines"]),
            tags=[c["subclassification"]["description"] for c in item.get("classifications") or []
                  if c.get("subclassification")],
            salary_text=item.get("salaryLabel") or "", salary_min=low, salary_max=high,
            salary_period=period, currency=currency, employment_type=", ".join(item.get("workTypes") or []),
            work_type=work_type_from(arrangement) if arrangement else "onsite", posted_at=to_iso(item.get("listingDate")),
        )
