/* Job Radar UI - small vanilla JS, no build step. */
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const ICON_CHECK = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';
  const ICON_X = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>';

  // ---------- helpers ----------
  async function post(url, data = {}, asForm = false) {
    const opts = { method: 'POST', headers: { 'X-Requested-With': 'fetch' } };
    if (asForm) opts.body = data; else { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(data); }
    const r = await fetch(url, opts);
    let body = {};
    try { body = await r.json(); } catch (e) { body = { ok: false, message: 'Something went wrong' }; }
    if (!r.ok && body.ok === undefined) body.ok = false;
    return body;
  }
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // ---------- toasts ----------
  function toast(msg, kind = 'ok', action) {
    if (!msg) return;
    const t = document.createElement('div');
    t.className = 'toast ' + (kind === 'error' ? 'error' : '');
    t.innerHTML = `<span class="t-ico">${kind === 'error' ? '!' : ICON_CHECK}</span><span>${esc(msg)}</span>`;
    if (action) {
      const b = document.createElement('button'); b.textContent = action.label;
      b.onclick = () => { action.run(); t.remove(); }; t.appendChild(b);
    }
    $('#toasts').appendChild(t);
    setTimeout(() => { t.classList.add('out'); setTimeout(() => t.remove(), 300); }, action ? 6000 : 4200);
  }
  window.toast = toast;
  try { JSON.parse($('#flashes')?.textContent || '[]').forEach(([k, m]) => toast(m, k)); } catch (e) {}

  // ---------- loading buttons ----------
  document.addEventListener('submit', e => {
    const btn = e.submitter;
    if (btn && btn.dataset.loading) { setTimeout(() => { btn.classList.add('is-loading'); btn.lastChild.textContent = ' ' + btn.dataset.loading; }, 0); }
    if (btn && btn.dataset.confirm && !window.confirm(btn.dataset.confirm)) e.preventDefault();
  });

  // ---------- find jobs dialog + progress ----------
  const findDlg = $('#find-dialog');
  $$('[data-open-find], a[href="#find"]').forEach(b => b.addEventListener('click', e => { e.preventDefault(); findDlg?.showModal(); }));
  $$('dialog [data-close]').forEach(b => b.addEventListener('click', () => b.closest('dialog').close()));
  $$('dialog').forEach(d => d.addEventListener('click', e => { if (e.target === d) d.close(); }));
  const scoreToggle = $('#find-score');
  const syncScore = () => $$('[name=score-mode]').forEach(r => r.disabled = !scoreToggle?.checked);
  scoreToggle?.addEventListener('change', syncScore); syncScore();
  $('#find-start')?.addEventListener('click', async () => {
    const f = findDlg;
    const opts = {
      alerts: $('#find-alerts', f)?.checked, feeds: $('#find-feeds', f)?.checked, updates: $('#find-updates', f)?.checked,
      score: scoreToggle?.checked ? ($('[name=score-mode]:checked', f)?.value || 'now') : 'none',
    };
    const r = await post('/tasks/find', opts);
    if (!r.ok) return toast(r.message, 'error');
    findDlg.close(); startPolling();
  });

  $$('[data-task]').forEach(b => b.addEventListener('click', async () => {
    const r = await post('/tasks/' + b.dataset.task);
    if (!r.ok) return toast(r.message, 'error');
    startPolling();
  }));

  const card = $('#progress');
  let polling = false, sawRunning = false;
  function renderProgress(s) {
    if (!card) return;
    card.classList.remove('hidden');
    const done = !s.running;
    $('.p-title', card).textContent = done ? (s.summary.failed ? 'Finished with a problem' : 'All done!') : 'Working on it…';
    $('.p-spin', card).classList.toggle('hidden', done);
    $('ul', card).innerHTML = s.steps.map(st =>
      `<li class="${st.status}"><span class="st">${st.status === 'done' ? ICON_CHECK : st.status === 'failed' ? ICON_X : ''}</span>
       <span>${esc(st.label)}${st.note ? `<div class="small" style="color:var(--red)">${esc(st.note)}</div>` : ''}</span></li>`).join('');
    $('pre', card).textContent = s.log.join('\n');
    const sum = $('.p-sum', card);
    if (done && s.summary && Object.keys(s.summary).length) {
      const m = s.summary, bits = [];
      bits.push(m.new_matches > 0 ? `<b>${m.new_matches} new match${m.new_matches === 1 ? '' : 'es'}</b> for you.` : 'No new strong matches this time.');
      if (m.new_jobs) bits.push(`${m.new_jobs} new jobs checked.`);
      if (m.waiting) bits.push(`${m.waiting} waiting for an AI rating.`);
      if (m.pending_batches) bits.push('Half-price ratings arrive within ~1 hour.');
      sum.innerHTML = `<p style="margin:0 0 10px">${bits.join(' ')}</p>
        <div class="row"><a class="btn sm primary" href="/jobs?tab=${m.new_matches ? 'best' : 'rated'}">See jobs</a>
        <button class="btn sm" onclick="location.reload()">Refresh page</button></div>`;
      sum.classList.remove('hidden');
    } else sum.classList.add('hidden');
  }
  async function poll() {
    let s;
    try { s = await (await fetch('/api/task')).json(); } catch (e) { polling = false; return; }
    $$('[data-task], [data-open-find]').forEach(b => b.disabled = s.running);
    if (s.running) sawRunning = true;
    if (s.running || (sawRunning && s.steps.length)) renderProgress(s);
    if (s.running) setTimeout(poll, 1200); else polling = false;
  }
  function startPolling() { sawRunning = true; if (!polling) { polling = true; poll(); } }
  $('#progress .p-close')?.addEventListener('click', () => { card.classList.add('hidden'); sawRunning = false; });
  $('#progress .p-log')?.addEventListener('click', () => $('pre', card).classList.toggle('hidden'));
  fetch('/api/task').then(r => r.json()).then(s => { if (s.running) startPolling(); }).catch(() => {});

  // ---------- job card actions ----------
  document.addEventListener('click', async e => {
    const act = e.target.closest('[data-act]');
    const cardEl = e.target.closest('[data-href]');
    if (!act) { if (cardEl && !e.target.closest('a, button, input, select, form')) location.href = cardEl.dataset.href; return; }
    e.preventDefault(); e.stopPropagation();
    const id = act.dataset.id, jobCard = act.closest('.job-card');
    if (act.dataset.act === 'hide') {
      const r = await post(`/jobs/${id}/ignore`);
      if (!r.ok) return toast(r.message, 'error');
      jobCard?.classList.add('leaving'); setTimeout(() => jobCard?.remove(), 300);
      toast('Job hidden', 'ok', { label: 'Undo', run: async () => { await post(`/jobs/${id}/ignore`, { undo: 1 }); location.reload(); } });
    }
    if (act.dataset.act === 'rate') {
      act.classList.add('is-loading'); act.lastChild.textContent = ' Rating…';
      const r = await post(`/jobs/${id}/score`);
      act.classList.remove('is-loading');
      if (!r.ok) { act.lastChild.textContent = ' Rate this job'; return toast(r.message, 'error'); }
      toast(r.message);
      const ring = jobCard?.querySelector('.ring');
      if (ring) { ring.className = `ring v-${r.verdict}`; ring.style.setProperty('--p', r.score); ring.innerHTML = `<b>${r.score}</b>`; }
      const why = jobCard?.querySelector('.why'); if (why) why.textContent = r.summary; else jobCard?.querySelector('.body')?.insertAdjacentHTML('beforeend', `<p class="why">${esc(r.summary)}</p>`);
      act.remove();
    }
    if (act.dataset.act === 'undo-hide') { await post(`/jobs/${id}/ignore`, { undo: 1 }); location.reload(); }
  });

  // instant search
  const live = $('[data-live-search]');
  live?.addEventListener('input', () => {
    const q = live.value.trim().toLowerCase();
    let shown = 0;
    $$('.job-card').forEach(c => { const hit = !q || c.dataset.search.includes(q); c.classList.toggle('hidden', !hit); shown += hit; });
    $('#no-results')?.classList.toggle('hidden', shown > 0);
  });

  // ---------- menus ----------
  document.addEventListener('click', e => {
    const t = e.target.closest('[data-menu]');
    $$('.menu.open').forEach(m => { if (!t || m !== t.parentElement) m.classList.remove('open'); });
    if (t) { e.preventDefault(); t.parentElement.classList.toggle('open'); }
  });

  // ---------- tag inputs ----------
  $$('.tags').forEach(box => {
    const hidden = $('input[type=hidden]', box.parentElement);
    const input = $('input.tag-input', box);
    const values = () => $$('.tag', box).map(t => t.dataset.v);
    const sync = () => { hidden.value = values().join(', '); hidden.dispatchEvent(new Event('change', { bubbles: true })); };
    const add = raw => {
      raw.split(',').map(s => s.trim()).filter(Boolean).forEach(v => {
        if (values().map(x => x.toLowerCase()).includes(v.toLowerCase())) return;
        const t = document.createElement('span'); t.className = 'tag'; t.dataset.v = v;
        t.innerHTML = `${esc(v)}<button type="button" aria-label="Remove ${esc(v)}">${ICON_X}</button>`;
        box.insertBefore(t, input);
      });
      sync();
    };
    (hidden.value ? hidden.value.split(',') : []).forEach(v => v.trim() && add(v));
    box.addEventListener('click', e => {
      const x = e.target.closest('.tag button');
      if (x) { x.parentElement.remove(); sync(); } else input.focus();
    });
    input.addEventListener('keydown', e => {
      if ((e.key === 'Enter' || e.key === ',') && input.value.trim()) { e.preventDefault(); add(input.value); input.value = ''; }
      else if (e.key === 'Enter') e.preventDefault();
      else if (e.key === 'Backspace' && !input.value) { const last = $$('.tag', box).pop(); if (last) { last.remove(); sync(); } }
    });
    input.addEventListener('blur', () => { if (input.value.trim()) { add(input.value); input.value = ''; } });
  });

  // ---------- preferences: tabs, show-if, save bar ----------
  const prefs = $('#prefs-form');
  if (prefs) {
    const showTab = id => {
      $$('.pref-pane').forEach(p => p.classList.toggle('hidden', p.dataset.tab !== id));
      $$('.prefs-nav a').forEach(a => a.classList.toggle('on', a.dataset.tab === id));
      $('[name=_tab]', prefs).value = id;
      history.replaceState(null, '', `?tab=${id}`);
    };
    $$('.prefs-nav a').forEach(a => a.addEventListener('click', e => { e.preventDefault(); showTab(a.dataset.tab); }));
    const bar = $('#savebar');
    const dirty = () => bar.classList.add('show');
    prefs.addEventListener('input', dirty); prefs.addEventListener('change', dirty);
    $('#savebar-reset')?.addEventListener('click', () => location.reload());
    window.addEventListener('beforeunload', e => { if (bar.classList.contains('show') && !prefs.dataset.submitting) { e.preventDefault(); e.returnValue = ''; } });
    prefs.addEventListener('submit', () => { prefs.dataset.submitting = '1'; });
    const syncShowIf = () => $$('[data-show-if]').forEach(el => {
      const [name, vals] = el.dataset.showIf.split(':');
      const on = $$(`[name="${name}"]:checked`).some(i => vals.split(',').includes(i.value));
      el.classList.toggle('hidden', !on);
    });
    prefs.addEventListener('change', syncShowIf); syncShowIf();
  }

  // ---------- board drag & drop ----------
  let dragged = null;
  $$('.app-card[draggable]').forEach(c => {
    c.addEventListener('dragstart', e => { dragged = c; c.classList.add('dragging'); e.dataTransfer.effectAllowed = 'move'; });
    c.addEventListener('dragend', () => { c.classList.remove('dragging'); $$('.col').forEach(x => x.classList.remove('over')); });
  });
  $$('.col[data-status]').forEach(col => {
    col.addEventListener('dragover', e => { if (dragged && col.dataset.status !== 'drafted') { e.preventDefault(); col.classList.add('over'); } });
    col.addEventListener('dragleave', e => { if (!col.contains(e.relatedTarget)) col.classList.remove('over'); });
    col.addEventListener('drop', async e => {
      e.preventDefault(); col.classList.remove('over');
      if (!dragged || dragged.closest('.col') === col) return;
      const card = dragged, from = card.closest('.col');
      col.querySelector('.cards').prepend(card); updateCounts();
      const r = await post(`/applications/${card.dataset.id}/status`, { status: col.dataset.status });
      if (!r.ok) { from.querySelector('.cards').prepend(card); updateCounts(); return toast(r.message || 'Could not move', 'error'); }
      card.querySelector('select').value = col.dataset.status;
      toast(r.message);
    });
  });
  $$('.app-card select').forEach(sel => sel.addEventListener('change', async e => {
    e.stopPropagation();
    const r = await post(`/applications/${sel.dataset.id}/status`, { status: sel.value });
    if (!r.ok) return toast(r.message, 'error');
    toast(r.message); setTimeout(() => location.reload(), 600);
  }));
  $$('.app-card select').forEach(sel => sel.addEventListener('click', e => e.stopPropagation()));
  function updateCounts() {
    $$('.col').forEach(c => {
      const n = $$('.app-card', c).length; $('.col-head .badge', c).textContent = n;
      $('.empty-col', c)?.classList.toggle('hidden', n > 0);
    });
  }

  // status track (application page)
  $$('.status-track button').forEach(b => b.addEventListener('click', async () => {
    const r = await post(`/applications/${b.dataset.id}/status`, { status: b.dataset.status });
    if (!r.ok) return toast(r.message, 'error');
    toast(r.message); setTimeout(() => location.reload(), 500);
  }));

  // ---------- CV dropzone ----------
  const dz = $('.dropzone');
  if (dz) {
    const input = $('input[type=file]', dz), form = dz.closest('form');
    const go = () => { if (!input.files.length) return; $('.analyzing').classList.add('show'); dz.classList.add('hidden'); form.submit(); };
    input.addEventListener('change', go);
    ['dragenter', 'dragover'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add('over'); }));
    ['dragleave', 'drop'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove('over'); }));
    dz.addEventListener('drop', e => { input.files = e.dataTransfer.files; go(); });
  }

  // expandable description
  $$('[data-expand]').forEach(b => b.addEventListener('click', () => {
    const box = $(b.dataset.expand); box.classList.toggle('collapsed');
    b.textContent = box.classList.contains('collapsed') ? 'Show full description' : 'Show less';
  }));

  // AJAX forms (data-ajax): stay on page, show toast
  $$('form[data-ajax]').forEach(f => f.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = e.submitter; btn?.classList.add('is-loading');
    const r = await post(btn?.formAction && btn.hasAttribute('formaction') ? btn.formAction : f.action, new FormData(f), true);
    btn?.classList.remove('is-loading');
    toast(r.message || (r.ok ? 'Done' : 'Something went wrong'), r.ok ? 'ok' : 'error');
    if (r.ok && f.dataset.ajax === 'reload') setTimeout(() => location.reload(), 700);
  }));
})();
