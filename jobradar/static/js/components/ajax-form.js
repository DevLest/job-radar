/* form[data-ajax]: submit in the background and show a toast ("reload" reloads after success). */
import { $$ } from '../lib/dom.js';
import { post } from '../lib/http.js';
import { toast } from './toast.js';

export function initAjaxForms() {
  $$('form[data-ajax]').forEach(f => f.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = e.submitter; btn?.classList.add('is-loading');
    const r = await post(btn?.formAction && btn.hasAttribute('formaction') ? btn.formAction : f.action, new FormData(f), true);
    btn?.classList.remove('is-loading');
    toast(r.message || (r.ok ? 'Done' : 'Something went wrong'), r.ok ? 'ok' : 'error');
    if (r.ok && f.dataset.ajax === 'reload') setTimeout(() => location.reload(), 700);
  }));
}
