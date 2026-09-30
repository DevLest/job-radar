/* Submit buttons with data-loading show a spinner label; data-confirm asks first. */
export function initLoadingButtons() {
  document.addEventListener('submit', e => {
    const btn = e.submitter;
    if (btn && btn.dataset.loading) { setTimeout(() => { btn.classList.add('is-loading'); btn.lastChild.textContent = ' ' + btn.dataset.loading; }, 0); }
    if (btn && btn.dataset.confirm && !window.confirm(btn.dataset.confirm)) e.preventDefault();
  });
}
