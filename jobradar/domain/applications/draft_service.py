"""Application drafts written by Claude from your CV. Never sent without you clicking Send."""

from __future__ import annotations

from ...lib.llm_client import LlmClient
from ..cv.cv_repository import CvRepository
from ..jobs.job import Job
from ..jobs.job_prompt_mapper import to_prompt_text
from .application_event_repository import ApplicationEventRepository
from .application_repository import ApplicationRepository
from .application_service import ApplicationService
from .contact_emails import emails_in

MAX_CV_CHARS = 20000
DEFAULT_TONE = "professional, warm, concise"

SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "body": {"type": "string", "description": "Plain-text email body / cover letter, 140-220 words"},
        "key_points": {"type": "array", "items": {"type": "string"}, "description": "Why this candidate fits (max 4)"},
    },
    "required": ["subject", "body", "key_points"],
    "additionalProperties": False,
}


def system_prompt(profile: dict, cv_text: str) -> list[dict]:
    settings = profile.get("applications") or {}
    candidate = profile.get("candidate") or {}
    return [{"type": "text", "cache_control": {"type": "ephemeral"}, "text": (
        "You write job application emails for this candidate. Rules: plain text, no markdown; 140-220 words; "
        "open with the exact role; 2-3 concrete, verifiable matches between the CV and the posting; never invent "
        "experience, numbers or skills not in the CV; mention the CV is attached; end with availability and the "
        f"candidate's name. Tone: {settings.get('tone', DEFAULT_TONE)}.\n"
        f"Signature to use:\n{settings.get('sender_signature') or candidate.get('name', '')}\n\n"
        f"CANDIDATE CV:\n{cv_text[:MAX_CV_CHARS]}")}]


def job_content(job: Job, profile: dict) -> str:
    analysis = job.analysis
    notes = (f"\n\nFIT NOTES: {analysis.get('summary', '')} "
             f"Matched: {', '.join(analysis.get('matched_skills', []))}") if analysis else ""
    return to_prompt_text(job, profile) + notes


class DraftService:
    def __init__(self, llm: LlmClient, cvs: CvRepository, applications: ApplicationRepository,
                 events: ApplicationEventRepository, lifecycle: ApplicationService):
        self.llm, self.cvs, self.applications, self.events, self.lifecycle = llm, cvs, applications, events, lifecycle

    def draft(self, profile: dict, job: Job) -> int:
        cv = self.cvs.active()
        if not cv:
            raise ValueError("Upload your CV first (CV page) - drafts are written from it.")
        result = self.llm.ask("draft", profile, system_prompt(profile, cv.text), job_content(job, profile), SCHEMA,
                              max_tokens=6000, effort="medium")
        app_id = self.lifecycle.ensure(job)
        self.applications.save_draft_text(app_id, result["subject"], result["body"], (emails_in(job.description) or [""])[0])
        self.events.add(app_id, "draft", "Draft written: " + "; ".join(result["key_points"]))
        return app_id
