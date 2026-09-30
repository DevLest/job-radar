/* [data-reload] buttons (including ones added later) reload the page. */
export function initReload() {
  document.addEventListener('click', e => { if (e.target.closest('[data-reload]')) location.reload(); });
}
