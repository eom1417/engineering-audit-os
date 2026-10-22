// One delegated listener per kind of event: an element names what it does (data-act on click, data-change on change,
// data-input on input) and a screen registers the handler with act(name, fn(el, event)). The global keys: Ctrl/Cmd+K
// opens Search or ask, Esc closes the sheet or clears the selection, Tab stays inside an open sheet.
import { trapFocus, openSheet, closeSheet, sheetOpen } from './sheets.js';
import { refresh } from './router.js';
import { clearSelection, picked } from '../data/selection.js';

const acts = {};
export function act(name, fn) { acts[name] = fn; }

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
