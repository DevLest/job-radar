/* Preferences page: client-side tabs, show-if fields and the unsaved-changes bar. */
import { $, $$ } from '../lib/dom.js';

export function initPreferencesPage() {
  const prefs = $('#prefs-form');
  if (!prefs) return;
  const showTab = id => {
    $$('.pref-pane').forEach(p => p.classList.toggle('hidden', p.dataset.tab !== id));
    $$('.prefs-nav a').forEach(a => a.classList.toggle('on', a.dataset.tab === id));
    $('[name=_tab]', prefs).value = id;
    history.replaceState(null, '', `?tab=${id}`);
  };
  $$('.prefs-nav a').forEach(a => a.addEventListener('click', e => { e.preventDefault(); showTab(a.dataset.tab); }));
  const bar = $('#savebar');
  const dirty = () => bar.classList.add('show');
  prefs.addEventListener('input', dirty); prefs.addEventListener('change', dirty);
  $('#savebar-reset')?.addEventListener('click', () => location.reload());
  window.addEventListener('beforeunload', e => { if (bar.classList.contains('show') && !prefs.dataset.submitting) { e.preventDefault(); e.returnValue = ''; } });
  prefs.addEventListener('submit', () => { prefs.dataset.submitting = '1'; });
  const syncShowIf = () => $$('[data-show-if]').forEach(el => {
    const [name, vals] = el.dataset.showIf.split(':');
    const on = $$(`[name="${name}"]:checked`).some(i => vals.split(',').includes(i.value));
    el.classList.toggle('hidden', !on);
  });
  prefs.addEventListener('change', syncShowIf); syncShowIf();
}
