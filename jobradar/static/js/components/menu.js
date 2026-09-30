/* Dropdown menus: [data-menu] toggles its parent .menu; clicking elsewhere closes. */
import { $$ } from '../lib/dom.js';

export function initMenus() {
  document.addEventListener('click', e => {
    const t = e.target.closest('[data-menu]');
    $$('.menu.open').forEach(m => { if (!t || m !== t.parentElement) m.classList.remove('open'); });
    if (t) { e.preventDefault(); t.parentElement.classList.toggle('open'); }
  });
}
