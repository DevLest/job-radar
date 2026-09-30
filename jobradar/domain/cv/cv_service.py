"""CV upload + analysis. The text is extracted locally (free) and analyzed once; the result can
fill in your profile, and the text is reused for application drafts."""

from __future__ import annotations

import base64
from pathlib import Path

from ...lib.llm_client import LlmClient
from ..preferences.profile_repository import ProfileRepository
from .cv_files import CvFileStore, extract_text
from .cv_profile_merge import apply_to_profile
from .cv_prompt import MAX_CV_CHARS, MIN_TEXT_CHARS, SCHEMA, SYSTEM
from .cv_repository import CvRecord, CvRepository


class CvService:
    def __init__(self, cvs: CvRepository, files: CvFileStore, llm: LlmClient, profiles: ProfileRepository):
        self.cvs, self.files, self.llm, self.profiles = cvs, files, llm, profiles

    def active(self) -> CvRecord | None:
        return self.cvs.active()

    def upload(self, filename: str, data: bytes) -> dict:
        path = self.files.save(filename, data)
        return self.analyze(path)

    def analyze(self, path: Path) -> dict:
        text = extract_text(path)
        analysis = self.llm.ask("cv", self.profiles.load(), SYSTEM, self._content(path, text), SCHEMA,
                                max_tokens=8000, effort="medium")
        self.cvs.add_active(path, text, analysis)
        return analysis

    @staticmethod
    def _content(path: Path, text: str):
        if len(text) >= MIN_TEXT_CHARS:
            return f"CV ({path.name}):\n\n{text[:MAX_CV_CHARS]}"
        if path.suffix.lower() == ".pdf":  # scanned PDF - let Claude read the pages directly
            return [{"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                    "data": base64.b64encode(path.read_bytes()).decode()}},
                    {"type": "text", "text": "Analyze this CV."}]
        raise ValueError("Could not read any text from this file.")

    def use_for_profile(self, replace_skills: bool) -> bool:
        cv = self.cvs.active()
        if not cv:
            return False
        self.profiles.save(apply_to_profile(self.profiles.load(), cv.analysis, replace_skills))
        return True
