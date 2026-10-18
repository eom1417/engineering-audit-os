// S-30 data stores and write chains (SYS-09) and S-31 one store (SYS-10), on data_paths.json: where each piece of
// data is kept, which files write and read it (a store written from several files needs attention first), how
// data travels from the field to the column (each tier known or not, and why), the server routes, and the chain of
// every write. Today, the change and the target.
import { t, tn, num, esc, icon, code, href, screen, data } from 'eaos';
import { tabs, seg, prov, search, count, fold, facts, enc, back, loading, notMeasured, empty, notFound, matches, where } from '../understand-kit/kit.js';

const NEEDS = ['data_paths', 'coverage'];
const TIERS = ['field', 'form', 'key', 'caller', 'endpoint', 'handler', 'column'];
const D = () => data.section('data_paths');
const own = st => (!st.writers.length ? 'readonly' : st.writers.length === 1 ? 'one' : 'many');
const KIND = { table: 'layers', auth: 'lock', resource: 'external', rpc: 'code' };
const CHANGE = { single_already: 'single', merged_in_target: 'merged', still_multiple: 'multiple' };
const target = st => (!st.target || st.target.single == null ? (own(st) === 'readonly' ? 'readonly' : null) : st.target.single ? 'one' : 'several');
const kindWord = k => t('un.store.' + k);

function ownTag(st) {
  const o = own(st);
  return o === 'many' ? `<span class="tag tag--caution">${icon('warn')}${esc(t('un.data.many', { n: tn('un.pl.file2', st.writers.length) }))}</span>`
    : o === 'one' ? `<span class="tag tag--ok">${icon('check')}${t('un.data.one')}</span>` : `<span class="tag tag--state">${t('un.data.readonly')}</span>`;
}
function storeRow(st, mode) {
  const tg = target(st);
  const meta = mode === 'change' ? (st.change ? t('un.data.change.' + CHANGE[st.change]) : t('un.data.change.none'))
    : mode === 'target' ? (tg ? t('un.data.target.' + tg) : t('un.data.target.none'))
    : `${kindWord(st.kind)}${t('list.sep')}${esc(t('un.data.wr', { w: num(st.writers.length), r: num(st.readers.length) }))}`;
  return `<a class="row" href="${href('/understand/data/' + enc(st.id))}">${icon(KIND[st.kind] || 'folder', 'muted')}
    <span class="row__main"><span class="un-gaprow__top">${code(st.name || st.id)}</span><span class="row__meta" style="display:block">${meta}</span></span>
    <span class="row__end">${ownTag(st)}</span>${icon('chev', 'icon--sm icon--dir muted')}</a>`;
}
function tiers(d) {
  return `<ol class="un-flowline">${(d.tiers || []).map(r => `<li><span class="un-flowline__from">${t('un.tier.' + r.id)}</span>
    <span class="un-flowline__known ${r.state === 'partial' ? 'caution-ic' : ''}">${r.state === 'measured' || r.state === 'partial' ? esc(t('un.tier.known', { k: num(r.known.value) })) : t('un.tier.' + r.state)}
      ${(r.gaps || []).map(g => ` <span class="small muted">${esc(t('un.tier.gap', { why: g.reason, n: tn('un.pl.path', g.paths) }))}</span>`).join('')}</span></li>`).join('')}</ol>`;
}

function dataPage(ctx) {
  if (ctx.state === 'empty') return empty(t('un.idx.empty'), t('un.idx.empty.guide'));
  const d = D();
  if (!d) return notMeasured('data', 'data_paths');
  const q = ctx.query;
  const mode = q.mode === 'change' || q.mode === 'target' ? q.mode : 'today';
  let stores = d.stores.slice();
  if (q.q) stores = stores.filter(st => matches([st.id, st.name, st.kind, kindWord(st.kind), st.writers.join(' '), st.readers.join(' '), st.endpoints.join(' ')].join(' '), q.q));
  const many = d.stores.filter(st => own(st) === 'many').sort((a, b) => b.writers.length - a.writers.length);
  return `<div class="page page--wide">
    ${tabs('data')}
    <h1 class="lede">${esc(t('un.data.lede', { n: tn('un.pl.store', d.stores.length), k: num(many.length) }))}</h1>
    <p class="guide">${t('un.data.guide')}</p>
    ${many.length ? `<section class="section" aria-labelledby="att-h" style="margin-top:24px"><div class="section-head"><h2 id="att-h">${t('un.data.attention')}</h2></div>
      <div class="panel rows">${many.map(st => `<a class="row row--you" href="${href('/understand/data/' + enc(st.id))}"><span class="row__main"><span class="row__title">${esc(t('un.data.att.row', { store: st.name || st.id, n: tn('un.pl.file2', st.writers.length) }))}</span>
        <span class="row__meta" style="display:block">${st.writers.map(code).join(' ')}</span></span>${icon('chev', 'icon--dir muted')}</a>`).join('')}</div></section>` : ''}
    ${mode !== 'today' ? prov(d.provenance) : ''}
    <div class="ptools">${seg('mode', [['today', t('un.story.today')], ['change', t('un.story.change')], ['target', t('un.story.target')]], mode, t('un.comp.mode'), { dflt: 'today' })}${search(q.q, t('un.data.search'))}</div>
    <div class="listhead">${count(stores.length, d.stores.length)}</div>
    ${stores.length ? `<div class="panel rows">${stores.map(st => storeRow(st, mode)).join('')}</div>` : `<div class="panel empty"><p class="empty__title">${t(d.stores.length ? 'un.data.none' : 'un.data.nostores')}</p></div>`}
    <div class="panel section">
      ${fold(t('un.data.chain'), t('un.data.chain.sum'), tiers(d))}
      ${fold(t('un.data.endpoints'), esc(tn('un.pl.endpoint', d.endpoints.length)), d.endpoints.length ? `<div class="un-table-wrap"><table class="un-table"><thead><tr><th scope="col">${t('un.data.ep')}</th><th scope="col">${t('un.data.ep.store')}</th><th scope="col">${t('un.data.ep.op')}</th><th scope="col">${t('un.data.ep.keys')}</th></tr></thead>
        <tbody>${d.endpoints.map(e => `<tr><td>${code(e.label)}</td><td>${e.store ? code(e.store) : `<span class="muted">${t('un.data.ep.nostore')}</span>`}</td><td>${esc(e.operation)}</td><td>${(e.keys || []).length ? e.keys.map(code).join(' ') : '—'}</td></tr>`).join('')}</tbody></table></div>` : `<p class="small muted">${t('un.none')}</p>`)}
      ${(d.violations || []).length ? fold(t('un.data.violations'), esc(tn('un.pl.store', d.violations.length)), `<ul class="rows">${d.violations.map(x => `<li class="row small" style="padding-inline:0">${code(x.subject)}<span class="row__main muted">${esc(t('un.data.many', { n: tn('un.pl.file2', x.writers.length) }))}</span></li>`).join('')}</ul>`) : ''}
    </div>
  </div>`;
}
screen({ id: 'S-30', path: '/understand/data', place: 'understand', needs: NEEDS, title: () => t('un.v.data'), render: dataPage, loading: () => loading(t('un.data.loading')) });

function chainHTML(p) {
  return `<ol class="un-chain un-chain--plain">${TIERS.map((tier, k) => {
    const s = p.steps[tier] || { state: 'gap' };
    const value = s.state === 'gap' ? esc(s.reason || t('un.chain.gap')) : s.state === 'direct' ? t('un.chain.direct')
      : (s.keys || s.columns || []).length ? (s.keys || s.columns).map(code).join(' ') : s.handler ? code(s.handler) : s.component ? code(s.component) : s.path ? code(where(s.path, s.line)) : '—';
    return `<li class="un-chain__step ${s.state === 'gap' ? 'un-chain__step--gap' : ''}"><div class="un-chain__a">
      <span class="un-chain__n num">${k + 1}</span><span class="row__main"><span class="small muted">${t('un.tier.' + tier)}</span>
      <span class="un-chain__label">${value}</span>${s.path && s.state !== 'gap' ? `<span class="small muted" style="display:block">${code(where(s.path, s.line))}</span>` : ''}</span></div></li>`;
  }).join('')}</ol>`;
}
function storePage(ctx) {
  const d = D();
  if (!d) return notMeasured('data', 'data_paths');
  const st = d.stores.find(x => x.id === ctx.params.id);
  if (!st) return notFound(ctx.params.id, '/understand/data', t('un.v.data'));
  const fileRow = f => `<li><a class="row" href="${href('/understand/functions', { module: f })}">${icon('file', 'icon--sm muted')}<span class="row__main">${code(f)}</span>${icon('chev', 'icon--sm icon--dir muted')}</a></li>`;
  const eps = d.endpoints.filter(e => e.store === st.id);
  const chains = (d.paths || []).filter(p => p.store === st.id);
  const tg = target(st);
  return `<div class="page">
    ${back('/understand/data', t('un.v.data'))}
    <div class="un-itemtags"><span class="tag tag--state">${kindWord(st.kind)}</span>${ownTag(st)}</div>
    <h1 class="lede un-lede-sm">${t('un.store.lede', { store: code(st.name || st.id), kind: kindWord(st.kind), w: esc(tn('un.pl.file2', st.writers.length)), r: esc(tn('un.pl.file2', st.readers.length)) })}</h1>
    ${tg ? `<p class="guide">${esc(t('un.data.target.' + tg + '.long', { file: (st.target && st.target.components[0]) || st.writers[0] || '' }))}</p>` : ''}
    <section class="section"><div class="panel panel__pad">${facts([
      [t('un.store.kind'), kindWord(st.kind)],
      [t('un.store.client'), st.client ? code(st.client) : `<span class="muted">—</span>`],
      [t('un.store.decl'), st.declared ? code(where(st.declared.path, st.declared.line)) : `<span class="muted">${t('un.store.nodecl')}</span>`],
      [t('un.store.rls'), st.kind !== 'table' ? t('un.store.rls.na') : !st.declared || st.declared.rls == null ? `<span class="muted">${t('nm')}</span>` : t(st.declared.rls ? 'un.store.rls.on' : 'un.store.rls.off')],
      [t('un.store.change'), st.change ? t('un.data.change.' + CHANGE[st.change]) : t('un.data.change.none')],
      [t('un.store.target'), tg ? t('un.data.target.' + tg) : t('un.data.target.none')],
      st.target && (st.target.unmapped || []).length ? [t('un.store.unmapped'), st.target.unmapped.map(code).join(' ')] : null,
    ])}</div></section>
    <section class="section"><div class="section-head"><h2>${t('un.store.writers')}</h2><span class="small muted">${esc(tn('un.pl.file2', st.writers.length))}</span></div>
      ${st.writers.length ? `<ul class="panel rows">${st.writers.map(fileRow).join('')}</ul>` : `<p class="small muted">${t('un.store.nowriters')}</p>`}</section>
    <section class="section"><div class="section-head"><h2>${t('un.store.readers')}</h2><span class="small muted">${esc(tn('un.pl.file2', st.readers.length))}</span></div>
      ${st.readers.length ? `<ul class="panel rows">${st.readers.map(fileRow).join('')}</ul>` : `<p class="small muted">${t('un.store.noreaders')}</p>`}</section>
    ${eps.length ? `<section class="section"><h2 class="h2" style="margin-bottom:12px">${t('un.data.endpoints')}</h2><div class="panel rows">${eps.map(e => `<div class="row"><span class="row__main">${code(e.label)}<span class="row__meta" style="display:block">${esc(e.operation)}${(e.keys || []).length ? `${t('list.sep')}${t('un.data.ep.keys')}: ${e.keys.map(code).join(' ')}` : ''}</span></span></div>`).join('')}</div></section>` : ''}
    <section class="section"><h2 class="h2">${t('un.store.chains')}</h2>
      ${chains.length ? chains.map((ch, i) => `<div class="un-chainbox"><div class="block-title">${esc(t('un.store.chain', { n: num(i + 1) }))}</div>${chainHTML(ch)}</div>`).join('') : `<p class="small muted" style="margin-top:8px">${t('un.store.nochains')}</p>`}</section>
  </div>`;
}
screen({ id: 'S-31', path: '/understand/data/:id', place: 'understand', needs: NEEDS, title: ctx => ctx.params.id + ' - ' + t('un.v.data'), render: storePage, loading: () => loading(t('un.data.loading')) });
