// One delegated listener per kind of event: an element names what it does (data-act on click, data-change on change,
// data-input on input) and a screen registers the handler with act(name, fn(el, event)). The global keys: Ctrl/Cmd+K
// opens Search or ask, Esc closes the sheet or clears the selection, Tab stays inside an open sheet.
import { trapFocus, openSheet, closeSheet, sheetOpen } from './sheets.js';
import { refresh } from './router.js';
import { clearSelection, picked, toggle } from '../data/selection.js';
import { toast } from './notices.js';
import { t } from './i18n.js';

const acts = {};
export function act(name, fn) { acts[name] = fn; }
/** Ticking a problem in the list `list` (data-change=`name`): shift with a tick in `ticks` picks the range from the last
 *  one, in the order the list shows; past the selection's cap, the person is told. */
export function tickAct(name, list, ticks) {
  let shift = false;
  document.addEventListener('click', e => { if (e.target.matches && e.target.matches(ticks)) shift = e.shiftKey; }, true);
  act(name, el => {
    const order = Array.from(document.querySelectorAll(`#main ${list} input[data-change="${name}"]`)).map(x => x.value);
    if (toggle(el.value, el.checked, shift, order) === 'max') toast(t('sel.max'), { refusal: true });
    shift = false;
    refresh();
  });
}

document.addEventListener('click', e => {
  const el = e.target.closest('[data-act]');
  if (!el) return;
  const fn = acts[el.dataset.act];
  if (!fn) return;
  if (el.tagName === 'A' || el.tagName === 'BUTTON' || el.classList.contains('scrim')) e.preventDefault();
  fn(el, e);
});
for (const type of ['change', 'input']) {
  document.addEventListener(type, e => {
    const el = e.target.closest(`[data-${type}]`);
    if (el && acts[el.dataset[type]]) acts[el.dataset[type]](el, e);
  });
}
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); openSheet('search'); return; }
  if (e.key === 'Escape') {
    if (sheetOpen()) { e.preventDefault(); closeSheet(); return; }
    if (picked.ids.size) { clearSelection(); refresh(); return; }
  }
  trapFocus(e);
});
