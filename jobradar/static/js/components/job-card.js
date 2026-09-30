/* Job card actions (data-act: hide / rate / undo-hide) and whole-card click via data-href. */
import { esc } from '../lib/dom.js';
import { post } from '../lib/http.js';
import { toast } from './toast.js';

async function hide(id, jobCard) {
  const r = await post(`/jobs/${id}/ignore`);
  if (!r.ok) return toast(r.message, 'error');
  jobCard?.classList.add('leaving'); setTimeout(() => jobCard?.remove(), 300);
  toast('Job hidden', 'ok', { label: 'Undo', run: async () => { await post(`/jobs/${id}/ignore`, { undo: 1 }); location.reload(); } });
}

async function rate(act, id, jobCard) {
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

export function initJobCards() {
  document.addEventListener('click', async e => {
    const act = e.target.closest('[data-act]');
    const cardEl = e.target.closest('[data-href]');
    if (!act) { if (cardEl && !e.target.closest('a, button, input, select, form')) location.href = cardEl.dataset.href; return; }
    e.preventDefault(); e.stopPropagation();
    const id = act.dataset.id, jobCard = act.closest('.job-card');
    if (act.dataset.act === 'hide') await hide(id, jobCard);
    if (act.dataset.act === 'rate') await rate(act, id, jobCard);
    if (act.dataset.act === 'undo-hide') { await post(`/jobs/${id}/ignore`, { undo: 1 }); location.reload(); }
  });
}
