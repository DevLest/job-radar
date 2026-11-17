from jobradar.pipeline.run_plan import RunContext, plan_steps
from jobradar.pipeline.task_routes import find_tasks

PROFILE = {"email_alerts": {"enabled": True}}


def context(**changes) -> RunContext:
    return RunContext(**{"api": True, "imap": True, "pending_batches": False, "active_apps": False, **changes})


def test_one_click_runs_everything_that_applies():
    assert plan_steps(PROFILE, context()) == ["alerts", "fetch", "score"]


def test_finished_batches_are_collected_first_and_updates_need_applications():
    steps = plan_steps(PROFILE, context(pending_batches=True, active_apps=True), "batch")
    assert steps == ["collect", "alerts", "fetch", "batch", "updates"]


def test_steps_needing_setup_are_skipped():
    # Closed postings and follow-ups are checked without a mailbox.
    assert plan_steps(PROFILE, context(api=False, imap=False, active_apps=True)) == ["fetch", "updates"]
    assert plan_steps({"email_alerts": {"enabled": False}}, context()) == ["fetch", "score"]


def test_wanted_limits_the_run():
    assert plan_steps(PROFILE, context(), "now", {"fetch"}) == ["fetch"]
    assert plan_steps(PROFILE, context(), "none") == ["alerts", "fetch"]


def test_find_button_and_options_dialog():
    assert find_tasks({}, PROFILE, context()) == ["alerts", "fetch", "score"]
    options = {"alerts": False, "fetch": True, "score": True, "updates": False, "score_mode": "batch"}
    assert find_tasks(options, PROFILE, context()) == ["fetch", "batch"]
    assert find_tasks({"alerts": False, "fetch": False, "score": False, "updates": False}, PROFILE, context()) == []
