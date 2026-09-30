"""Self-contained HTML + CSV report of scored jobs. No tokens involved."""

from __future__ import annotations

import csv
import html
import json
from datetime import datetime
from pathlib import Path

CSS = """
:root{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1b;--mute:#6b6b66;--line:#e4e4df;--apply:#1f7a4d;--maybe:#a86b00;--skip:#9b2c2c}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--card:#1e1e1c;--fg:#ecece8;--mute:#9a9a93;--line:#33332f;--apply:#4cc38a;--maybe:#e0a33a;--skip:#e0706e}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px}h1{font-size:20px;margin:0 0 4px}.sub{color:var(--mute);margin-bottom:16px}
.bar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}.bar input,.bar select{padding:6px 10px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg)}
.job{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin-bottom:10px;display:grid;grid-template-columns:56px 1fr;gap:14px}
.score{font-size:22px;font-weight:700;text-align:center}.v{font-size:11px;text-transform:uppercase;letter-spacing:.05em;text-align:center}
.apply{color:var(--apply)}.maybe{color:var(--maybe)}.skip,.error{color:var(--skip)}
.t{font-weight:600;font-size:15px}.t a{color:inherit}.meta{color:var(--mute);font-size:13px}.sum{margin:6px 0}
.chips span{display:inline-block;font-size:12px;padding:1px 8px;border-radius:10px;border:1px solid var(--line);margin:2px 4px 2px 0}
.miss{opacity:.7;text-decoration:line-through}.flag{border-color:var(--skip)!important;color:var(--skip)}
.id{font-family:ui-monospace,monospace;font-size:11px;color:var(--mute)}
"""

JS = """
const q=document.getElementById('q'),v=document.getElementById('v');
function f(){const s=q.value.toLowerCase(),vv=v.value;document.querySelectorAll('.job').forEach(e=>{
e.style.display=(e.textContent.toLowerCase().includes(s)&&(!vv||e.dataset.v===vv))?'':'none'})}
q.oninput=f;v.onchange=f;
"""


def _chips(items, cls=""):
    return "".join(f'<span class="{cls}">{html.escape(i)}</span>' for i in items)


def build(db, out_dir: Path, min_score: int = 0) -> Path:
    out_dir.mkdir(exist_ok=True)
    rows = db.rows("stage='scored' AND verdict!='error' AND score>=? AND status NOT IN ('ignored') "
                   "ORDER BY score DESC, posted_at DESC", (min_score,))
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    cards = []
    with open(out_dir / f"jobs_{stamp}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["score", "verdict", "title", "company", "location", "salary", "rate_fit", "setup_fit",
                    "summary", "url", "source", "posted", "status", "id"])
        for r in rows:
            a = json.loads(r["analysis"] or "{}")
            w.writerow([r["score"], r["verdict"], r["title"], r["company"], r["location"][:80],
                        a.get("salary_stated", ""), a.get("rate_fit"), a.get("setup_fit"), a.get("summary"),
                        r["url"], r["source"], (r["posted_at"] or "")[:10], r["status"], r["id"]])
            status = f' · <b>{html.escape(r["status"])}</b>' if r["status"] else ""
            cards.append(f"""<div class="job" data-v="{r['verdict']}">
<div><div class="score {r['verdict']}">{r['score']}</div><div class="v {r['verdict']}">{r['verdict']}</div></div>
<div><div class="t"><a href="{html.escape(r['url'])}" target="_blank" rel="noopener">{html.escape(r['title'])}</a></div>
<div class="meta">{html.escape(r['company'] or '')} · {html.escape((r['location'] or 'n/a')[:80])} · {html.escape(a.get('salary_stated') or 'pay not stated')}
 · via {r['source']} · {(r['posted_at'] or '')[:10]}{status}</div>
<div class="sum">{html.escape(a.get('summary', ''))}</div>
<div class="chips">{_chips(a.get('matched_skills', []))}{_chips(a.get('missing_skills', []), 'miss')}{_chips(a.get('red_flags', []), 'flag')}</div>
<div class="id">rate: {a.get('rate_fit')} · setup: {a.get('setup_fit')} · seniority: {a.get('seniority_fit')} · id: {html.escape(r['id'])}</div>
</div></div>""")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Radar</title><style>{CSS}</style></head><body><main>
<h1>Job Radar</h1><div class="sub">{len(rows)} scored matches · generated {datetime.now():%Y-%m-%d %H:%M} · listings link to their original source</div>
<div class="bar"><input id="q" placeholder="Filter text..."><select id="v"><option value="">All verdicts</option>
<option value="apply">Apply</option><option value="maybe">Maybe</option><option value="skip">Skip</option></select></div>
{''.join(cards) or '<p>No scored jobs yet.</p>'}
</main><script>{JS}</script></body></html>"""
    path = out_dir / "latest.html"
    path.write_text(page, encoding="utf-8")
    return path
