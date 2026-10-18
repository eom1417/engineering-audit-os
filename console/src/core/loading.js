// The loading state a screen shows while its code or its sections are read: still blocks, no shimmer.
import { esc } from './format.js';
import { t } from './i18n.js';

export function loadingHTML() {
  return `<div class="page" aria-busy="true"><h1 class="lede">${esc(t('st.loading'))}</h1>
    <ul class="panel rows" style="margin-top:24px">${[1, 2, 3].map(() => `<li class="row"><span style="flex:1;display:grid;gap:8px"><span class="skel-line" style="width:40%"></span><span class="skel-line" style="width:85%"></span></span></li>`).join('')}</ul></div>`;
}
