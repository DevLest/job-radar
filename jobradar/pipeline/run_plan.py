"""Which steps a run does. One plan shared by the 'Find jobs' button, the scheduler and the CLI, so
nobody has to remember to collect half-price ratings or work out which steps apply right now."""

from __future__ import annotations

from dataclasses import dataclass

from ..container import Container
from ..domain.settings.settings_service import api_configured

SCORE_MODES = ("now", "batch", "none")


@dataclass
class RunContext:
    """What is set up, and what is waiting."""
    api: bool
    imap: bool
    pending_batches: bool
    active_apps: bool


def run_context(container: Container) -> RunContext:
    return RunContext(api=api_configured(), imap=container.mail.imap_configured(),
                      pending_batches=container.batches.has_pending(),
                      active_apps=container.applications.count_active() > 0)


def plan_steps(profile: dict, context: RunContext, score_mode: str = "now",
               wanted: set[str] | None = None) -> list[str]:
    """Step names in run order. `wanted` limits the run to some of alerts / fetch / score / updates
    (None = everything that applies). Finished half-price ratings are always collected first."""
    def want(name: str) -> bool:
        return wanted is None or name in wanted

    alerts_on = (profile.get("email_alerts") or {}).get("enabled", True)
    steps = ["collect"] if context.api and context.pending_batches else []
    if want("alerts") and context.imap and alerts_on:
        steps.append("alerts")
    if want("fetch"):
        steps.append("fetch")
    if want("score") and context.api and score_mode in ("now", "batch"):
        steps.append("score" if score_mode == "now" else "batch")
    if want("updates") and context.active_apps:
        steps.append("updates")
    return steps
