from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ...web.request_scope import container
from .preferences_service import PreferencesError

preferences_bp = Blueprint("preferences", __name__, url_prefix="/preferences")


@preferences_bp.get("")
def page():
    service = container().preferences
    return render_template("pages/preferences.html", tabs=service.tabs(), values=service.form_values(),
                           tab=request.args.get("tab", "work"), saved=request.args.get("saved"))


@preferences_bp.post("")
def save():
    tab = request.form.get("_tab", "work")
    try:
        container().preferences.save(request.form, tab)
    except PreferencesError as e:
        flash(str(e), "error")
        return redirect(url_for("preferences.page", tab=e.tab))
    return redirect(url_for("preferences.page", tab=tab, saved=1))
