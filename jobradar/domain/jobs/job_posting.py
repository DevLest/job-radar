from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JobPosting:
    """A job as a source reports it, before it is stored."""
    source: str
    ext_id: str
    title: str
    company: str
    url: str
    description: str = ""
    location: str = ""
    tags: list[str] = field(default_factory=list)
    salary_text: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_period: str = "year"          # hour | month | year
    currency: str = ""
    employment_type: str = ""
    remote: bool | None = None
    work_type: str = ""                  # remote | hybrid | onsite | "" (unknown)
    posted_at: str | None = None         # ISO-8601 UTC

    @property
    def id(self) -> str:
        return f"{self.source}:{self.ext_id}"


def remote_flag(work_type: str) -> bool | None:
    return True if work_type == "remote" else (False if work_type in ("hybrid", "onsite") else None)
