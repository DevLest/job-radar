"""Job -> the compact plain text Claude sees (scoring and drafts)."""

from __future__ import annotations

from .job import Job

DEFAULT_MAX_DESCRIPTION = 3500


def _location(job: Job, profile: dict) -> str:
    location = job.location or "not stated"
    if len(location) > 200:  # long country allow-lists: keep the one that matters
        home = ((profile.get("candidate") or {}).get("based_in") or "").lower()
        countries = location.count(",") + 1
        included = "INCLUDING" if home and home in location.lower() else "NOT including"
        location = f"{countries} countries, {included} {home or 'candidate country'}"
    return location


def _salary(job: Job) -> str:
    if job.salary_min or job.salary_max:
        return f"{job.salary_min or '?'}-{job.salary_max or '?'} {job.currency or ''} per {job.salary_period}"
    return job.salary_text or ""


def to_prompt_text(job: Job, profile: dict) -> str:
    cap = (profile.get("claude") or {}).get("max_description_chars", DEFAULT_MAX_DESCRIPTION)
    description = job.description or ""
    if len(description) > cap:
        description = description[:cap] + " [truncated]"
    tags = ", ".join(tag for tag in job.tags if tag)
    work_type = job.work_type or {1: "remote", 0: "not remote"}.get(job.remote, "not stated")
    return (f"TITLE: {job.title}\nCOMPANY: {job.company or 'not stated'}\nLOCATION: {_location(job, profile)}\n"
            f"WORK TYPE: {work_type}\nEMPLOYMENT: {job.employment_type or 'not stated'}\n"
            f"SALARY: {_salary(job) or 'not stated'}\nTAGS: {tags or '-'}\n\nDESCRIPTION:\n{description}")
