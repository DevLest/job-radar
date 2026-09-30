"""Start background tasks from the UI and poll their progress."""

from __future__ import annotations

from flask import Blueprint, abort, jsonify, request

from ..web.request_scope import container, task_runner
from .pipeline_steps import STEP_NAMES

tasks_bp = Blueprint("tasks", __name__)
BUSY = "Already running - wait for it to finish"


def find_tasks(options: dict, batch_pending: bool) -> list[str]:
    """The 'Find jobs' dialog's choices -> task names, in run order."""
    names = []
    if options.get("alerts"):
        names.append("alerts")
    if options.get("feeds"):
        names.append("fetch")
    if options.get("score") == "now":
        names.append("score")
    elif options.get("score") == "batch":
        names += ["collect", "batch"] if batch_pending else ["batch"]
    if options.get("updates"):
        names.append("updates")
    return names


@tasks_bp.post("/tasks/find")
def find():
    names = find_tasks(request.get_json(silent=True) or {}, container().batches.has_pending())
    if not names:
        return jsonify(ok=False, message="Pick at least one thing to do"), 400
    if not task_runner().start(names):
        return jsonify(ok=False, message=BUSY), 409
    return jsonify(ok=True)


@tasks_bp.post("/tasks/<name>")
def start(name):
    if name not in STEP_NAMES:
        abort(404)
    if not task_runner().start([name]):
        return jsonify(ok=False, message=BUSY), 409
    return jsonify(ok=True)


@tasks_bp.get("/api/task")
def state():
    return jsonify(task_runner().state())
