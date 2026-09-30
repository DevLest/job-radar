"""Local web UI (http://127.0.0.1:5000). Binds to localhost only."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, url_for

from . import applications as apps
from . import cv as cvmod
from . import llm, mailer, pipeline, scorer
from .db import DB
from .icons import icon
from .settings import DB_PATH, ENV_KEYS, SECRET_KEYS, env_values, load_env, load_profile, save_env, save_profile
from .sources import Job

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

CURRENCIES = ["USD", "PHP", "EUR", "GBP", "AUD", "SGD", "CAD", "JPY"]
WORK_CARDS = [("remote", "Remote", "Work from home, anywhere you're allowed", "globe"),
              ("hybrid", "Hybrid", "Some days in the office", "hybrid"),
              ("onsite", "On-site", "Full time at the office", "building")]
MODEL_CARDS = [("claude-opus-5-5", "Most accurate", "Opus 5.5 · ~$0.015 per job"),
               ("claude-sonnet-5-5", "Balanced", "Sonnet 5.5 · ~$0.008 per job"),
               ("claude-haiku-4-5", "Cheapest", "Haiku 4.5 · ~$0.003 per job")]

# Preferences page: tabs -> sections -> fields (dotted path, label, kind, options, help).
# kinds: text, textarea, int, float, select, tags (list), lines, switch (bool), pills/cards (multi),
#        radiocards (single choice), fx (currency table)
PREFS = [
    ("work", "Pay & work style", "wallet", [
        {"title": "How much do you want to earn?", "layout": "pay",
         "desc": "Jobs that clearly pay less than your minimum are skipped automatically - no AI cost.",
         "fields": [("rate.minimum", "Minimum", "float", None, ""), ("rate.target", "Target", "float", None, ""),
                    ("rate.currency", "Currency", "select", CURRENCIES, ""),
                    ("rate.per", "Per", "select", ["hour", "day", "month", "year"], "")]},
        {"title": "How do you want to work?", "desc": "Pick everything you're open to.",
         "fields": [("work_setup.work_types", "", "cards", WORK_CARDS, ""),
                    ("work_setup.onsite_locations", "Cities where hybrid / on-site is OK", "tags", None,
                     "Hybrid and on-site jobs in other cities are skipped. Type a city and press Enter."),
                    ("work_setup.employment_types", "Contract type", "pills",
                     ["full-time", "part-time", "contract", "freelance"], "")]},
        {"title": "Currency conversion", "collapsed": True,
         "desc": "Lets a salary in another currency be compared with yours. Approximate rates are fine.",
         "fields": [("rate.fx_to_rate_currency", "", "fx", None, "One per line: CURRENCY = value of 1 unit in your currency")]},
    ]),
    ("me", "About me & skills", "user", [
        {"title": "About you", "desc": "Tip: upload your CV and this fills itself in.", "grid": True,
         "fields": [("candidate.name", "Name", "text", None, ""), ("candidate.title", "Headline", "text", None, ""),
                    ("candidate.years_experience", "Years of experience", "float", None, ""),
                    ("candidate.seniority", "Level", "pills1", ["junior", "mid", "senior", "lead"], ""),
                    ("candidate.based_in", "Based in", "text", None, ""), ("candidate.timezone", "Timezone", "text", None, ""),
                    ("candidate.languages_spoken", "Languages", "tags", None, ""),
                    ("candidate.summary", "Short summary", "textarea", None, "")]},
        {"title": "Your skills", "desc": "Type a skill and press Enter. Use the words job ads use (e.g. 'laravel', 'vue').",
         "fields": [("skills.primary", "Main skills", "tags", None, "Your core stack - these matter most"),
                    ("skills.secondary", "Other skills", "tags", None, ""),
                    ("skills.learning", "Currently learning", "tags", None, "")]},
    ]),
    ("search", "Where to search", "search", [
        {"title": "What to search for", "desc": "Every job site below is searched with these words.",
         "fields": [("sources.search_terms", "Search terms", "tags", None, "e.g. laravel, vue, full stack")]},
        {"title": "Job sites for the Philippines",
         "desc": "Jobs open to people in the Philippines, from local and international companies. "
                 "Searched directly - no account or login needed.",
         "grid": True,
         "fields": [("sources.jobstreet", "JobStreet", "switch", None, "ph.jobstreet.com"),
                    ("sources.onlinejobs", "OnlineJobs.ph", "switch", None, "Foreign employers hiring Filipinos remotely"),
                    ("sources.linkedin", "LinkedIn", "switch", None, "Remote jobs open to the Philippines")]},
        {"title": "International remote sites", "collapsed": True,
         "desc": "Global remote boards. Only jobs you can do from the Philippines are kept (worldwide, APAC or "
                 "Philippines) - jobs limited to other countries, like 'Remote - US', are skipped automatically.",
         "grid": True,
         "fields": [("sources.remotive", "Remotive", "switch", None, ""), ("sources.remoteok", "RemoteOK", "switch", None, ""),
                    ("sources.jobicy", "Jobicy", "switch", None, ""), ("sources.himalayas", "Himalayas", "switch", None, ""),
                    ("sources.weworkremotely", "We Work Remotely", "switch", None, ""),
                    ("sources.hackernews", "Hacker News", "switch", None, "Monthly 'Who is hiring?' thread"),
                    ("sources.arbeitnow", "Arbeitnow", "switch", None, "Mostly Europe")]},
        {"title": "Job-alert emails", "collapsed": True,
         "desc": "Also read the job alerts that LinkedIn, Indeed, JobStreet and OnlineJobs.ph email you. "
                 "This is the only way to get Indeed jobs - Indeed blocks direct searching.",
         "fields": [("email_alerts.enabled", "Read my job-alert emails", "switch", None, "Needs your mailbox connected in Settings"),
                    ("email_alerts.lookback_days", "Look back (days)", "int", None, "")]},
        {"title": "Companies you'd love to work for", "collapsed": True,
         "desc": "Watch their careers pages directly. Use the name from the careers link.",
         "fields": [("companies.greenhouse", "Greenhouse boards", "tags", None, "boards.greenhouse.io/<name>"),
                    ("companies.lever", "Lever boards", "tags", None, "jobs.lever.co/<name>"),
                    ("companies.ashby", "Ashby boards", "tags", None, "jobs.ashbyhq.com/<name>")]},
    ]),
    ("filters", "Filters", "filter", [
        {"title": "Job titles", "desc": "Quick, free filtering before the AI looks at anything.",
         "fields": [("filters.title_include", "Show titles containing any of", "tags", None, ""),
                    ("filters.title_exclude", "Never show titles containing", "tags", None, ""),
                    ("filters.max_age_days", "Ignore jobs older than (days)", "int", None, ""),
                    ("filters.min_keyword_score", "How many of your skills must appear", "int", None,
                     "Main skill = 3 points, other skill = 1 point")]},
        {"title": "Remote job locations", "desc": "Remote jobs often say where you must live.",
         "fields": [("work_setup.allowed_locations", "Locations that include you", "tags", None, "e.g. worldwide, apac, philippines"),
                    ("work_setup.reject_locations", "Always skip when it says", "tags", None, "e.g. us only"),
                    ("work_setup.strict_location", "Skip remote jobs whose location doesn't match", "switch", None,
                     "Saves AI cost. Turn off to see more borderline jobs."),
                    ("work_setup.max_timezone_overlap_hours_needed", "Hours of timezone overlap you can do", "int", None, "")]},
        {"title": "Deal breakers", "desc": "The AI marks these jobs as 'skip'.",
         "fields": [("deal_breakers", "", "lines", None, "One per line")]},
    ]),
    ("ai", "AI & automation", "sparkles", [
        {"title": "AI model", "desc": "Used to rate jobs, read alert emails, analyze your CV and write drafts.",
         "fields": [("claude.model", "", "radiocards", MODEL_CARDS, ""),
                    ("claude.effort", "Thinking effort", "pills1", ["low", "medium", "high"], "Higher is slower and costs more"),
                    ("claude.max_jobs_per_run", "Max jobs rated per run", "int", None, "A hard cap on spend per run"),
                    ("claude.max_description_chars", "Max job description length sent", "int", None, "")]},
        {"title": "Automatic checks", "desc": "While this app is open, it can check for jobs and replies on a timer.",
         "fields": [("automation.enabled", "Check automatically", "switch", None, ""),
                    ("automation.interval_hours", "Every (hours)", "float", None, ""),
                    ("automation.tasks", "What to do", "pills", ["alerts", "fetch", "score", "updates"],
                     "alerts = alert emails · fetch = job websites · score = AI rating (costs money) · updates = employer replies"),
                    ("automation.score_mode", "AI rating speed", "pills1", ["batch", "now"], "batch = half price, ready within ~1 hour")]},
    ]),
    ("apply", "Applications", "send", [
        {"title": "How your drafts sound", "desc": "",
         "fields": [("applications.tone", "Tone", "text", None, "e.g. professional, warm, concise"),
                    ("applications.sender_signature", "Email signature", "textarea", None, "Name, phone, LinkedIn - one per line")]},
    ]),
]

BOARD = [("drafted", "Drafts", ["drafted"], "pen"), ("applied", "Applied", ["applied"], "send"),
         ("acknowledged", "Heard back", ["acknowledged", "assessment"], "inbox"),
         ("interview", "Interview", ["interview"], "calendar"), ("offer", "Offer", ["offer"], "star"),
         ("rejected", "Closed", ["rejected", "withdrawn"], "x")]

JOB_TABS = [
    ("best", "Top matches", "stage='scored' AND verdict='apply' AND status!='ignored'"),
    ("maybe", "Worth a look", "stage='scored' AND verdict='maybe' AND status!='ignored'"),
    ("rated", "All rated", "stage='scored' AND verdict!='error' AND status!='ignored'"),
    ("waiting", "Not rated yet", "stage IN ('queued','batched') AND status!='ignored'"),
    ("filtered", "Filtered out", "stage IN ('rejected','duplicate')"),
    ("hidden", "Hidden", "status='ignored'"),
]

WORDS = {
    "verdict": {"apply": "Great match", "maybe": "Could work", "skip": "Weak match", "error": "Couldn't rate"},
    "rate_fit": {"meets_target": "Pays your target", "meets_minimum": "Meets your minimum",
                 "below_minimum": "Below your minimum", "not_stated": "Pay not listed"},
    "setup_fit": {"fits": "Work setup fits", "unclear": "Work setup unclear", "conflicts": "Work setup doesn't fit"},
    "seniority_fit": {"fits": "Right level for you", "under_qualified": "Asks for more experience",
                      "over_qualified": "You may be overqualified", "unclear": "Level unclear"},
    "status": apps.LABELS,
    "tone": {"ok": {"meets_target", "meets_minimum", "fits"}, "bad": {"below_minimum", "conflicts"}},
}


def all_fields():
    for _, _, _, sections in PREFS:
        for sec in sections:
            yield from sec["fields"]


def dget(d: dict, path: str):
    for part in path.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(part)
    return d


def dset(d: dict, path: str, value):
    parts = path.split(".")
    for part in parts[:-1]:
        d = d.setdefault(part, {})
    d[parts[-1]] = value


def to_form(value, kind):
    if kind == "tags":
        return ", ".join(str(v) for v in value or [])
    if kind == "lines":
        return "\n".join(value or [])
    if kind == "fx":
        return "\n".join(f"{k} = {v}" for k, v in (value or {}).items())
    if kind in ("pills", "cards"):
        return value or []
    if kind == "float" and isinstance(value, float) and value.is_integer():
        return int(value)
    return "" if value is None else value


def from_form(form, path, kind):
    raw = form.get(path, "")
    if kind == "switch":
        return path in form
    if kind in ("pills", "cards"):
        return form.getlist(path)
    if kind == "tags":
        return [s.strip() for s in raw.split(",") if s.strip()]
    if kind == "lines":
        return [s.strip() for s in raw.splitlines() if s.strip()]
    if kind in ("int", "float"):
        try:
            return (int if kind == "int" else float)(raw) if raw.strip() else None
        except ValueError:
            raise ValueError(f"'{raw}' is not a number")
    if kind == "fx":
        out = {}
        for line in raw.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                try:
                    out[k.strip().upper()] = float(v)
                except ValueError:
                    raise ValueError(f"Currency conversion: '{line.strip()}' should look like PHP = 0.0175")
        return out
    return raw.strip()


# --- request plumbing ----------------------------------------------------------

def db() -> DB:
    if "db" not in g:
        g.db = DB(DB_PATH)
    return g.db


@app.teardown_appcontext
def _close(_exc):
    d = g.pop("db", None)
    if d:
        d.conn.close()


@app.before_request
def _same_origin_only():
    # Blocks other websites from POSTing to this local app (e.g. to send emails).
    if request.method == "POST":
        src = request.headers.get("Origin") or request.headers.get("Referer") or ""
        if urlparse(src).netloc != request.host:
            abort(403)


def wants_json() -> bool:
    return request.headers.get("X-Requested-With") == "fetch"


def reply(ok: bool = True, message: str = "", fallback: str = "jobs", status: int = 200, **data):
    """JSON for the interactive UI, flash + redirect for plain form posts."""
    if wants_json():
        return jsonify(ok=ok, message=message, **data), (status if not ok else 200)
    if message:
        flash(message, "ok" if ok else "error")
    return redirect(request.form.get("next") or request.referrer or url_for(fallback))


@app.template_filter("ago")
def ago(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso[:10]
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    days = (datetime.now(timezone.utc) - dt).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 30:
        return f"{days} days ago"
    return dt.strftime("%d %b %Y")


@app.template_filter("money")
def money(v) -> str:
    try:
        return f"{float(v):,.0f}"
    except (TypeError, ValueError):
        return ""


def setup_status(d: DB, profile: dict) -> list[dict]:
    has_jobs = d.one("SELECT COUNT(*) n FROM jobs")["n"] > 0
    return [
        {"done": bool(os.environ.get("ANTHROPIC_API_KEY")), "title": "Add your AI key", "icon": "key",
         "text": "Needed to rate jobs and write applications.", "url": url_for("settings_page"), "cta": "Open Settings"},
        {"done": cvmod.active(d) is not None, "title": "Upload your CV", "icon": "file",
         "text": "The AI learns your skills from it and uses it for applications.", "url": url_for("cv_page"), "cta": "Upload CV"},
        {"done": d.meta("prefs_saved") == "1", "title": "Set your pay & work style", "icon": "wallet",
         "text": "Minimum pay, remote / hybrid / on-site, and your cities.", "url": url_for("profile_page"), "cta": "Set preferences"},
        {"done": mailer.imap_configured(), "title": "Connect your email (optional)", "icon": "mail",
         "text": "Reads LinkedIn / Indeed / JobStreet / OnlineJobs.ph alerts and employer replies.",
         "url": url_for("settings_page"), "cta": "Connect email"},
        {"done": has_jobs, "title": "Find your first jobs", "icon": "sparkles",
         "text": "Click 'Find jobs' at the top right.", "url": "#find", "cta": "Find jobs"},
    ]


STATIC = Path(__file__).parent / "static"


@app.template_global()
def asset(name: str) -> str:
    """Static URL with the file's modification time, so browsers never use an outdated copy."""
    return url_for("static", filename=name, v=int((STATIC / name).stat().st_mtime))


@app.context_processor
def _globals():
    d = db()
    profile = load_profile()
    cap = (profile.get("claude") or {}).get("max_jobs_per_run", 40)
    queued = d.one("SELECT COUNT(*) n FROM jobs WHERE stage='queued'")["n"]
    return {
        "icon": icon, "W": WORDS, "loads": json.loads,
        "nav": {
            "matches": d.one("SELECT COUNT(*) n FROM jobs WHERE stage='scored' AND verdict='apply' AND status=''")["n"],
            "active_apps": d.one(f"SELECT COUNT(*) n FROM applications WHERE status IN "
                                 f"({','.join('?' * len(apps.ACTIVE))})", apps.ACTIVE)["n"],
            "spent": d.one("SELECT COALESCE(SUM(cost_usd),0) s FROM usage")["s"],
            "queued": queued, "cap": cap,
            "est_max": scorer.estimate(profile, cap), "est_queued": scorer.estimate(profile, min(queued, cap)),
            "pending_batches": d.one("SELECT COUNT(*) n FROM batches WHERE done=0")["n"],
        },
        "configured": {"api": bool(os.environ.get("ANTHROPIC_API_KEY")), "imap": mailer.imap_configured(),
                       "smtp": mailer.smtp_configured(), "cv": cvmod.active(d) is not None},
    }


# --- tasks -----------------------------------------------------------------------

@app.post("/tasks/find")
def task_find():
    opts = request.get_json(silent=True) or {}
    names = []
    if opts.get("alerts"):
        names.append("alerts")
    if opts.get("feeds"):
        names.append("fetch")
    if opts.get("score") == "now":
        names.append("score")
    elif opts.get("score") == "batch":
        names += ["collect", "batch"] if db().one("SELECT 1 FROM batches WHERE done=0") else ["batch"]
    if opts.get("updates"):
        names.append("updates")
    if not names:
        return jsonify(ok=False, message="Pick at least one thing to do"), 400
    if not pipeline.runner.start(names):
        return jsonify(ok=False, message="Already running - wait for it to finish"), 409
    return jsonify(ok=True)


@app.post("/tasks/<name>")
def task(name):
    if name not in pipeline.STEPS:
        abort(404)
    if not pipeline.runner.start([name]):
        return jsonify(ok=False, message="Already running - wait for it to finish"), 409
    return jsonify(ok=True)


@app.get("/api/task")
def task_state():
    return jsonify(pipeline.runner.state())


# --- home --------------------------------------------------------------------------

@app.get("/")
def home():
    d = db()
    week = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    top = d.q("SELECT * FROM jobs WHERE stage='scored' AND verdict IN ('apply','maybe') AND status='' "
              "ORDER BY score DESC, posted_at DESC LIMIT 6")
    attention = d.q("SELECT * FROM applications WHERE next_action!='' AND next_action IS NOT NULL "
                    "AND status NOT IN ('rejected','withdrawn','offer') ORDER BY last_update DESC LIMIT 5")
    activity = d.q("SELECT e.*, a.company, a.title FROM app_events e JOIN applications a ON a.id=e.application_id "
                   "ORDER BY e.ts DESC, e.id DESC LIMIT 8")
    stats = {
        "matches": d.one("SELECT COUNT(*) n FROM jobs WHERE stage='scored' AND verdict='apply' AND status=''")["n"],
        "new_week": d.one("SELECT COUNT(*) n FROM jobs WHERE stage='scored' AND verdict IN ('apply','maybe') "
                          "AND first_seen>=?", (week,))["n"],
        "applied": d.one("SELECT COUNT(*) n FROM applications WHERE status!='drafted'")["n"],
        "interviews": d.one("SELECT COUNT(*) n FROM applications WHERE status IN ('interview','offer')")["n"],
        "seen": d.one("SELECT COUNT(*) n FROM jobs")["n"],
    }
    return render_template("home.html", setup=setup_status(d, load_profile()), top=top, attention=attention,
                           activity=activity, stats=stats, applied_idx=_applied_index())


# --- jobs --------------------------------------------------------------------------

def _applied_index():
    applied = db().q("SELECT job_id, fingerprint, lower(company) c, status, applied_at FROM applications WHERE status!='drafted'")
    return {"fp": {a["fingerprint"]: a for a in applied}, "co": {a["c"]: a for a in applied if a["c"]}}


@app.get("/jobs")
def jobs():
    tab = request.args.get("tab", "best")
    tabs = {k: w for k, _, w in JOB_TABS}
    if tab not in tabs:
        tab = "best"
    q = request.args.get("q", "").strip()
    wt = request.args.get("wt", "")
    source = request.args.get("source", "")
    sort = request.args.get("sort", "best")
    where, params = [tabs[tab]], []
    if wt:
        where.append("work_type=?"), params.append(wt)
    if source:
        where.append("source=?"), params.append(source)
    if q:
        where.append("(title LIKE ? OR company LIKE ? OR location LIKE ?)"), params.extend([f"%{q}%"] * 3)
    if sort == "new":
        order = "posted_at DESC"
    elif tab in ("waiting", "filtered"):
        order = "kw_score DESC, posted_at DESC"
    else:
        order = "score DESC, posted_at DESC"
    rows = db().q(f"SELECT * FROM jobs WHERE {' AND '.join(where)} ORDER BY {order} LIMIT 200", params)
    counts = {k: db().one(f"SELECT COUNT(*) n FROM jobs WHERE {w}")["n"] for k, _, w in JOB_TABS}
    sources = [r["source"] for r in db().q("SELECT DISTINCT source FROM jobs ORDER BY source")]
    return render_template("jobs.html", rows=rows, tab=tab, tabs=JOB_TABS, counts=counts, q=q, wt=wt, source=source,
                           sort=sort, sources=sources, applied_idx=_applied_index())


@app.get("/jobs/<path:job_id>")
def job(job_id):
    j = db().job(job_id)
    if not j:
        abort(404)
    a = apps.for_job(db(), job_id)
    return render_template("job.html", j=j, a=a, prior=apps.prior(db(), j),
                           analysis=json.loads(j["analysis"] or "{}"), emails=apps.emails_in_posting(j),
                           events=apps.events(db(), a["id"]) if a else [], board=BOARD)


@app.post("/jobs/add")
def job_add():
    f = request.form
    if not f.get("title", "").strip():
        return reply(False, "Please enter the job title")
    wt = f.get("work_type", "")
    ext = hashlib.sha1(f"{f.get('company')}|{f.get('title')}|{f.get('url')}".lower().encode()).hexdigest()[:16]
    new = db().insert_new([Job(source="manual", ext_id=ext, title=f["title"].strip(), company=f.get("company", "").strip(),
                               url=f.get("url", "").strip(), description=f.get("description", ""),
                               location=f.get("location", ""), salary_text=f.get("salary", ""), work_type=wt,
                               remote=True if wt == "remote" else (False if wt in ("hybrid", "onsite") else None))])
    if not new:
        return reply(False, "That job is already in your list")
    db().update(new[0], stage="queued", kw_score=99)  # you picked it: skip the free filter
    flash("Job added. Click 'Rate this job' to see how well it fits you.", "ok")
    return redirect(url_for("job", job_id=new[0]))


@app.post("/jobs/<path:job_id>/score")
def job_score(job_id):
    j = db().job(job_id)
    profile = load_profile()
    try:
        msg = llm.create(scorer.request_params(j, profile, scorer.system_blocks(profile)))
        db().log_usage(msg.model, False, msg.usage, llm.cost(msg.model, msg.usage), "score")
        result = scorer.parse(msg)
        scorer._save(db(), job_id, result)
    except Exception as e:
        return reply(False, f"Couldn't rate this job: {e}", status=500)
    if "error" in result:
        return reply(False, f"Couldn't rate this job: {result['error']}", status=500)
    return reply(True, f"Rated {result['score']}/100 - {WORDS['verdict'][result['verdict']]}",
                 score=result["score"], verdict=result["verdict"], summary=result["summary"])


@app.post("/jobs/<path:job_id>/ignore")
def job_ignore(job_id):
    undo = bool(request.form.get("undo") or (request.get_json(silent=True) or {}).get("undo"))
    db().update(job_id, status="" if undo else "ignored")
    return reply(True, "Job is back in your list" if undo else "Job hidden")


@app.post("/jobs/<path:job_id>/draft")
def job_draft(job_id):
    try:
        apps.draft(db(), load_profile(), db().job(job_id))
        flash("Your draft is ready. Read it through and edit anything you like.", "ok")
    except Exception as e:
        flash(f"Couldn't write the draft: {e}", "error")
    return redirect(url_for("job", job_id=job_id) + "#apply")


@app.post("/jobs/<path:job_id>/applied")
def job_applied(job_id):
    j = db().job(job_id)
    app_id = apps.ensure(db(), j)
    f = request.form
    if f.get("body") is not None:
        apps.save_draft(db(), app_id, f.get("to_email", ""), f.get("subject", ""), f.get("body", ""))
    apps.mark_applied(db(), app_id, f.get("method", "website"))
    flash("Nice! Saved as applied. We'll watch your inbox for replies.", "ok")
    return redirect(url_for("job", job_id=job_id) + "#apply")


# --- applications ------------------------------------------------------------------

@app.get("/applications")
def applications():
    rows = db().q("SELECT a.*, j.score, j.verdict, (SELECT summary FROM app_events e WHERE e.application_id=a.id "
                  "ORDER BY e.ts DESC, e.id DESC LIMIT 1) last_event "
                  "FROM applications a LEFT JOIN jobs j ON j.id=a.job_id ORDER BY COALESCE(a.last_update, a.created_at) DESC")
    columns = [{"key": k, "title": t, "icon": ic, "cards": [r for r in rows if r["status"] in sts]} for k, t, sts, ic in BOARD]
    return render_template("applications.html", columns=columns, total=len(rows), statuses=apps.STATUSES)


@app.get("/applications/<int:app_id>")
def application(app_id):
    a = apps.get(db(), app_id)
    if not a:
        abort(404)
    return render_template("application.html", a=a, events=apps.events(db(), app_id), statuses=apps.STATUSES,
                           j=db().job(a["job_id"]) if a["job_id"] else None)


@app.post("/applications/<int:app_id>/save")
def application_save(app_id):
    f = request.form
    apps.save_draft(db(), app_id, f.get("to_email", ""), f.get("subject", ""), f.get("body", ""), f.get("notes"))
    return reply(True, "Draft saved")


@app.post("/applications/<int:app_id>/send")
def application_send(app_id):
    f = request.form
    apps.save_draft(db(), app_id, f.get("to_email", ""), f.get("subject", ""), f.get("body", ""))
    a = apps.get(db(), app_id)
    j = db().job(a["job_id"]) if a["job_id"] else None
    if a["status"] != "drafted":
        return reply(False, "This application was already sent.")
    if j and apps.prior(db(), j) and not f.get("confirm_duplicate"):
        return reply(False, "You already applied to this company - tick the confirmation box to send anyway.")
    try:
        apps.send(db(), app_id, attach_cv=bool(f.get("attach_cv")))
    except Exception as e:
        return reply(False, str(e))
    return reply(True, f"Sent to {a['to_email']}! We'll watch for their reply.")


@app.post("/applications/<int:app_id>/status")
def application_status(app_id):
    data = request.get_json(silent=True) or request.form
    status = data.get("status")
    if status not in apps.STATUSES:
        abort(400)
    if apps.get(db(), app_id)["status"] != status:
        apps.set_status(db(), app_id, status, (data.get("note") or "").strip())
    if data.get("next_action") is not None:
        db().exec("UPDATE applications SET next_action=? WHERE id=?", (data["next_action"], app_id))
    return reply(True, f"Moved to {WORDS['status'][status]}", fallback="applications")


@app.post("/applications/<int:app_id>/note")
def application_note(app_id):
    note = (request.form.get("note") or "").strip()
    if note:
        apps.event(db(), app_id, "note", note)
    return reply(True, "Note added" if note else "", fallback="applications")


# --- CV ----------------------------------------------------------------------------

@app.get("/cv")
def cv_page():
    c = cvmod.active(db())
    return render_template("cv.html", c=c, analysis=json.loads(c["analysis"]) if c else None,
                           history=db().q("SELECT id, filename, uploaded_at, active FROM cvs ORDER BY id DESC"))


@app.post("/cv/upload")
def cv_upload():
    f = request.files.get("file")
    if not f or not f.filename:
        flash("Choose a file first", "error")
        return redirect(url_for("cv_page"))
    try:
        path = cvmod.save_upload(f.filename, f.read())
        cvmod.analyze(db(), load_profile(), path)
        flash("Your CV has been analyzed. Check the results, then use them for your preferences.", "ok")
    except Exception as e:
        flash(f"Couldn't analyze your CV: {e}", "error")
    return redirect(url_for("cv_page"))


@app.post("/cv/apply")
def cv_apply():
    c = cvmod.active(db())
    if not c:
        abort(400)
    profile = cvmod.apply_to_profile(load_profile(), json.loads(c["analysis"]), bool(request.form.get("replace")))
    save_profile(profile)
    flash("Done - your skills and details were filled in from your CV. Check them below.", "ok")
    return redirect(url_for("profile_page", tab="me"))


# --- preferences & settings --------------------------------------------------------

@app.get("/preferences")
def profile_page():
    profile = load_profile()
    values = {path: to_form(dget(profile, path), kind) for path, _, kind, *_ in all_fields()}
    return render_template("profile.html", prefs=PREFS, values=values, tab=request.args.get("tab", "work"),
                           saved=request.args.get("saved"))


@app.post("/preferences")
def profile_save():
    profile = load_profile()
    tab = request.form.get("_tab", "work")
    try:
        for path, label, kind, *_ in all_fields():
            dset(profile, path, from_form(request.form, path, kind))
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("profile_page", tab=tab))
    if not profile["work_setup"].get("work_types"):
        flash("Pick at least one way of working (remote, hybrid or on-site)", "error")
        return redirect(url_for("profile_page", tab="work"))
    save_profile(profile)
    db().set_meta("prefs_saved", "1")
    return redirect(url_for("profile_page", tab=tab, saved=1))


@app.get("/settings")
def settings_page():
    return render_template("settings.html", values=env_values(), secrets=SECRET_KEYS)


@app.post("/settings")
def settings_save():
    save_env({k: request.form.get(k, "") for k in ENV_KEYS})
    llm.reset_client()
    flash("Settings saved", "ok")
    return redirect(url_for("settings_page"))


@app.post("/settings/test")
def settings_test():
    try:
        with mailer.imap() as m:
            n = len(mailer.search(m, "ALL"))
        return reply(True, f"Connected! Found {n:,} emails in your mailbox.", fallback="settings_page")
    except Exception as e:
        return reply(False, str(e), fallback="settings_page")


@app.get("/usage")
def usage():
    rows = db().q("SELECT purpose, model, COUNT(*) calls, SUM(input_tokens) i, SUM(output_tokens) o, "
                  "SUM(cache_read) cr, SUM(cost_usd) usd FROM usage GROUP BY purpose, model ORDER BY usd DESC")
    funnel = {r["stage"]: r["n"] for r in db().q("SELECT stage, COUNT(*) n FROM jobs GROUP BY stage")}
    reasons = db().q("SELECT substr(reject_reason, 1, instr(reject_reason || ':', ':') - 1) r, COUNT(*) n "
                     "FROM jobs WHERE stage='rejected' GROUP BY r ORDER BY n DESC LIMIT 8")
    month = db().one("SELECT COALESCE(SUM(cost_usd),0) s FROM usage WHERE ts>=?",
                     (datetime.now(timezone.utc).strftime("%Y-%m-01"),))["s"]
    return render_template("usage.html", rows=rows, funnel=funnel, reasons=reasons, month=month)


def serve(host: str = "127.0.0.1", port: int = 5000):
    load_env()
    threading.Thread(target=pipeline.scheduler_loop, daemon=True).start()
    print(f"Job Radar is running: open http://{host}:{port} in your browser (close this window to stop).")
    app.run(host=host, port=port, debug=False, threaded=True)
