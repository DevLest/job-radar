from __future__ import annotations

from dataclasses import dataclass

from .application_status import ACTIVE, ALWAYS_ACCEPTED, FORWARD_RANK, LABELS


@dataclass
class Application:
    id: int
    job_id: str | None = None
    fingerprint: str | None = None
    company: str | None = None
    title: str | None = None
    url: str | None = None
    status: str = "drafted"
    method: str | None = None
    to_email: str | None = None
    subject: str | None = None
    body: str | None = None
    sent_message_id: str | None = None
    created_at: str | None = None
    applied_at: str | None = None
    last_checked: str | None = None
    last_update: str | None = None
    next_action: str | None = ""
    notes: str | None = ""

    @property
    def status_label(self) -> str:
        return LABELS[self.status]

    @property
    def is_draft(self) -> bool:
        return self.status == "drafted"

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE

    def move_to(self, status: str, when: str) -> tuple[str, ...]:
        """Set the status; returns the changed fields. The first move to 'applied' stamps applied_at."""
        changed = ["status", "last_update"]
        self.status, self.last_update = status, when
        if status == "applied" and not self.applied_at:
            self.applied_at = when
            changed.append("applied_at")
        return tuple(changed)

    def accepts_automatic(self, status: str) -> bool:
        """Emails may only move an application forward (or close it with an offer / rejection)."""
        return status in ALWAYS_ACCEPTED or FORWARD_RANK.get(status, 0) > FORWARD_RANK.get(self.status, 0)

    @staticmethod
    def move_summary(status: str, note: str = "") -> str:
        return f"Moved to {LABELS[status]}" + (f" - {note}" if note else "")
