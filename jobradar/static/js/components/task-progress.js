/* Background task progress card: [data-task] buttons start a task, the card polls /api/task. */
import { $, $$, esc } from '../lib/dom.js';
import { post } from '../lib/http.js';
import { ICON_CHECK, ICON_X } from '../lib/icons.js';
import { toast } from './toast.js';

let card = null, polling = false, sawRunning = false;

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
      <button class="btn sm" data-reload>Refresh page</button></div>`;
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

export function startPolling() { sawRunning = true; if (!polling) { polling = true; poll(); } }

export function initTaskProgress() {
  card = $('#progress');
  $$('[data-task]').forEach(b => b.addEventListener('click', async () => {
    const r = await post('/tasks/' + b.dataset.task);
    if (!r.ok) return toast(r.message, 'error');
    startPolling();
  }));
  $('#progress .p-close')?.addEventListener('click', () => { card.classList.add('hidden'); sawRunning = false; });
  $('#progress .p-log')?.addEventListener('click', () => $('pre', card).classList.toggle('hidden'));
  fetch('/api/task').then(r => r.json()).then(s => { if (s.running) startPolling(); }).catch(() => {});
}
