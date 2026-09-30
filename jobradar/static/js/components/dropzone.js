/* CV dropzone: choosing or dropping a file submits the upload form and shows the "analyzing" card. */
import { $ } from '../lib/dom.js';

export function initDropzone() {
  const dz = $('.dropzone');
  if (!dz) return;
  const input = $('input[type=file]', dz), form = dz.closest('form');
  const go = () => { if (!input.files.length) return; $('.analyzing').classList.add('show'); dz.classList.add('hidden'); form.submit(); };
  input.addEventListener('change', go);
  ['dragenter', 'dragover'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove('over'); }));
  dz.addEventListener('drop', e => { input.files = e.dataTransfer.files; go(); });
}
