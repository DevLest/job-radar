"""Jinja filters, globals and the layout context every page gets."""

from __future__ import annotations

from flask import Flask, url_for

from ..shared.constants.paths import STATIC_DIR
from ..shared.utils.date_utils import time_ago
from ..shared.utils.format_utils import money
from .icons import icon
from .request_scope import container

STYLESHEETS = ["tokens", "base", "layout", "atoms", "job-list", "forms", "pages", "organisms", "misc"]


def asset(name: str) -> str:
    """Static URL with the file's modification time, so browsers never use an outdated copy."""
    return url_for("static", filename=name, v=int((STATIC_DIR / name).stat().st_mtime))


def register(app: Flask):
    app.add_template_filter(time_ago, "ago")
    app.add_template_filter(money, "money")
    app.add_template_global(asset, "asset")
    app.add_template_global(icon, "icon")
    app.add_template_global(STYLESHEETS, "stylesheets")

    @app.context_processor
    def _layout():
        layout = container().layout
        return {"nav": layout.nav(), "configured": layout.configured()}
