"""One background task at a time. The UI polls state(): step-by-step progress, a raw log for
the curious, and a short summary when finished."""

from __future__ import annotations

import threading
import traceback
from datetime import datetime
from typing import Callable

from ..container import Container
from .pipeline_steps import LABELS, PipelineSteps

MAX_LOG_LINES = 400


class TaskRunner:
    def __init__(self, container_factory: Callable[[], Container]):
        self.container_factory = container_factory
        self.lock = threading.Lock()
        self.running = False
        self.steps: list[dict] = []
        self.lines: list[str] = []
        self.summary: dict = {}
        self.finished_at = ""

    def log(self, line: str):
        self.lines.append(f"{datetime.now():%H:%M:%S} {line}")
        self.lines = self.lines[-MAX_LOG_LINES:]

    def start(self, names: list[str]) -> bool:
        with self.lock:
            if self.running:
                return False
            self.running, self.lines, self.summary, self.finished_at = True, [], {}, ""
            self.steps = [{"key": n, "label": LABELS.get(n, n), "status": "pending", "note": ""} for n in names]
        threading.Thread(target=self._run, daemon=True).start()
        return True

    def _run(self):
        container = self.container_factory()
        try:
            profile = container.profiles.load()
            before = self._counts(container)
            steps = PipelineSteps(container).by_name()
            for step in self.steps:
                self._run_step(step, steps[step["key"]], profile)
            after = self._counts(container)
            self.summary = {
                "new_matches": after["matches"] - before["matches"],
                "new_jobs": after["jobs"] - before["jobs"],
                "waiting": container.jobs.count_stage("queued"),
                "pending_batches": container.batches.count_pending(),
                "failed": sum(step["status"] == "failed" for step in self.steps),
            }
        finally:
            self.log("Finished.")
            self.finished_at = datetime.now().isoformat(timespec="seconds")
            self.running = False
            container.close()

    def _run_step(self, step: dict, run: Callable, profile: dict):
        step["status"] = "running"
        try:
            run(profile, self.log)
            step["status"] = "done"
        except SystemExit as e:
            step["status"], step["note"] = "failed", str(e)
            self.log(f"  stopped: {e}")
        except Exception as e:  # keep going with the next step
            step["status"], step["note"] = "failed", str(e)
            self.log(f"  {step['key']} failed: {e}")
            traceback.print_exc()

    @staticmethod
    def _counts(container: Container) -> dict[str, int]:
        return {"matches": container.jobs.count_good_matches(), "jobs": container.jobs.count()}

    def state(self) -> dict:
        return {"running": self.running, "steps": self.steps, "log": self.lines,
                "summary": self.summary, "finished_at": self.finished_at}
