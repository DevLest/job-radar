"""The .env file: secrets and mailbox settings. Never part of profile.yaml, because parts of
the profile are sent to Claude."""

from __future__ import annotations

import os
from pathlib import Path


class EnvFile:
    def __init__(self, path: Path, keys: list[str], defaults: dict[str, str]):
        self.path, self.keys, self.defaults = path, keys, defaults

    def load(self):
        """Load into os.environ without overriding variables already set in the shell."""
        for key, value in self.defaults.items():
            os.environ.setdefault(key, value)
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

    def values(self) -> dict[str, str]:
        return {key: os.environ.get(key, "") for key in self.keys}

    def write(self, values: dict[str, str]):
        self.path.write_text("".join(f"{k}={values[k]}\n" for k in self.keys if values.get(k)), encoding="utf-8")
        for key, value in values.items():
            if value:
                os.environ[key] = value
