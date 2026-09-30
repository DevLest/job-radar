"""Application statuses, the board columns they appear in, and timeline event vocabulary."""

STATUSES = ["drafted", "applied", "acknowledged", "assessment", "interview", "offer", "rejected", "withdrawn"]
LABELS = {"drafted": "Draft", "applied": "Applied", "acknowledged": "Heard back", "assessment": "Assessment",
          "interview": "Interview", "offer": "Offer", "rejected": "Rejected", "withdrawn": "Withdrawn"}
ACTIVE = ("applied", "acknowledged", "assessment", "interview")
CLOSED = ("rejected", "withdrawn")
# Automatic updates (from emails) only move forward along this order.
FORWARD_RANK = {"applied": 1, "acknowledged": 2, "assessment": 3, "interview": 4, "offer": 5}
ALWAYS_ACCEPTED = ("rejected", "offer")
TRACK = ["applied", "acknowledged", "assessment", "interview", "offer"]

# key, title, statuses shown in the column, icon
BOARD = [("drafted", "Drafts", ["drafted"], "pen"), ("applied", "Applied", ["applied"], "send"),
         ("acknowledged", "Heard back", ["acknowledged", "assessment"], "inbox"),
         ("interview", "Interview", ["interview"], "calendar"), ("offer", "Offer", ["offer"], "star"),
         ("rejected", "Closed", ["rejected", "withdrawn"], "x")]

EVENT_ICONS = {"email_in": "mail", "sent": "send", "note": "pen", "posting_closed": "x", "draft": "sparkles"}
EVENT_LABELS = {"email_in": "Email received", "sent": "Sent", "note": "Note", "posting_closed": "Posting closed",
                "draft": "Draft written", "status": "Status", "auto": "Updated from email"}


def label(status: str) -> str:
    return LABELS[status]
