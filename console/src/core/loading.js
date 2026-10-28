// The loading state a screen shows while its code or its sections are read: still blocks, no shimmer.
import { esc } from './format.js';
import { t } from './i18n.js';
import { skeletonRows } from './parts.js';

export function loadingHTML() {
  return `<div class="page" aria-busy="true"><h1 class="lede">${esc(t('st.loading'))}</h1>
    ${skeletonRows(3, [40, 85], { cls: 'mt-6' })}</div>`;
}
