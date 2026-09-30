"""Job Radar - fetch job boards + alert emails, filter for free, score the survivors with Claude.

    python run.py ui              # open the web app at http://127.0.0.1:5000  (recommended)
    python run.py                 # full pipeline: alerts -> feeds -> filter -> score -> updates -> report
    python run.py --batch         # same, but scoring via Batch API (50% cheaper, async)
    python run.py alerts          # read LinkedIn / Indeed / JobStreet / OnlineJobs.ph alert emails
    python run.py fetch           # fetch feeds + filter only (zero tokens) - use to tune profile.yaml
    python run.py updates         # check your inbox for replies to applications + closed postings
    python run.py collect         # collect finished batch results + rebuild report
    python run.py dry-run         # show what WOULD be sent to Claude and the estimated cost
    python run.py report          # rebuild the static HTML/CSV report
    python run.py stats           # funnel + spend
"""

from __future__ import annotations

import argparse

from ..container import Container, env_file
from ..pipeline.pipeline_steps import PipelineSteps
from . import commands

COMMANDS = ["run", "ui", "alerts", "fetch", "score", "updates", "collect", "report", "dry-run", "stats"]


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="?", default="run", choices=COMMANDS)
    parser.add_argument("--batch", action="store_true", help="score via Batch API (50%% cheaper, results within ~1h)")
    parser.add_argument("--wait", type=float, default=0, help="minutes to wait for batch results")
    parser.add_argument("--limit", type=int, help="override max_jobs_per_run")
    parser.add_argument("--min-score", type=int, default=0, help="hide jobs below this score in the report")
    parser.add_argument("--port", type=int, default=5000)
    return parser.parse_args()


def run_pipeline(c: Container, args):
    if not c.profiles.exists:
        print("Created profile.yaml from the example - edit it (or use `python run.py ui` -> Profile).")
    profile = c.profiles.load()
    if args.command == "dry-run":
        return commands.dry_run(c, profile, args.limit)
    steps = PipelineSteps(c)
    if args.command in ("run", "alerts"):
        steps.alerts(profile, print)
    if args.command in ("run", "fetch"):
        steps.fetch(profile, print)
    if args.command in ("run", "score"):
        if args.batch:
            c.batch_scoring.collect(0)
            steps.score(profile, print, batch=True, limit=args.limit)
            if c.batch_scoring.collect(args.wait):
                print("Batch submitted. Run `python run.py collect` later (usually < 1h).")
        else:
            steps.score(profile, print, limit=args.limit)
    if args.command in ("run", "updates"):
        steps.updates(profile, print)
    if args.command in ("run", "score"):
        commands.report(c, args.min_score)


def main():
    args = parse_args()
    env_file().load()
    if args.command == "ui":
        from ..app import serve
        return serve(port=args.port)
    c = Container()
    try:
        if args.command == "stats":
            return commands.stats(c)
        if args.command == "report":
            return commands.report(c, args.min_score)
        if args.command == "collect":
            left = c.batch_scoring.collect(args.wait)
            print(f"{left} batch(es) still processing" if left else "All batches collected.")
            return commands.report(c, args.min_score)
        return run_pipeline(c, args)
    finally:
        c.close()
