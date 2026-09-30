/* Toast notifications; also replays server flash messages from #flashes. */
import { $, esc } from '../lib/dom.js';
import { ICON_CHECK } from '../lib/icons.js';

export function toast(msg, kind = 'ok', action) {
  if (!msg) return;
  const t = document.createElement('div');
  t.className = 'toast ' + (kind === 'error' ? 'error' : '');
  t.innerHTML = `<span class="t-ico">${kind === 'error' ? '!' : ICON_CHECK}</span><span>${esc(msg)}</span>`;
  if (action) {
    const b = document.createElement('button'); b.textContent = action.label;
    b.onclick = () => { action.run(); t.remove(); }; t.appendChild(b);
  }
  $('#toasts').appendChild(t);
  setTimeout(() => { t.classList.add('out'); setTimeout(() => t.remove(), 300); }, action ? 6000 : 4200);
}

export function initToasts() {
  window.toast = toast;
  try { JSON.parse($('#flashes')?.textContent || '[]').forEach(([k, m]) => toast(m, k)); } catch (e) {}
}
