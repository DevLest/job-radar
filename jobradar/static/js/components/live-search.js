/* Instant client-side filtering of job cards by their data-search text. */
import { $, $$ } from '../lib/dom.js';

export function initLiveSearch() {
  const live = $('[data-live-search]');
  live?.addEventListener('input', () => {
    const q = live.value.trim().toLowerCase();
    let shown = 0;
    $$('.job-card').forEach(c => { const hit = !q || c.dataset.search.includes(q); c.classList.toggle('hidden', !hit); shown += hit; });
    $('#no-results')?.classList.toggle('hidden', shown > 0);
  });
}
