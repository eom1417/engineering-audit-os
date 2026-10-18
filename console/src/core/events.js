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
document.addEventListener('change', e => {
  const el = e.target.closest('[data-change]');
  if (el && acts[el.dataset.change]) acts[el.dataset.change](el, e);
});
document.addEventListener('input', e => {
  const el = e.target.closest('[data-input]');
  if (el && acts[el.dataset.input]) acts[el.dataset.input](el, e);
});
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); openSheet('search'); return; }
  if (e.key === 'Escape') {
    if (sheetOpen()) { e.preventDefault(); closeSheet(); return; }
    if (picked.ids.size) { clearSelection(); refresh(); return; }
  }
  trapFocus(e);
});
