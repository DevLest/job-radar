"""Job-alert emails from LinkedIn, Indeed, JobStreet and OnlineJobs.ph -> Job rows.

These sites forbid scraping, but they will happily email you alerts. We read those
emails (read-only) and have Claude list the jobs in each one. Token savings:
- each email is processed once (Message-ID remembered)
- HTML is flattened to text and every link is replaced by a short [Ln] reference
- the extracted list is small structured JSON
Alerts only contain a snippet, so scoring these jobs works on limited information.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from . import llm, mailer
from .sources import Job

MAX_EMAIL_CHARS = 14000

# Job-id patterns inside (possibly tracking-wrapped) links -> canonical URL.
JOB_LINKS = {
    "linkedin": (re.compile(r"linkedin\.com/(?:comm/)?jobs/view/(\d+)"), "https://www.linkedin.com/jobs/view/{}"),
    "jobstreet": (re.compile(r"jobstreet\.com(?:\.ph)?/(?:[a-z-]+/)*job/(\d+)"), "https://ph.jobstreet.com/job/{}"),
    "onlinejobs": (re.compile(r"onlinejobs\.ph/jobseekers/job/([\w-]+)"), "https://www.onlinejobs.ph/jobseekers/job/{}"),
}

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


def canonical(provider: str, href: str) -> tuple[str, str | None]:
    """(url, stable id or None). Unwraps provider job ids from tracking links when present."""
    if provider == "indeed":
        jk = parse_qs(urlparse(href).query).get("jk")
        if jk:
            host = urlparse(href).netloc if "indeed." in urlparse(href).netloc else "www.indeed.com"
            return f"https://{host}/viewjob?jk={jk[0]}", jk[0]
        m = re.search(r"jk=([0-9a-f]{16})", href)
        return (f"https://www.indeed.com/viewjob?jk={m.group(1)}", m.group(1)) if m else (href, None)
    pat = JOB_LINKS.get(provider)
    if pat:
        m = pat[0].search(href)
        if m:
            return pat[1].format(m.group(1)), m.group(1)
    return href, None


def _provider(sender: str, senders: dict) -> str | None:
    s = sender.lower()
    for provider, needles in senders.items():
        if any(n.lower() in s for n in needles):
            return provider
    return None


def extract(db, profile: dict, provider: str, msg) -> list[Job]:
    text, links = mailer.readable(msg, keep_links=True)
    if len(text) > MAX_EMAIL_CHARS:
        text = text[:MAX_EMAIL_CHARS] + "\n[email truncated]"
    content = f"PROVIDER: {provider}\nSUBJECT: {msg.get('Subject', '')}\n\n{text}"
    data = llm.ask(db, "alerts", profile, SYSTEM, content, SCHEMA, max_tokens=8000)
    when = mailer.message_date(msg)
    posted = (when or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    jobs = []
    for j in data["jobs"]:
        if not j["title"].strip():
            continue
        ref = re.fullmatch(r"L(\d+)", j["link"].strip())
        href = links[int(ref.group(1)) - 1] if ref and int(ref.group(1)) <= len(links) else ""
        url, ext = canonical(provider, href) if href else ("", None)
        if not ext:
            ext = hashlib.sha1(f"{j['company']}|{j['title']}|{j['location']}".lower().encode()).hexdigest()[:16]
        wt = "" if j["work_type"] == "unknown" else j["work_type"]
        jobs.append(Job(
            source=provider, ext_id=ext, title=j["title"].strip(), company=j["company"].strip(), url=url,
            description=(j["snippet"] + f"\n\n(From a {provider} job alert email - only a snippet is available;"
                                        " open the link for the full posting.)").strip(),
            location=j["location"], salary_text=j["salary"], employment_type=j["employment_type"],
            remote=True if wt == "remote" else (False if wt in ("hybrid", "onsite") else None),
            work_type=wt, posted_at=posted,
        ))
    return jobs


def ingest(db, profile: dict, log=print) -> list[Job]:
    cfg = profile.get("email_alerts") or {}
    if not cfg.get("enabled", True):
        log("  email alerts disabled in profile")
        return []
    senders = cfg.get("senders") or {}
    since = mailer.imap_date(datetime.now() - timedelta(days=cfg.get("lookback_days", 7)))
    jobs: list[Job] = []
    with mailer.imap() as m:
        for provider, needles in senders.items():
            nums = set()
            for n in needles:
                nums.update(mailer.search(m, f"(SINCE {since} FROM {mailer.quote(n)})"))
            found = 0
            for num in sorted(nums, key=int):
                msg = mailer.fetch(m, num)
                if msg is None:
                    continue
                mid = mailer.message_id(msg)
                if db.seen_email(mid):
                    continue
                if _provider(msg.get("From", ""), senders) != provider:
                    continue
                try:
                    got = extract(db, profile, provider, msg)
                except llm.LLMError as e:
                    log(f"  {provider}: could not read '{msg.get('Subject', '')[:50]}': {e}")
                    continue
                db.mark_email(mid, "alert", f"{provider}: {len(got)} jobs")
                jobs += got
                found += len(got)
            log(f"  {provider:<11} {len(nums):>3} emails -> {found} jobs")
    return jobs
