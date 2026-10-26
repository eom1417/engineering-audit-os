// S-54 What changing a file touches (PRB-14), the sheet one problem opens beside its files: EAOS's impact action
// (a free read, eaos/analysis/maps/impact.py) on the check's facts: who imports it directly and further, the code paths and entry
// points through it, the tests that reach it, and the files that change with it in the history. Nothing is estimated.
import { t, tn, num, esc, icon, code, href, sheet, data } from 'eaos';
import { read } from '../understand-kit/reads.js';
import { nm } from '../understand-kit/kit.js';

const go = h => `href="${h}" data-act="go" data-href="${h}"`;
const fileRow = f => `<li class="row" style="min-height:44px">${icon('file', 'icon--sm muted')}<span class="row__main">${code(f)}</span></li>`;
const more = (n, shown) => (n > shown ? `<li class="row small muted" style="min-height:40px">${esc(t('un.comp.andmore', { n: num(n - shown) }))}</li>` : '');

/** The code path a traced flow is (paths.json paths[].flow), to open it. */
function pathOfFlow(id) {
  const p = ((data.section('paths') || {}).paths || []).find(x => x.flow === id);
  return p || null;
}

sheet('impact', {
  kind: 'drawer',
  needs: ['paths'],
  render(path) {
    const head = { title: esc(t('pd.touches')), sub: code(path) };
    const got = read('impact', { target: path });
    const copy = `<button class="btn btn--quiet btn--block" data-act="copy" data-text="eaos impact ${esc(path)}">${icon('copy')}${t('pv.copy')}</button>`;
    if (got.state === 'offline') return Object.assign(head, { body: nm(t('un.imp.offline'), t('un.imp.offline.why')), foot: copy });
    if (got.state === 'loading') return Object.assign(head, { body: `<p class="small muted" role="status" aria-busy="true">${t('un.imp.reading')}</p>`, foot: copy });
    if (got.state === 'failed') return Object.assign(head, { body: `<p class="small" role="alert">${icon('warn', 'icon--sm')} ${esc(got.error || '')}</p>`, foot: copy });
    const im = got.answer || {};
    const direct = im.direct_dependents || [], further = im.transitive_dependents || [];
    const flows = im.flows || [], entries = im.entry_points || [], tests = im.covering_tests || [], partners = im.change_partners || [];
    return Object.assign(head, {
      body: `<p>${esc(t('un.imp.lede', { d: tn('un.pl.file2', direct.length), f: tn('un.pl.file2', further.length), p: tn('un.pl.path', flows.length), t: tn('un.pl.file2', tests.length) }))}</p>
        <p class="free-band">${icon('check', 'icon--sm')}${t('un.imp.free')}</p>
        <div><div class="block-title">${esc(t('un.imp.importers', { n: num(direct.length) }))}</div>
          ${direct.length ? `<ul class="panel rows">${direct.slice(0, 8).map(fileRow).join('')}${more(direct.length, 8)}</ul>` : `<p class="small muted">${t('un.imp.noimporters')}</p>`}
          ${further.length ? `<p class="small muted" style="margin-top:4px">${esc(t('un.imp.further', { n: tn('un.pl.file2', further.length), depth: num(im.depth || 3) }))}</p>` : ''}</div>
        <div><div class="block-title">${t('un.imp.flows')}</div>${flows.length || entries.length ? `<div class="panel rows">${flows.map(f => {
          const p = pathOfFlow(f.flow_id);
          const inner = `${icon('code', 'icon--sm muted')}<span class="row__main"><span class="row__title small">${code(f.route || f.flow_id)}</span><span class="row__meta" style="display:block">${code(f.entry)}</span></span>`;
          return p ? `<a class="row" ${go(href('/understand/paths/' + encodeURIComponent(p.id)))}>${inner}${icon('chev', 'icon--sm icon--dir muted')}</a>` : `<div class="row">${inner}</div>`;
        }).join('')}${entries.map(e => `<div class="row">${icon('external', 'icon--sm muted')}<span class="row__main"><span class="row__title small">${code(e.route || e.surface)}</span><span class="row__meta" style="display:block">${code(e.location)}</span></span></div>`).join('')}</div>`
          : `<p class="small muted">${t('un.imp.noflows')}</p>`}</div>
        <div><div class="block-title">${t('un.imp.tests')}</div>${tests.length ? `<ul class="panel rows">${tests.slice(0, 8).map(f => `<li class="row" style="min-height:44px">${icon('check', 'icon--sm ok-ic')}<span class="row__main">${code(f)}</span></li>`).join('')}${more(tests.length, 8)}</ul>` : `<p class="small muted">${t('un.imp.notests')}</p>`}</div>
        <div><div class="block-title">${t('un.imp.together')}</div>${partners.length ? `<ul class="panel rows">${partners.map(x => `<li class="row" style="min-height:48px"><span class="row__main">${code(x.path)}<span class="un-together" aria-hidden="true"><i style="transform:scaleX(${Math.min(1, x.confidence || 0)})"></i></span></span><span class="small num">${esc(t('un.imp.pct', { p: Math.round((x.confidence || 0) * 100) }))}</span></li>`).join('')}</ul>
          <p class="small muted" style="margin-top:4px">${t('un.imp.together.note')}</p>` : `<p class="small muted">${t('un.imp.nopartners')}</p>`}</div>
        ${(im.limits || []).length ? `<p class="small muted">${t('un.imp.limits')}</p>` : ''}`,
      foot: copy,
    });
  },
});
