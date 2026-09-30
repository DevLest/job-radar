"""One alert email -> job postings, read by Claude. Links are sent as short [Ln] references."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from ...lib import mail_client
from ...lib.email_text import readable
from ...lib.llm_client import LlmClient
from ...shared.utils.hash_utils import short_hash
from ..jobs.job_posting import JobPosting, remote_flag
from .alert_links import canonical

MAX_EMAIL_CHARS = 14000
SNIPPET_NOTE = "\n\n(From a {provider} job alert email - only a snippet is available; open the link for the full posting.)"

SCHEMA = {
    "type": "object",
    "properties": {
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "location": {"type": "string"},
                    "work_type": {"type": "string", "enum": ["remote", "hybrid", "onsite", "unknown"]},
                    "salary": {"type": "string", "description": "As written, or empty"},
                    "employment_type": {"type": "string", "description": "full-time / part-time / contract..., or empty"},
                    "snippet": {"type": "string", "description": "Any description text shown for this job, max 300 chars"},
                    "link": {"type": "string", "description": "The Ln reference of the job's link, e.g. L12, or empty"},
                },
                "required": ["title", "company", "location", "work_type", "salary", "employment_type", "snippet", "link"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["jobs"],
    "additionalProperties": False,
}

SYSTEM = """You extract job postings from job-alert emails (LinkedIn, Indeed, JobStreet, OnlineJobs.ph).
List every distinct job posting in the email, including "similar jobs" sections. Skip ads, courses,
articles, profile tips and navigation. Links appear as [text](Ln); return the Ln of each job's own link.
Copy text as written; never invent a company, salary or location. Use empty strings when absent."""


class AlertExtractor:
    def __init__(self, llm: LlmClient):
        self.llm = llm

    def extract(self, profile: dict, provider: str, message) -> list[JobPosting]:
        text, links = readable(message, keep_links=True)
        if len(text) > MAX_EMAIL_CHARS:
            text = text[:MAX_EMAIL_CHARS] + "\n[email truncated]"
        content = f"PROVIDER: {provider}\nSUBJECT: {message.get('Subject', '')}\n\n{text}"
        data = self.llm.ask("alerts", profile, SYSTEM, content, SCHEMA, max_tokens=8000)
        received = mail_client.message_date(message)
        posted = (received or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        return [self._posting(provider, item, links, posted) for item in data["jobs"] if item["title"].strip()]

    @staticmethod
    def _posting(provider: str, item: dict, links: list[str], posted: str) -> JobPosting:
        ref = re.fullmatch(r"L(\d+)", item["link"].strip())
        href = links[int(ref.group(1)) - 1] if ref and int(ref.group(1)) <= len(links) else ""
        url, ext_id = canonical(provider, href) if href else ("", None)
        if not ext_id:
            ext_id = short_hash(f"{item['company']}|{item['title']}|{item['location']}".lower())
        work_type = "" if item["work_type"] == "unknown" else item["work_type"]
        return JobPosting(
            source=provider, ext_id=ext_id, title=item["title"].strip(), company=item["company"].strip(), url=url,
            description=(item["snippet"] + SNIPPET_NOTE.format(provider=provider)).strip(),
            location=item["location"], salary_text=item["salary"], employment_type=item["employment_type"],
            remote=remote_flag(work_type), work_type=work_type, posted_at=posted)
