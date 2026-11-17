"""Start background tasks from the UI and poll their progress."""

from __future__ import annotations

from flask import Blueprint, abort, jsonify, request

from ..web.request_scope import container, task_runner
from .pipeline_steps import STEP_NAMES
from .run_plan import plan_steps, run_context

tasks_bp = Blueprint("tasks", __name__)
BUSY = "Already running - wait for it to finish"
FIND_OPTIONS = ("alerts", "fetch", "score", "updates")


def find_tasks(options: dict, profile: dict, context) -> list[str]:
    """'Find jobs' -> task names. No options = one click: everything that applies, AI rating right away.
    The options dialog can switch parts off or pick half-price rating."""
    wanted = {name for name in FIND_OPTIONS if options.get(name)} if options else None
    return plan_steps(profile, context, options.get("score_mode", "now"), wanted)


@tasks_bp.post("/tasks/find")
def find():
    c = container()
    names = find_tasks(request.get_json(silent=True) or {}, c.profiles.load(), run_context(c))
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
