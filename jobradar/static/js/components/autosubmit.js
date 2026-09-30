/* [data-autosubmit] controls submit their form when the value changes. */
import { $$ } from '../lib/dom.js';

export function initAutosubmit() {
  $$('[data-autosubmit]').forEach(el => el.addEventListener('change', () => el.form?.submit()));
}
