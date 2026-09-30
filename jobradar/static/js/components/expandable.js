/* [data-expand="#box"] toggles a collapsed description box. */
import { $, $$ } from '../lib/dom.js';

export function initExpandables() {
  $$('[data-expand]').forEach(b => b.addEventListener('click', () => {
    const box = $(b.dataset.expand); box.classList.toggle('collapsed');
    b.textContent = box.classList.contains('collapsed') ? 'Show full description' : 'Show less';
  }));
}
