/* Applications board: drag cards between columns, or change status with the card's select. */
import { $, $$ } from '../lib/dom.js';
import { post } from '../lib/http.js';
import { toast } from './toast.js';

function updateCounts() {
  $$('.col').forEach(c => {
    const n = $$('.app-card', c).length; $('.col-head .badge', c).textContent = n;
    $('.empty-col', c)?.classList.toggle('hidden', n > 0);
  });
}

export function initBoard() {
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
}
