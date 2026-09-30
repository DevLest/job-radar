from __future__ import annotations

from dataclasses import dataclass, field

from .job_posting import JobPosting

# stage: new -> rejected | queued -> batched -> scored; duplicates never leave "duplicate".
HIDDEN = "ignored"


@dataclass
class Job(JobPosting):
    """A stored job and its place in the funnel."""
    fingerprint: str = ""
    first_seen: str | None = None
    stage: str = "new"
    reject_reason: str | None = None
    batch_id: str | None = None
    kw_score: float | None = None
    score: int | None = None
    verdict: str | None = None
    analysis: dict = field(default_factory=dict)
    status: str = ""
    notes: str = ""

    @property
    def is_rated(self) -> bool:
        return self.score is not None

    @property
    def is_hidden(self) -> bool:
        return self.status == HIDDEN

    def hide(self):
        self.status = HIDDEN

    def unhide(self):
        self.status = ""

    def queue(self, keyword_score: float):
        self.stage, self.reject_reason, self.kw_score = "queued", None, keyword_score

    def reject(self, reason: str, keyword_score: float):
        self.stage, self.reject_reason, self.kw_score = "rejected", reason, keyword_score

    def pick_manually(self):
        """You picked it yourself: skip the free filter and go straight to the rating queue."""
        self.stage, self.kw_score = "queued", 99

    def mark_batched(self, batch_id: str):
        self.stage, self.batch_id = "batched", batch_id

    def requeue(self):
        self.stage, self.batch_id = "queued", None

    def record_score(self, result: dict) -> tuple[str, ...]:
        """Store Claude's assessment; returns the fields that changed. A failed rating keeps
        any earlier score but marks the verdict as an error."""
        self.stage, self.analysis = "scored", result
        if "error" in result:
            self.verdict = "error"
            return "stage", "verdict", "analysis"
        self.score, self.verdict = result["score"], result["verdict"]
        return "stage", "score", "verdict", "analysis"
