"""Local web UI (http://127.0.0.1:5000). Binds to localhost only."""

from __future__ import annotations

import os
import threading

from flask import Flask

from .container import Container, env_file
from .domain.applications.application_routes import applications_bp
from .domain.cv.cv_routes import cv_bp
from .domain.home.home_routes import home_bp
from .domain.jobs.job_routes import jobs_bp
from .domain.preferences.preferences_routes import preferences_bp
from .domain.settings.settings_routes import settings_bp
from .domain.usage.usage_routes import usage_bp
from .pipeline.scheduler import scheduler_loop
from .pipeline.task_routes import tasks_bp
from .pipeline.task_runner import TaskRunner
from .web import request_scope, security, template_helpers

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
BLUEPRINTS = [home_bp, jobs_bp, applications_bp, cv_bp, preferences_bp, settings_bp, usage_bp, tasks_bp]


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.urandom(24)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # always revalidate JS modules / CSS (they import each other)
    app.extensions["task_runner"] = TaskRunner(Container)
    request_scope.register(app)
    security.register(app)
    template_helpers.register(app)
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)
    return app


def serve(host: str = "127.0.0.1", port: int = 5000):
    env_file().load()
    app = create_app()
    threading.Thread(target=scheduler_loop, args=(app.extensions["task_runner"], Container), daemon=True).start()
    print(f"Job Radar is running: open http://{host}:{port} in your browser (close this window to stop).")
    app.run(host=host, port=port, debug=False, threaded=True)
