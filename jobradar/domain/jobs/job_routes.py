from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ...web.request_scope import container
from ...web.responses import reply
from .job_labels import verdict_word
from .job_queries import JobListFilter
from .job_service import JobError, ManualJob

jobs_bp = Blueprint("jobs", __name__, url_prefix="/jobs")


@jobs_bp.get("", endpoint="list")
def list_jobs():
    args = request.args
    page = container().job_service.list_page(JobListFilter(
        tab=args.get("tab", "best"), search=args.get("q", "").strip(), work_type=args.get("wt", ""),
        source=args.get("source", ""), sort=args.get("sort", "best")))
    return render_template("pages/jobs.html", page=page)


@jobs_bp.get("/<path:job_id>")
def detail(job_id):
    page = container().job_service.detail(job_id)
    if not page:
        abort(404)
    return render_template("pages/job.html", page=page)


@jobs_bp.post("/add")
def add():
    form = request.form
    manual = ManualJob(title=form.get("title"), company=form.get("company"), url=form.get("url"),
                       location=form.get("location"), work_type=form.get("work_type"), salary=form.get("salary"),
                       description=form.get("description"))
    try:
        job_id = container().job_service.add_manual(manual)
    except JobError as e:
        return reply(False, str(e))
    flash("Job added. Click 'Rate this job' to see how well it fits you.", "ok")
    return redirect(url_for("jobs.detail", job_id=job_id))


@jobs_bp.post("/<path:job_id>/score")
def score(job_id):
    c = container()
    try:
        result = c.scoring.score_one(job_id, c.profiles.load())
    except Exception as e:
        return reply(False, f"Couldn't rate this job: {e}", status=500)
    if "error" in result:
        return reply(False, f"Couldn't rate this job: {result['error']}", status=500)
    return reply(True, f"Rated {result['score']}/100 - {verdict_word(result['verdict'])}",
                 score=result["score"], verdict=result["verdict"], summary=result["summary"])


@jobs_bp.post("/<path:job_id>/ignore")
def ignore(job_id):
    undo = bool(request.form.get("undo") or (request.get_json(silent=True) or {}).get("undo"))
    container().job_service.set_hidden(job_id, hidden=not undo)
    return reply(True, "Job is back in your list" if undo else "Job hidden")


@jobs_bp.post("/<path:job_id>/draft")
def draft(job_id):
    c = container()
    try:
        c.drafts.draft(c.profiles.load(), c.jobs.get(job_id))
        flash("Your draft is ready. Read it through and edit anything you like.", "ok")
    except Exception as e:
        flash(f"Couldn't write the draft: {e}", "error")
    return redirect(url_for("jobs.detail", job_id=job_id) + "#apply")


@jobs_bp.post("/<path:job_id>/applied")
def applied(job_id):
    form = request.form
    draft_text = None
    if form.get("body") is not None:
        draft_text = {"to_email": form.get("to_email", ""), "subject": form.get("subject", ""),
                      "body": form.get("body", "")}
    container().application_service.applied_elsewhere(job_id, form.get("method", "website"), draft_text)
    flash("Nice! Saved as applied. We'll watch your inbox for replies.", "ok")
    return redirect(url_for("jobs.detail", job_id=job_id) + "#apply")
