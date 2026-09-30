from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ...web.request_scope import container
from ...web.responses import reply
from .settings_service import ENV_KEYS, SECRET_KEYS

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.get("")
def page():
    return render_template("pages/settings.html", values=container().settings.values(), secrets=SECRET_KEYS)


@settings_bp.post("")
def save():
    container().settings.save({key: request.form.get(key, "") for key in ENV_KEYS})
    flash("Settings saved", "ok")
    return redirect(url_for("settings.page"))


@settings_bp.post("/test")
def test():
    try:
        count = container().settings.test_mailbox()
        return reply(True, f"Connected! Found {count:,} emails in your mailbox.", fallback="settings.page")
    except Exception as e:
        return reply(False, str(e), fallback="settings.page")
