from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from .profile_defaults import normalize


class ProfileRepository:
    """profile.yaml: pay, work style, skills and filters. Created from the example on first use."""

    def __init__(self, path: Path, example: Path):
        self.path, self.example = path, example

    @property
    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> dict:
        if not self.path.exists():
            shutil.copy(self.example, self.path)
        return normalize(yaml.safe_load(self.path.read_text(encoding="utf-8")) or {})

    def save(self, profile: dict):
        self.path.write_text(yaml.safe_dump(profile, sort_keys=False, allow_unicode=True, width=110),
                             encoding="utf-8")
