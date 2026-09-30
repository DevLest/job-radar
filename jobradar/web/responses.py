from __future__ import annotations

from flask import flash, jsonify, redirect, request, url_for


def wants_json() -> bool:
    return request.headers.get("X-Requested-With") == "fetch"


def reply(ok: bool = True, message: str = "", fallback: str = "jobs.list", status: int = 200, **data):
    """JSON for the interactive UI, flash + redirect for plain form posts."""
    if wants_json():
        return jsonify(ok=ok, message=message, **data), (status if not ok else 200)
    if message:
        flash(message, "ok" if ok else "error")
    return redirect(request.form.get("next") or request.referrer or url_for(fallback))


def json_body_or_form():
    return request.get_json(silent=True) or request.form
