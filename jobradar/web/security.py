from __future__ import annotations

from urllib.parse import urlparse

from flask import Flask, abort, request


def register(app: Flask):
    @app.before_request
    def _same_origin_only():
        # Blocks other websites from POSTing to this local app (e.g. to send emails).
        if request.method == "POST":
            source = request.headers.get("Origin") or request.headers.get("Referer") or ""
            if urlparse(source).netloc != request.host:
                abort(403)
