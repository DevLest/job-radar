/* <dialog> helpers: [data-open-dialog="#id"] opens, [data-close] and backdrop clicks close. */
import { $, $$ } from '../lib/dom.js';

export function initDialogs() {
  $$('[data-open-dialog]').forEach(b => b.addEventListener('click', e => { e.preventDefault(); $(b.dataset.openDialog)?.showModal(); }));
  $$('dialog [data-close]').forEach(b => b.addEventListener('click', () => b.closest('dialog').close()));
  $$('dialog').forEach(d => d.addEventListener('click', e => { if (e.target === d) d.close(); }));
}
