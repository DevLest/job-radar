from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ...web.request_scope import container

cv_bp = Blueprint("cv", __name__, url_prefix="/cv")


@cv_bp.get("")
def page():
    return render_template("pages/cv.html", cv=container().cv_service.active())


@cv_bp.post("/upload")
def upload():
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Choose a file first", "error")
        return redirect(url_for("cv.page"))
    try:
        container().cv_service.upload(file.filename, file.read())
        flash("Your CV has been analyzed. Check the results, then use them for your preferences.", "ok")
    except Exception as e:
        flash(f"Couldn't analyze your CV: {e}", "error")
    return redirect(url_for("cv.page"))


@cv_bp.post("/apply")
def apply():
    if not container().cv_service.use_for_profile(replace_skills=bool(request.form.get("replace"))):
        abort(400)
    flash("Done - your skills and details were filled in from your CV. Check them below.", "ok")
    return redirect(url_for("preferences.page", tab="me"))
