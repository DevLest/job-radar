from __future__ import annotations

from flask import Blueprint, abort, render_template, request

from ...web.request_scope import container
from ...web.responses import json_body_or_form, reply
from .application_mapper import to_board, to_page
from .application_status import STATUSES, label

applications_bp = Blueprint("applications", __name__, url_prefix="/applications")


def _draft_form() -> dict:
    form = request.form
    return {"to_email": form.get("to_email", ""), "subject": form.get("subject", ""), "body": form.get("body", "")}


@applications_bp.get("")
def board():
    return render_template("pages/applications.html", board=to_board(container().applications.board_rows()))


@applications_bp.get("/<int:app_id>")
def detail(app_id):
    c = container()
    app = c.application_service.get(app_id)
    if not app:
        abort(404)
    return render_template("pages/application.html", page=to_page(app, c.events.for_application(app_id)))


@applications_bp.post("/<int:app_id>/save")
def save(app_id):
    draft = _draft_form()
    container().application_service.save_draft(app_id, draft["to_email"], draft["subject"], draft["body"],
                                               request.form.get("notes"))
    return reply(True, "Draft saved")


@applications_bp.post("/<int:app_id>/send")
def send(app_id):
    form = request.form
    try:
        to = container().sending.send_draft(app_id, _draft_form(), attach_cv=bool(form.get("attach_cv")),
                                            confirm_duplicate=bool(form.get("confirm_duplicate")))
    except Exception as e:
        return reply(False, str(e))
    return reply(True, f"Sent to {to}! We'll watch for their reply.")


@applications_bp.post("/<int:app_id>/status")
def status(app_id):
    data = json_body_or_form()
    new_status = data.get("status")
    if new_status not in STATUSES:
        abort(400)
    service = container().application_service
    if not service.get(app_id):
        abort(404)
    service.change_status(app_id, new_status, (data.get("note") or "").strip(), data.get("next_action"))
    return reply(True, f"Moved to {label(new_status)}", fallback="applications.board")


@applications_bp.post("/<int:app_id>/note")
def note(app_id):
    added = container().application_service.add_note(app_id, request.form.get("note"))
    return reply(True, "Note added" if added else "", fallback="applications.board")
