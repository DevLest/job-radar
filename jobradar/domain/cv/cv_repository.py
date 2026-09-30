from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ...lib.database import Database
from ...shared.utils.date_utils import now_iso


@dataclass
class CvRecord:
    id: int
    filename: str
    path: str
    uploaded_at: str
    text: str
    analysis: dict

    @property
    def file(self) -> Path:
        return Path(self.path)


class CvRepository:
    def __init__(self, db: Database):
        self.db = db

    def active(self) -> CvRecord | None:
        row = self.db.one("SELECT * FROM cvs WHERE active=1 ORDER BY id DESC LIMIT 1")
        if not row:
            return None
        return CvRecord(id=row["id"], filename=row["filename"], path=row["path"], uploaded_at=row["uploaded_at"],
                        text=row["text"], analysis=json.loads(row["analysis"] or "{}"))

    def add_active(self, path: Path, text: str, analysis: dict):
        """The newest upload becomes the only active CV."""
        self.db.execute("UPDATE cvs SET active=0")
        self.db.execute("INSERT INTO cvs (filename, path, uploaded_at, text, analysis, active) VALUES (?,?,?,?,?,1)",
                        (path.name, str(path), now_iso(), text, json.dumps(analysis)))
