from __future__ import annotations

from ...shared.utils.format_utils import money
from .job import Job
from .job_labels import METER_PERCENT, fit_tone, fit_word, meter_tone, verdict_word
from .job_view import AppliedBadge, Chip, JobCardView, JobDetailView, Meter

CARD_PAY_CHARS = 40
CARD_LOCATION_CHARS = 48
CARD_SKILLS = 4
COLLAPSE_DESCRIPTION_AT = 600


def pay_label(job: Job) -> str:
    """What the job pays, as Claude read it, as posted, or from the parsed range."""
    label = job.analysis.get("salary_stated") or job.salary_text
    if not label and job.salary_max:
        label = (f"{money(job.salary_min)}–{money(job.salary_max)} {job.currency or ''} / {job.salary_period}")
    return (label or "").strip()


def fit_chips(analysis: dict) -> list[Chip]:
    chips = []
    for kind, hidden in (("rate_fit", ("unclear", "not_stated")), ("setup_fit", ("unclear",))):
        value = analysis.get(kind)
        if value and value not in hidden:
            chips.append(Chip(fit_word(kind, value), fit_tone(value)))
    return chips


def meters(analysis: dict) -> list[Meter]:
    skills = analysis.get("skills_match")
    rows = [Meter("Your skills", skills, f"{skills}% match", meter_tone(skills))]
    for kind, label in (("rate_fit", "Pay"), ("setup_fit", "Work setup"), ("seniority_fit", "Experience level")):
        value = analysis.get(kind)
        percent = METER_PERCENT[kind].get(value, 50)
        rows.append(Meter(label, percent, fit_word(kind, value), meter_tone(percent)))
    return rows


def applied_badge(job: Job, applied_index: dict) -> AppliedBadge:
    same = applied_index["fp"].get(job.fingerprint)
    if same:
        return AppliedBadge(same_role_applied_at=same["applied_at"])
    return AppliedBadge(at_company=(job.company or "").lower() in applied_index["co"])


def to_card(job: Job, applied_index: dict) -> JobCardView:
    analysis = job.analysis
    location = job.location or ""
    skills = analysis.get("matched_skills") or []
    search = " ".join([job.title or "", job.company or "", location, " ".join(skills)]).lower()
    return JobCardView(
        id=job.id, title=job.title, company=job.company, posted_at=job.posted_at, source=job.source, url=job.url,
        location_short=location[:CARD_LOCATION_CHARS] + ("…" if len(location) > CARD_LOCATION_CHARS else ""),
        work_type=job.work_type, score=job.score, verdict=job.verdict, verdict_word=verdict_word(job.verdict),
        pay_short=pay_label(job)[:CARD_PAY_CHARS], fit_chips=fit_chips(analysis), top_skills=skills[:CARD_SKILLS],
        summary=analysis.get("summary", ""), reject_reason=job.reject_reason, is_hidden=job.is_hidden,
        can_rate=job.score is None and job.stage != "batched", applied=applied_badge(job, applied_index),
        search_text=search)


def to_detail(job: Job, emails: list[str]) -> JobDetailView:
    analysis = job.analysis
    view = JobDetailView(
        id=job.id, title=job.title, company=job.company, location=(job.location or "")[:90],
        posted_at=job.posted_at, source=job.source, url=job.url, work_type=job.work_type,
        employment_type=job.employment_type, score=job.score, verdict=job.verdict,
        verdict_word=verdict_word(job.verdict), status=job.status, reject_reason=job.reject_reason,
        pay=pay_label(job), description=job.description or "",
        description_collapsible=len(job.description or "") > COLLAPSE_DESCRIPTION_AT,
        error=analysis.get("error"), summary=analysis.get("summary", ""), emails=emails)
    if job.is_rated and not view.error:
        view.meters = meters(analysis)
        view.matched_skills = analysis.get("matched_skills") or []
        view.missing_skills = analysis.get("missing_skills") or []
        view.red_flags = analysis.get("red_flags") or []
    return view
