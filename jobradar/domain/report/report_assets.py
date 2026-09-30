"""Inline CSS/JS of the self-contained HTML report."""

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
