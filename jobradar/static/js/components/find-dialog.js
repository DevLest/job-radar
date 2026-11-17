/* "Find jobs": the button runs everything that applies in one click; the options dialog can switch
   parts off or pick half-price rating. */
import { $, $$ } from '../lib/dom.js';
import { post } from '../lib/http.js';
import { toast } from './toast.js';
import { startPolling } from './task-progress.js';

async function startFind(options) {
  const r = await post('/tasks/find', options);
  if (!r.ok) { toast(r.message, 'error'); return false; }
  startPolling();
  return true;
}

function chosenOptions(dialog) {
  const checked = id => !!$('#find-' + id, dialog)?.checked;
  return {
    alerts: checked('alerts'), fetch: checked('fetch'), score: checked('score'), updates: checked('updates'),
    score_mode: $('[name=score-mode]:checked', dialog)?.value || 'now',
  };
}

export function initFindDialog() {
  const dialog = $('#find-dialog');
  $$('[data-open-find], a[href="#find"]').forEach(b => b.addEventListener('click', e => { e.preventDefault(); startFind({}); }));
  $$('[data-find-options]').forEach(b => b.addEventListener('click', () => dialog?.showModal()));
  const scoreToggle = $('#find-score');
  const syncScore = () => $$('[name=score-mode]').forEach(r => r.disabled = !scoreToggle?.checked);
  scoreToggle?.addEventListener('change', syncScore); syncScore();
  $('#find-start')?.addEventListener('click', async () => {
    if (await startFind(chosenOptions(dialog))) dialog.close();
  });
}
