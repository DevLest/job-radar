"""Runs the configured automatic tasks every N hours while the UI is running."""

from __future__ import annotations

import time
import traceback
from datetime import datetime, timedelta, timezone
from typing import Callable

from ..container import Container
from .task_runner import TaskRunner

LAST_RUN_KEY = "last_auto_run"
CHECK_EVERY_SECONDS = 60
TASK_ORDER = ["alerts", "fetch", "score", "updates"]


def auto_tasks(profile: dict) -> list[str]:
    automation = profile.get("automation") or {}
    tasks = [task for task in TASK_ORDER if task in (automation.get("tasks") or [])]
    if "score" in tasks and automation.get("score_mode", "batch") == "batch":
        tasks[tasks.index("score")] = "batch"
        tasks.insert(0, "collect")
    return tasks


def _due(last_run: str, interval_hours: float) -> bool:
    return not last_run or datetime.fromisoformat(last_run) < datetime.now(timezone.utc) - timedelta(hours=interval_hours)


def scheduler_loop(runner: TaskRunner, container_factory: Callable[[], Container]):
    while True:
        try:
            container = container_factory()
            try:
                profile = container.profiles.load()
                automation = profile.get("automation") or {}
                if automation.get("enabled") and not runner.running:
                    if _due(container.meta.get(LAST_RUN_KEY), float(automation.get("interval_hours", 6))):
                        container.meta.set(LAST_RUN_KEY, datetime.now(timezone.utc).isoformat())
                        runner.start(auto_tasks(profile))
            finally:
                container.close()
        except Exception:
            traceback.print_exc()
        time.sleep(CHECK_EVERY_SECONDS)
