from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..jobs.job_repository import JobRepository
from .usage_repository import UsageRepository

PURPOSE_LABELS = {"score": "Rating jobs", "alerts": "Reading alert emails", "cv": "Analyzing your CV",
                  "draft": "Writing applications", "updates": "Reading employer replies"}
FUNNEL_STEPS = [("scored", "Rated by AI"), ("queued", "Waiting for rating"), ("batched", "Being rated (half price)"),
                ("rejected", "Skipped by your filters"), ("duplicate", "Duplicates")]


@dataclass
class FeatureCost:
    label: str
    model: str
    calls: int
    usd: float

    @property
    def per_call(self) -> float:
        return self.usd / self.calls


@dataclass
class FunnelStep:
    label: str
    count: int
    percent: float


@dataclass
class UsagePage:
    features: list[FeatureCost]
    month: float
    skipped_free: int
    funnel: list[FunnelStep]
    reasons: list[tuple[str, int]]


class UsageService:
    def __init__(self, usage: UsageRepository, jobs: JobRepository):
        self.usage, self.jobs = usage, jobs

    def page(self) -> UsagePage:
        features = [FeatureCost(PURPOSE_LABELS.get(row["purpose"], row["purpose"]), row["model"], row["calls"],
                                row["usd"] or 0) for row in self.usage.by_feature()]
        month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
        stages = self.jobs.stage_counts()
        total = sum(stages.values()) or 1
        funnel = [FunnelStep(label, stages[key], round(stages[key] / total * 100, 0))
                  for key, label in FUNNEL_STEPS if stages.get(key)]
        return UsagePage(features=features, month=self.usage.spent_since(month_start),
                         skipped_free=stages.get("rejected", 0) + stages.get("duplicate", 0),
                         funnel=funnel, reasons=self.jobs.top_reject_reasons())
