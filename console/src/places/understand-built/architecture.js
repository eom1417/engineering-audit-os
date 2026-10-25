// S-35 architecture and design sources (SYS-17): the architecture in brief (from the report's sections: today's and
// the target's components, the links, the import cycles, the decisions' records, the documents), the design standard and its free sources
// (design_brief), a suggested design for "what the product is", and "Adopt this design…" (design_choose saves it as
// DESIGN.md beside the report; the screen review then judges every page against it), previewed free first.
import { t, tn, num, esc, icon, code, href, screen, act, setQuery, parseHash, data, offline } from 'eaos';
import { tabs, facts, fold, start, nm, enc, loading, emptyView } from '../understand-kit/kit.js';
import { read } from '../understand-kit/reads.js';
import { actionSheet } from '../understand-kit/preview.js';

const NEEDS = ['docs', 'system'];
const waitHTML = got => (got.state === 'loading' ? `<p class="small muted" role="status" aria-busy="true">${t('un.arch.reading')}</p>`
  : got.state === 'offline' ? nm(t('un.arch.offline'), t('un.arch.offline.why')) : `<p class="small" role="alert">${icon('warn', 'icon--sm')} ${esc(got.error || '')}</p>`);
const DOCS = ['TARGET-ARCHITECTURE.md', 'CURRENT-STATE.md'];

/** The architecture in brief, from the report's sections (system.json, docs.json): no action to run. */
function summary() {
  const sys = data.section('system');
  if (!sys) return nm(t('un.comp.nm'), t('un.comp.nm.why'));
  const c = sys.counts || {}, v = k => (c[k] ? c[k].value : null);
  const docs = (data.section('docs') || {}).docs || [];
  const named = DOCS.map(p => docs.find(d => d.path === p)).filter(Boolean);
  return `<div class="panel panel__pad">${facts([
    [t('un.arch.today'), esc(tn('un.pl.comp', v('components') || sys.current.nodes.length))],
    [t('un.arch.target'), `<a class="link" href="${href('/understand/story')}">${esc(tn('un.pl.comp', v('target_components') || sys.target.nodes.length))}</a>`],
    [t('un.arch.links'), esc(t('un.arch.links.v', { links: num(v('edges')), imports: num(v('imports')) }))],
    [t('un.arch.cycles'), num(sys.current.edges.filter(e => e.cycle).length)],
    [t('un.arch.decisions'), esc(tn('un.pl.doc', docs.filter(d => d.group === 'adr').length))],
    named.length ? [t('un.arch.docs'), named.map(d => `<a class="link" href="${href('/understand/library/' + enc(d.path))}">${code(d.path)}</a>`).join(' ')] : null,
  ])}</div>`;
}
function sources(got) {
  if (!got) return `<a class="btn btn--secondary btn--sm" href="${href('/understand/architecture', { sources: '1' })}">${t('un.arch.showsources')}</a>`;
  if (got.state !== 'ready') return waitHTML(got);
  const a = got.answer || {};
  const fonts = ((a.fonts || {}).arabic || []);
  return `<div class="panel">
    ${fold(t('un.arch.standard'), esc(tn('un.pl.rule', (a.standard || []).length)), `<ul class="un-doc__ul">${(a.standard || []).map(s => `<li>${esc(s)}</li>`).join('')}</ul>`)}
    ${fold(t('un.arch.fonts'), esc(tn('un.pl.font', fonts.length)), `<ul class="rows">${fonts.map(f => `<li class="row small" style="padding-inline:0"><span class="row__main"><span class="row__title">${esc(f.name)}</span><span class="row__meta" style="display:block">${esc(f.for)}</span></span>${code(f.id)}</li>`).join('')}</ul>`)}
    ${fold(t('un.arch.libs'), esc(tn('un.pl.source', Object.keys(a.sources || {}).length)), `<ul class="rows">${Object.entries(a.sources || {}).map(([k, v]) => `<li class="row small" style="padding-inline:0"><span class="row__main"><span class="row__title">${code(k)}</span><span class="row__meta" style="display:block">${esc(v.offers)}</span></span></li>`).join('')}</ul>`)}
  </div>`;
}

// What the design brief suggests for the described product, and its line under the form
function suggestionHTML(a, product, brief) {
  const suggestion = a.suggestion || '';
  if (suggestion) return `<div class="panel panel__pad" style="margin-top:12px"><div class="block-title">${esc(t('un.arch.suggested.for', { product }))}</div><pre class="code un-pre" tabindex="0">${esc(suggestion)}</pre></div>
        <div class="actions">${start('adopt', esc(t('un.arch.adopt')), 'btn--primary', 'data-fk="adopt"')}<p class="actions__note">${t('un.arch.adopt.note.v')}</p></div>`;
  return product && brief && brief.state === 'ready' ? `<p class="small muted">${t('un.arch.nosuggestion')}</p>` : '';
}

function archPage(ctx) {
  if (ctx.state === 'empty') return emptyView('architecture');
  const product = ctx.query.product || '';
  // the design sources are an action of their own: asked when the person opens them or describes the product
  const brief = product || ctx.query.sources ? read('design_brief', product ? { product } : {}) : null;
  const a = brief && brief.state === 'ready' ? brief.answer || {} : {};
  return `<div class="page">
    ${tabs('architecture')}
    <h1 class="lede">${t('un.arch.lede')}</h1>
    <p class="guide">${t('un.arch.guide')}</p>
    <section class="section"><h2 class="h2" style="margin-bottom:12px">${t('un.arch.summary')}</h2>${summary()}</section>
    <section class="section"><h2 class="h2" style="margin-bottom:12px">${t('un.arch.sources')}</h2>${sources(brief)}</section>
    <section class="section"><h2 class="h2" style="margin-bottom:12px">${t('un.arch.pick')}</h2>
      ${a.current ? `<p class="small"><span class="tag tag--ok">${icon('check')}${t('un.arch.current')}</span></p>` : `<p class="small muted">${t('un.arch.nocurrent')}</p>`}
      <form class="un-product" data-form="un-product"><label class="field"><span class="block-title">${t('un.arch.product')}</span>
        <input class="input" name="product" data-fk="un-product" value="${esc(product)}" placeholder="${esc(t('un.arch.product.ph'))}" autocomplete="off"></label>
        <button class="btn btn--secondary btn--sm" data-act="un-product" style="margin-top:8px">${t('un.arch.suggest')}</button></form>
      ${suggestionHTML(a, product, brief)}
    </section>
  </div>`;
}
screen({ id: 'S-35', path: '/understand/architecture', place: 'understand', needs: NEEDS, title: () => t('un.v.architecture'), render: archPage, loading: () => loading(t('un.arch.reading')) });
act('un-product', el => { const v = el.closest('form').querySelector('input').value.trim(); setQuery({ product: v || null }); });

const suggestionOf = () => { const p = parseHash().query.product; const got = p && !offline() ? read('design_brief', { product: p }) : null; return got && got.state === 'ready' ? (got.answer || {}).suggestion || '' : ''; };
actionSheet('adopt', {
  action: 'design_choose',
  title: () => t('un.arch.adopt.title'),
  inputs: () => ({ content: suggestionOf() }),
  ready: () => !!suggestionOf(),
  command: () => 'eaos design-choose DESIGN.md',
  done: () => t('un.arch.adopted'),
});
