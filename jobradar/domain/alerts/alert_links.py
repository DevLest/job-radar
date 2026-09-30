"""Tracking-wrapped links in alert emails -> the job's canonical URL and stable id."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

JOB_LINKS = {
    "linkedin": (re.compile(r"linkedin\.com/(?:comm/)?jobs/view/(\d+)"), "https://www.linkedin.com/jobs/view/{}"),
    "jobstreet": (re.compile(r"jobstreet\.com(?:\.ph)?/(?:[a-z-]+/)*job/(\d+)"), "https://ph.jobstreet.com/job/{}"),
    "onlinejobs": (re.compile(r"onlinejobs\.ph/jobseekers/job/([\w-]+)"), "https://www.onlinejobs.ph/jobseekers/job/{}"),
}
INDEED_KEY = re.compile(r"jk=([0-9a-f]{16})")


def _indeed(href: str) -> tuple[str, str | None]:
    parsed = urlparse(href)
    job_key = parse_qs(parsed.query).get("jk")
    if job_key:
        host = parsed.netloc if "indeed." in parsed.netloc else "www.indeed.com"
        return f"https://{host}/viewjob?jk={job_key[0]}", job_key[0]
    match = INDEED_KEY.search(href)
    return (f"https://www.indeed.com/viewjob?jk={match.group(1)}", match.group(1)) if match else (href, None)


def canonical(provider: str, href: str) -> tuple[str, str | None]:
    """(url, stable id or None). Unwraps provider job ids from tracking links when present."""
    if provider == "indeed":
        return _indeed(href)
    pattern = JOB_LINKS.get(provider)
    if pattern:
        match = pattern[0].search(href)
        if match:
            return pattern[1].format(match.group(1)), match.group(1)
    return href, None


def provider_of(sender: str, senders: dict) -> str | None:
    lowered = sender.lower()
    for provider, needles in senders.items():
        if any(needle.lower() in lowered for needle in needles):
            return provider
    return None
