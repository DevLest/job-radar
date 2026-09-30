"""Applications: draft (Claude), review, send (you click Send), track, and check for replies.

Nothing is ever sent automatically. Update checks are cheap: replies to an email we sent are
matched by Message-ID for free; other emails are only sent to Claude when they mention the
company, arrived after you applied, and were not seen before."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from . import cv, llm, mailer
from .db import fingerprint, now
from .scorer import job_text

LABELS = {"drafted": "Draft", "applied": "Applied", "acknowledged": "Heard back", "assessment": "Assessment",
          "interview": "Interview", "offer": "Offer", "rejected": "Rejected", "withdrawn": "Withdrawn"}
STATUSES = ["drafted", "applied", "acknowledged", "assessment", "interview", "offer", "rejected", "withdrawn"]
ACTIVE = ("applied", "acknowledged", "assessment", "interview")
RANK = {"applied": 1, "acknowledged": 2, "assessment": 3, "interview": 4, "offer": 5}
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Big job sites block or fake 200s for bots, so "is the posting still up?" only works elsewhere.
NO_POSTING_CHECK = {"linkedin", "indeed", "jobstreet", "onlinejobs", "hackernews", "manual"}

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "body": {"type": "string", "description": "Plain-text email body / cover letter, 140-220 words"},
        "key_points": {"type": "array", "items": {"type": "string"}, "description": "Why this candidate fits (max 4)"},
    },
    "required": ["subject", "body", "key_points"],
    "additionalProperties": False,
}

UPDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "related": {"type": "boolean", "description": "Is this email about this specific application?"},
        "status": {"type": "string", "enum": ["acknowledged", "assessment", "interview", "offer", "rejected",
                                              "info_request", "other"]},
        "summary": {"type": "string", "description": "One sentence"},
        "action_needed": {"type": "string", "description": "What the candidate should do next, or empty"},
    },
    "required": ["related", "status", "summary", "action_needed"],
    "additionalProperties": False,
}


def get(db, app_id: int):
    return db.one("SELECT * FROM applications WHERE id=?", (app_id,))


def for_job(db, job_id: str):
    return db.one("SELECT * FROM applications WHERE job_id=? ORDER BY id DESC LIMIT 1", (job_id,))


def prior(db, job) -> list:
    """Applications (other than drafts for this very job) to the same role or the same company."""
    fp = fingerprint(job["company"], job["title"])
    company = (job["company"] or "").strip().lower()
    return db.q("SELECT * FROM applications WHERE status!='drafted' AND job_id!=? AND "
                "(fingerprint=? OR (?!='' AND lower(company)=?)) ORDER BY applied_at DESC",
                (job["id"], fp, company, company))


def event(db, app_id: int, kind: str, summary: str, message_id: str | None = None):
    db.exec("INSERT INTO app_events (application_id, ts, kind, summary, message_id) VALUES (?,?,?,?,?)",
            (app_id, now(), kind, summary, message_id))


def events(db, app_id: int):
    return db.q("SELECT * FROM app_events WHERE application_id=? ORDER BY ts DESC, id DESC", (app_id,))


def set_status(db, app_id: int, status: str, note: str = "", kind: str = "status"):
    app = get(db, app_id)
    fields = {"status": status, "last_update": now()}
    if status == "applied" and not app["applied_at"]:
        fields["applied_at"] = now()
    sets = ",".join(f"{k}=?" for k in fields)
    db.exec(f"UPDATE applications SET {sets} WHERE id=?", (*fields.values(), app_id))
    if app["job_id"]:
        db.update(app["job_id"], status=status)
    event(db, app_id, kind, f"Moved to {LABELS[status]}" + (f" - {note}" if note else ""))


def ensure(db, job) -> int:
    """The application row for a job, created as a draft if needed."""
    app = for_job(db, job["id"])
    if app:
        return app["id"]
    return db.exec("INSERT INTO applications (job_id, fingerprint, company, title, url, status, created_at) "
                   "VALUES (?,?,?,?,?,'drafted',?)",
                   (job["id"], fingerprint(job["company"], job["title"]), job["company"], job["title"], job["url"], now()))


def emails_in_posting(job) -> list[str]:
    found = EMAIL_RE.findall(job["description"] or "")
    return [e.rstrip(".") for e in dict.fromkeys(found) if not e.lower().endswith((".png", ".jpg"))]


def draft(db, profile: dict, job) -> int:
    c = cv.active(db)
    if not c:
        raise ValueError("Upload your CV first (CV page) - drafts are written from it.")
    app_cfg = profile.get("applications") or {}
    cand = profile.get("candidate") or {}
    system = [{"type": "text", "cache_control": {"type": "ephemeral"}, "text": (
        "You write job application emails for this candidate. Rules: plain text, no markdown; 140-220 words; "
        "open with the exact role; 2-3 concrete, verifiable matches between the CV and the posting; never invent "
        "experience, numbers or skills not in the CV; mention the CV is attached; end with availability and the "
        f"candidate's name. Tone: {app_cfg.get('tone', 'professional, warm, concise')}.\n"
        f"Signature to use:\n{app_cfg.get('sender_signature') or cand.get('name', '')}\n\nCANDIDATE CV:\n{c['text'][:20000]}")}]
    analysis = json.loads(job["analysis"] or "{}")
    content = job_text(job, profile) + (f"\n\nFIT NOTES: {analysis.get('summary', '')} "
                                        f"Matched: {', '.join(analysis.get('matched_skills', []))}" if analysis else "")
    d = llm.ask(db, "draft", profile, system, content, DRAFT_SCHEMA, max_tokens=6000, effort="medium")
    app_id = ensure(db, job)
    to = (emails_in_posting(job) or [""])[0]
    db.exec("UPDATE applications SET subject=?, body=?, to_email=COALESCE(NULLIF(to_email,''), ?) WHERE id=?",
            (d["subject"], d["body"], to, app_id))
    event(db, app_id, "draft", "Draft written: " + "; ".join(d["key_points"]))
    return app_id


def save_draft(db, app_id: int, to_email: str, subject: str, body: str, notes: str | None = None):
    db.exec("UPDATE applications SET to_email=?, subject=?, body=? WHERE id=?", (to_email, subject, body, app_id))
    if notes is not None:
        db.exec("UPDATE applications SET notes=? WHERE id=?", (notes, app_id))


def send(db, app_id: int, attach_cv: bool = True) -> str:
    app = get(db, app_id)
    if not (app["to_email"] and EMAIL_RE.fullmatch(app["to_email"].strip())):
        raise ValueError("Enter a valid recipient email address.")
    if not (app["subject"] and app["body"]):
        raise ValueError("Subject and message are required.")
    c = cv.active(db)
    mid = mailer.send(app["to_email"].strip(), app["subject"], app["body"],
                      Path(c["path"]) if (attach_cv and c) else None)
    db.exec("UPDATE applications SET method='email', sent_message_id=? WHERE id=?", (mid, app_id))
    event(db, app_id, "sent", f"Emailed {app['to_email']}", mid)
    set_status(db, app_id, "applied", "sent by email")
    return mid


def mark_applied(db, app_id: int, method: str = "website"):
    db.exec("UPDATE applications SET method=? WHERE id=?", (method, app_id))
    set_status(db, app_id, "applied", f"via {method}")


# --- update checks -----------------------------------------------------------

def _classify(db, profile: dict, app, msg) -> dict:
    text, _ = mailer.readable(msg)
    content = (f"APPLICATION: {app['title']} at {app['company']} (applied {(app['applied_at'] or '')[:10]})\n\n"
               f"EMAIL FROM: {msg.get('From', '')}\nSUBJECT: {msg.get('Subject', '')}\nDATE: {msg.get('Date', '')}\n\n"
               f"{text[:2500]}")
    system = ("You triage emails for a job seeker. Decide if the email is about the given application "
              "(same company; job alerts, newsletters and marketing are NOT related) and what it means.")
    return llm.ask(db, "updates", profile, system, content, UPDATE_SCHEMA, max_tokens=2000)


def _apply_update(db, app, result: dict, mid: str):
    event(db, app["id"], "email_in", result["summary"] + (f" -> {result['action_needed']}" if result["action_needed"] else ""), mid)
    new = result["status"]
    if result["action_needed"]:
        db.exec("UPDATE applications SET next_action=? WHERE id=?", (result["action_needed"], app["id"]))
    if new in ("rejected", "offer") or RANK.get(new, 0) > RANK.get(app["status"], 0):
        set_status(db, app["id"], new, "from email", kind="auto")
    db.exec("UPDATE applications SET last_update=? WHERE id=?", (now(), app["id"]))


def check_emails(db, profile: dict, log=print, per_app: int = 5):
    apps = db.q(f"SELECT * FROM applications WHERE status IN ({','.join('?' * len(ACTIVE))})", ACTIVE)
    if not apps:
        log("  no active applications to check")
        return
    alert_senders = [n for v in ((profile.get("email_alerts") or {}).get("senders") or {}).values() for n in v]
    me = mailer.my_address().lower()
    with mailer.imap() as m:
        for app in apps:
            since = datetime.fromisoformat(app["applied_at"] or app["created_at"]) - timedelta(days=1)
            nums = set()
            if app["sent_message_id"]:  # direct replies: exact and free
                nums.update(mailer.search(m, f"(HEADER In-Reply-To {mailer.quote(app['sent_message_id'])})"))
            if app["company"] and len(app["company"]) >= 3:
                nums.update(mailer.search(m, f"(SINCE {mailer.imap_date(since)} TEXT {mailer.quote(app['company'])})"))
            checked = 0
            for num in sorted(nums, key=int, reverse=True):
                if checked >= per_app:
                    break
                msg = mailer.fetch(m, num)
                if msg is None:
                    continue
                mid = mailer.message_id(msg)
                sender = (msg.get("From") or "").lower()
                if db.seen_email(f"{app['id']}|{mid}") or (me and me in sender) or any(n.lower() in sender for n in alert_senders):
                    continue
                db.mark_email(f"{app['id']}|{mid}", "update", app["company"] or "")
                is_reply = bool(app["sent_message_id"]) and app["sent_message_id"] in (msg.get("In-Reply-To") or "")
                checked += 1
                try:
                    result = _classify(db, profile, app, msg)
                except llm.LLMError as e:
                    log(f"  could not classify email for {app['company']}: {e}")
                    continue
                if result["related"] or is_reply:
                    _apply_update(db, app, result, mid)
                    log(f"  {app['company']}: {result['status']} - {result['summary'][:80]}")
            db.exec("UPDATE applications SET last_checked=? WHERE id=?", (now(), app["id"]))


def check_postings(db, log=print):
    """Flag applications whose posting disappeared (404/410). Free - no tokens."""
    rows = db.q("SELECT a.*, j.source FROM applications a LEFT JOIN jobs j ON j.id=a.job_id "
                f"WHERE a.status IN ({','.join('?' * len(ACTIVE))}) AND a.url != ''", ACTIVE)
    with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": "job-radar/0.1"}) as http:
        for r in rows:
            if r["source"] in NO_POSTING_CHECK:
                continue
            if db.one("SELECT 1 FROM app_events WHERE application_id=? AND kind='posting_closed'", (r["id"],)):
                continue
            try:
                code = http.get(r["url"]).status_code
            except httpx.HTTPError:
                continue
            if code in (404, 410):
                event(db, r["id"], "posting_closed", f"Job posting is no longer online (HTTP {code})")
                log(f"  {r['company']}: posting closed")


def check_updates(db, profile: dict, log=print):
    if mailer.imap_configured():
        check_emails(db, profile, log)
    else:
        log("  mailbox not configured - skipping reply check")
    check_postings(db, log)
    stale = datetime.now(timezone.utc) - timedelta(days=14)
    for a in db.q("SELECT * FROM applications WHERE status='applied' AND applied_at < ? AND "
                  "(next_action IS NULL OR next_action='')", (stale.isoformat(),)):
        db.exec("UPDATE applications SET next_action=? WHERE id=?", ("No reply in 14 days - consider a follow-up", a["id"]))
