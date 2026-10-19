// Scroll regions (code, wide tables) are reachable by keyboard and named (axe: scrollable-region-focusable).
import { t } from './i18n.js';

export function a11yRegions(root) {
  (root || document).querySelectorAll('.code, .ac-table-wrap, .un-table-wrap, .un-pre').forEach(el => {
    if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '0');
    if (!el.hasAttribute('role')) el.setAttribute('role', 'region');
    if (!el.hasAttribute('aria-label') && !el.hasAttribute('aria-labelledby')) el.setAttribute('aria-label', t(el.matches('.code, .un-pre') ? 'a11y.code' : 'a11y.table'));
  });
  // a segmented control that slides sideways shows its chosen choice (a redraw slid it back to its start)
  (root || document).querySelectorAll('.seg > [aria-pressed="true"], .seg > [aria-current="true"], .seg > [aria-selected="true"]').forEach(on => {
    const seg = on.parentElement, r = on.getBoundingClientRect(), box = seg.getBoundingClientRect();
    seg.scrollLeft += r.left < box.left ? r.left - box.left : r.right > box.right ? r.right - box.right : 0;
  });
}

/** What a person set inside `scope`, held across a redraw of it: the returned function, called once the new markup is
 * in, opens the folds they opened again (a page drawn from live data every few seconds closed them under the person)
 * and focuses the same control (data-fk, else id) with what was typed in it and its caret (it erased the field, or
 * sent the caret to its start, as it was typed). */
export function hold(scope) {
  const opened = scope ? [...scope.querySelectorAll('details[open]')].map(foldKey) : [];
  const a = document.activeElement;
  const fk = scope && a && a !== document.body && scope.contains(a) ? (a.getAttribute('data-fk') || a.id) : null;
  const typing = fk && /^(INPUT|TEXTAREA)$/.test(a.tagName) && a.selectionStart !== null ? { value: a.value, from: a.selectionStart, to: a.selectionEnd } : null;
  return () => {
    if (opened.length) scope.querySelectorAll('details:not([open])').forEach(d => { if (opened.includes(foldKey(d))) d.open = true; });
    const el = fk && (document.querySelector(`[data-fk="${CSS.escape(fk)}"]`) || document.getElementById(fk));
    if (!el) return;
    el.focus({ preventScroll: true });
    if (!typing || el.tagName !== a.tagName) return;
    if (el.value !== typing.value) el.value = typing.value;
    try { el.setSelectionRange(typing.from, typing.to); } catch (e) { /* a field without a caret */ }
  };
}

// A fold by its id, else by its title and which of the folds with that title it is (new events come after them)
function foldKey(d) {
  if (d.id) return d.id;
  const title = d.querySelector('summary') ? d.querySelector('summary').textContent.trim() : '';
  const same = [...d.ownerDocument.querySelectorAll('details')].filter(x => !x.id && x.querySelector('summary') && x.querySelector('summary').textContent.trim() === title);
  return title + '#' + same.indexOf(d);
}
