// Scroll regions (code, wide tables) are reachable by keyboard and named (axe: scrollable-region-focusable).
import { t } from './i18n.js';

export function a11yRegions(root) {
  (root || document).querySelectorAll('.code, .ac-table-wrap, .un-table-wrap, .un-pre').forEach(el => {
    if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '0');
    if (!el.hasAttribute('role')) el.setAttribute('role', 'region');
    if (!el.hasAttribute('aria-label') && !el.hasAttribute('aria-labelledby')) el.setAttribute('aria-label', t(el.matches('.code, .un-pre') ? 'a11y.code' : 'a11y.table'));
  });
}
