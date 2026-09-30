/* Application page: status-track steps and [data-set-status] buttons (e.g. Re-open) set the status. */
import { $$ } from '../lib/dom.js';
import { post } from '../lib/http.js';
import { toast } from './toast.js';

async function setStatus(id, status) {
  const r = await post(`/applications/${id}/status`, { status });
  if (!r.ok) return toast(r.message, 'error');
  toast(r.message); setTimeout(() => location.reload(), 500);
}

export function initStatusTrack() {
  $$('.status-track button').forEach(b => b.addEventListener('click', () => setStatus(b.dataset.id, b.dataset.status)));
  $$('[data-set-status]').forEach(b => b.addEventListener('click', () => setStatus(b.dataset.id, b.dataset.setStatus)));
}
