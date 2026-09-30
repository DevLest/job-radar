"""Self-contained HTML + CSV report of scored jobs (python run.py report). No tokens involved."""

from __future__ import annotations

import csv
import html
from datetime import datetime
from pathlib import Path

from ..jobs.job import Job
from ..jobs.job_repository import JobRepository
from .report_assets import CSS, JS

REPORT_WHERE = "stage='scored' AND verdict!='error' AND score>=? AND status NOT IN ('ignored')"
CSV_HEADER = ["score", "verdict", "title", "company", "location", "salary", "rate_fit", "setup_fit",
              "summary", "url", "source", "posted", "status", "id"]


def _chips(items, css_class=""):
    return "".join(f'<span class="{css_class}">{html.escape(item)}</span>' for item in items)


def _csv_row(job: Job) -> list:
    a = job.analysis
    return [job.score, job.verdict, job.title, job.company, job.location[:80], a.get("salary_stated", ""),
            a.get("rate_fit"), a.get("setup_fit"), a.get("summary"), job.url, job.source,
            (job.posted_at or "")[:10], job.status, job.id]


def _card(job: Job) -> str:
    a = job.analysis
    status = f' · <b>{html.escape(job.status)}</b>' if job.status else ""
    return f"""<div class="job" data-v="{job.verdict}">
<div><div class="score {job.verdict}">{job.score}</div><div class="v {job.verdict}">{job.verdict}</div></div>
<div><div class="t"><a href="{html.escape(job.url)}" target="_blank" rel="noopener">{html.escape(job.title)}</a></div>
<div class="meta">{html.escape(job.company or '')} · {html.escape((job.location or 'n/a')[:80])} · {html.escape(a.get('salary_stated') or 'pay not stated')}
 · via {job.source} · {(job.posted_at or '')[:10]}{status}</div>
<div class="sum">{html.escape(a.get('summary', ''))}</div>
<div class="chips">{_chips(a.get('matched_skills', []))}{_chips(a.get('missing_skills', []), 'miss')}{_chips(a.get('red_flags', []), 'flag')}</div>
<div class="id">rate: {a.get('rate_fit')} · setup: {a.get('setup_fit')} · seniority: {a.get('seniority_fit')} · id: {html.escape(job.id)}</div>
</div></div>"""


def _page(jobs: list[Job], cards: list[str]) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Radar</title><style>{CSS}</style></head><body><main>
<h1>Job Radar</h1><div class="sub">{len(jobs)} scored matches · generated {datetime.now():%Y-%m-%d %H:%M} · listings link to their original source</div>
<div class="bar"><input id="q" placeholder="Filter text..."><select id="v"><option value="">All verdicts</option>
<option value="apply">Apply</option><option value="maybe">Maybe</option><option value="skip">Skip</option></select></div>
{''.join(cards) or '<p>No scored jobs yet.</p>'}
</main><script>{JS}</script></body></html>"""


class ReportBuilder:
    def __init__(self, jobs: JobRepository):
        self.jobs = jobs

    def build(self, out_dir: Path, min_score: int = 0) -> Path:
        out_dir.mkdir(exist_ok=True)
        jobs = self.jobs.find(REPORT_WHERE, (min_score,), order="score DESC, posted_at DESC")
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        with open(out_dir / f"jobs_{stamp}.csv", "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(CSV_HEADER)
            writer.writerows(_csv_row(job) for job in jobs)
        path = out_dir / "latest.html"
        path.write_text(_page(jobs, [_card(job) for job in jobs]), encoding="utf-8")
        return path
