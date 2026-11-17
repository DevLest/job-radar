"""While the UI is running: collects finished half-price ratings in the background, and runs the
configured automatic tasks every N hours."""

from __future__ import annotations

import time
import traceback
from datetime import datetime, timedelta, timezone
from typing import Callable

from ..container import Container
from .run_plan import plan_steps, run_context
from .task_runner import TaskRunner

LAST_RUN_KEY = "last_auto_run"
CHECK_EVERY_SECONDS = 60
COLLECT_EVERY_SECONDS = 300


def auto_tasks(profile: dict, container: Container) -> list[str]:
    automation = profile.get("automation") or {}
    return plan_steps(profile, run_context(container), automation.get("score_mode", "batch"),
                      set(automation.get("tasks") or []))


def _due(last_run: str, interval_hours: float) -> bool:
    return not last_run or datetime.fromisoformat(last_run) < datetime.now(timezone.utc) - timedelta(hours=interval_hours)


def collect_finished_batches(runner: TaskRunner, container: Container):
    """Quietly stores half-price ratings once they are ready, so 'collect' is never a manual step."""
    if runner.running or not container.batches.has_pending():
        return
    with runner.lock:  # never overlaps a run started from the UI
        if not runner.running:
            container.batch_scoring.collect(0, log=lambda _line: None)


def _tick(runner: TaskRunner, container: Container, collect_now: bool):
    profile = container.profiles.load()
    automation = profile.get("automation") or {}
    if automation.get("enabled") and not runner.running:
        if _due(container.meta.get(LAST_RUN_KEY), float(automation.get("interval_hours", 6))):
            container.meta.set(LAST_RUN_KEY, datetime.now(timezone.utc).isoformat())
            tasks = auto_tasks(profile, container)
            if tasks:
                runner.start(tasks)
                return
    if collect_now:
        collect_finished_batches(runner, container)


def scheduler_loop(runner: TaskRunner, container_factory: Callable[[], Container]):
    last_collect = 0.0
    while True:
        try:
            container = container_factory()
            try:
                collect_now = time.monotonic() - last_collect >= COLLECT_EVERY_SECONDS
                if collect_now:
                    last_collect = time.monotonic()
                _tick(runner, container, collect_now)
            finally:
                container.close()
        except Exception:
            traceback.print_exc()
        time.sleep(CHECK_EVERY_SECONDS)
