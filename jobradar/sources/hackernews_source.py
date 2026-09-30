from __future__ import annotations

import re

from ..domain.jobs.job_posting import JobPosting
from ..lib.http_client import HttpClient
from ..shared.utils.date_utils import to_iso
from ..shared.utils.text_utils import strip_html
from .job_source import SourceQuery
from .source_parsing import work_type_from

ALGOLIA = "https://hn.algolia.com/api/v1"
THREAD_TITLE = "Ask HN: Who is hiring?"


class HackerNewsSource:
    """The monthly 'Who is hiring?' thread. Convention: first line is "Company | Role | Location | ..."."""
    name = "hackernews"

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch(self, query: SourceQuery) -> list[JobPosting]:
        hits = self.http.get_json(f"{ALGOLIA}/search_by_date", tags="story,author_whoishiring", hitsPerPage=10)["hits"]
        story = next((hit for hit in hits if hit["title"].startswith(THREAD_TITLE)), None)
        if not story:
            return []
        thread = self.http.get_json(f"{ALGOLIA}/items/{story['objectID']}")
        postings = []
        for comment in thread.get("children", []):
            text = strip_html(comment.get("text"))
            if text:
                postings.append(self._posting(comment, text))
        return postings

    @staticmethod
    def _posting(comment: dict, text: str) -> JobPosting:
        first_line = text.split("\n", 1)[0]
        parts = [part.strip() for part in first_line.split("|")]
        return JobPosting(
            source="hackernews", ext_id=str(comment["id"]),
            title=(" | ".join(parts[1:3]) if len(parts) > 1 else first_line)[:120],
            company=parts[0][:80], url=f"https://news.ycombinator.com/item?id={comment['id']}",
            description=text, location=" | ".join(parts[2:]) if len(parts) > 2 else "",
            remote=True if re.search(r"(?i)\bremote\b", first_line) else None,
            work_type=work_type_from(first_line), posted_at=to_iso(comment.get("created_at")),
        )
