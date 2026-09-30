/* Tag inputs: a .tags box plus the sibling hidden input that holds "a, b, c". */
import { $, $$, esc } from '../lib/dom.js';
import { ICON_X } from '../lib/icons.js';

function initTagBox(box) {
  const hidden = $('input[type=hidden]', box.parentElement);
  const input = $('input.tag-input', box);
  const values = () => $$('.tag', box).map(t => t.dataset.v);
  const sync = () => { hidden.value = values().join(', '); hidden.dispatchEvent(new Event('change', { bubbles: true })); };
  const add = raw => {
    raw.split(',').map(s => s.trim()).filter(Boolean).forEach(v => {
      if (values().map(x => x.toLowerCase()).includes(v.toLowerCase())) return;
      const t = document.createElement('span'); t.className = 'tag'; t.dataset.v = v;
      t.innerHTML = `${esc(v)}<button type="button" aria-label="Remove ${esc(v)}">${ICON_X}</button>`;
      box.insertBefore(t, input);
    });
    sync();
  };
  (hidden.value ? hidden.value.split(',') : []).forEach(v => v.trim() && add(v));
  box.addEventListener('click', e => {
    const x = e.target.closest('.tag button');
    if (x) { x.parentElement.remove(); sync(); } else input.focus();
  });
  input.addEventListener('keydown', e => {
    if ((e.key === 'Enter' || e.key === ',') && input.value.trim()) { e.preventDefault(); add(input.value); input.value = ''; }
    else if (e.key === 'Enter') e.preventDefault();
    else if (e.key === 'Backspace' && !input.value) { const last = $$('.tag', box).pop(); if (last) { last.remove(); sync(); } }
  });
  input.addEventListener('blur', () => { if (input.value.trim()) { add(input.value); input.value = ''; } });
}

export function initTagInputs() {
  $$('.tags').forEach(initTagBox);
}
