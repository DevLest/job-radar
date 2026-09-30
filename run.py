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
from collections import Counter

from jobradar import pipeline, report, scorer
from jobradar.db import DB
from jobradar.settings import DB_PATH, PROFILE, ROOT, load_env, load_profile


def do_report(db: DB, args):
    path = report.build(db, ROOT / "reports", args.min_score)
    print(f"Report: {path}")
    top = db.rows("stage='scored' AND verdict='apply' AND status='' ORDER BY score DESC LIMIT 10")
    if top:
        print("\nTop matches to apply to:")
        for r in top:
            print(f"  {r['score']:>3}  {r['title'][:50]:<50} {(r['company'] or '')[:22]:<22} {r['url']}")


def do_dry_run(db: DB, profile: dict, args):
    from jobradar import llm
    rows = scorer.pick(db, profile, args.limit)
    if not rows:
        print("Nothing queued. Run `python run.py fetch` first.")
        return
    system = scorer.system_blocks(profile)
    p = scorer.request_params(rows[0], profile, system)
    count = lambda content: llm.client().messages.count_tokens(
        model=p["model"], system=system, messages=[{"role": "user", "content": content}]).input_tokens
    n, sys_n = count(p["messages"][0]["content"]), count("x")
    pin, pout, pcache = llm.PRICES.get(p["model"], llm.PRICES["claude-opus-5-5"])
    per_job = ((n - sys_n) * pin + sys_n * pcache + 600 * pout) / 1e6  # ~600 output tokens incl. thinking
    print(f"{len(rows)} jobs would be scored with {p['model']}.")
    print(f"System prompt {sys_n} tokens (cached), first job {n - sys_n} tokens.")
    print(f"Estimated: ~${per_job:.4f}/job, ~${per_job * len(rows):.3f} this run "
          f"(~${per_job * len(rows) / 2:.3f} with --batch)\n")
    print("--- first job as sent ---\n" + p["messages"][0]["content"][:1500])
    print("\n--- queue ---")
    for r in rows:
        print(f"  kw={r['kw_score']:>4g}  {r['title'][:60]:<60} {(r['company'] or '')[:25]}")


def do_stats(db: DB):
    stages = Counter(r["stage"] for r in db.rows())
    verdicts = Counter(r["verdict"] for r in db.rows("stage='scored'"))
    reasons = Counter((r["reject_reason"] or "").split(":")[0] for r in db.rows("stage='rejected'"))
    statuses = Counter(r["status"] for r in db.q("SELECT status FROM applications"))
    u = db.one("SELECT COUNT(*) n, SUM(input_tokens) i, SUM(output_tokens) o, SUM(cache_read) c, SUM(cost_usd) usd FROM usage")
    print("Funnel:", dict(stages))
    print("Verdicts:", dict(verdicts))
    print("Top reject reasons:", dict(reasons.most_common(6)))
    print("Applications:", dict(statuses) or "-")
    print(f"LLM calls: {u['n']}, input {u['i'] or 0:,} tok, output {u['o'] or 0:,} tok, cache reads {u['c'] or 0:,} tok, "
          f"total ~${u['usd'] or 0:.4f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", default="run",
                    choices=["run", "ui", "alerts", "fetch", "score", "updates", "collect", "report", "dry-run", "stats"])
    ap.add_argument("--batch", action="store_true", help="score via Batch API (50%% cheaper, results within ~1h)")
    ap.add_argument("--wait", type=float, default=0, help="minutes to wait for batch results")
    ap.add_argument("--limit", type=int, help="override max_jobs_per_run")
    ap.add_argument("--min-score", type=int, default=0, help="hide jobs below this score in the report")
    ap.add_argument("--port", type=int, default=5000)
    args = ap.parse_args()

    load_env()
    if args.command == "ui":
        from jobradar.web import serve
        return serve(port=args.port)

    db = DB(DB_PATH)
    if args.command == "stats":
        return do_stats(db)
    if args.command == "report":
        return do_report(db, args)
    if args.command == "collect":
        left = scorer.collect_batches(db, args.wait)
        print(f"{left} batch(es) still processing" if left else "All batches collected.")
        return do_report(db, args)

    if not PROFILE.exists():
        print("Created profile.yaml from the example - edit it (or use `python run.py ui` -> Profile).")
    profile = load_profile()
    if args.command == "dry-run":
        return do_dry_run(db, profile, args)
    if args.command in ("run", "alerts"):
        pipeline.step_alerts(db, profile, print)
    if args.command in ("run", "fetch"):
        pipeline.step_fetch(db, profile, print)
    if args.command in ("run", "score"):
        if args.batch:
            scorer.collect_batches(db, 0)
            pipeline.step_score(db, profile, print, batch=True, limit=args.limit)
            if scorer.collect_batches(db, args.wait):
                print("Batch submitted. Run `python run.py collect` later (usually < 1h).")
        else:
            pipeline.step_score(db, profile, print, limit=args.limit)
    if args.command in ("run", "updates"):
        pipeline.step_updates(db, profile, print)
    if args.command in ("run", "score"):
        do_report(db, args)


if __name__ == "__main__":
    main()
