"""One Container (and so one SQLite connection) per request."""

from __future__ import annotations

from flask import Flask, current_app, g

from ..container import Container
from ..pipeline.task_runner import TaskRunner


def container() -> Container:
    if "container" not in g:
        g.container = Container()
    return g.container


def task_runner() -> TaskRunner:
    return current_app.extensions["task_runner"]


def register(app: Flask):
    @app.teardown_appcontext
    def _close(_exc):
        scoped = g.pop("container", None)
        if scoped:
            scoped.close()
