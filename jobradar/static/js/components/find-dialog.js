/* "Find jobs" dialog: pick what to check, then start the background task. */
import { $, $$ } from '../lib/dom.js';
import { post } from '../lib/http.js';
import { toast } from './toast.js';
import { startPolling } from './task-progress.js';

export function initFindDialog() {
  const findDlg = $('#find-dialog');
  $$('[data-open-find], a[href="#find"]').forEach(b => b.addEventListener('click', e => { e.preventDefault(); findDlg?.showModal(); }));
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
}
