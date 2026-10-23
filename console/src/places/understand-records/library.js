// S-40 the library (LIB-01, LIB-02, LIB-06) and S-41 one document (LIB-03, LIB-04, LIB-05), on docs.json and
// media.json, and each document's text read alone from the library (14 MB whole: live, /api/sections/library?only=);
// documents by purpose and reading order, search over titles, paths and headings, the images and diagrams; a document
// in the reader's language when the check wrote both, its contents, its links opening in place, its diagrams drawn.
import { t, tn, L, num, esc, icon, code, href, rich, screen, sheet, act, data, prefs, refresh, model, offline, normalize, markdown } from 'eaos';
import { tabs, seg, search, count, fold, nm, enc, back, loading, notMeasured, emptyView, notFound, zoomBar, zoomable, page, matches } from '../understand-kit/kit.js';
import { flowchartSVG, parseFlowchart, mermaidOf, mermaidBlock } from './markdown.js';

const NEEDS = ['docs', 'media', 'cards', 'coverage'];
const ORDER = ['start', 'story', 'plan', 'PLAN', 'adr', 'technical', 'look', 'handover', 'i18n'];
const docs = () => (data.section('docs') || {}).docs || [];
const titleOf = d => (d.titles && d.titles[prefs.lang]) || d.title || d.path;
const minutes = bytes => Math.max(1, Math.round(bytes / 1200));
const docLink = (path, query) => href('/understand/library/' + enc(path), query);
const size = d => t('un.lib.size', { kb: num(Math.max(1, Math.round(d.bytes / 1024))), min: tn('pl.minute', minutes(d.bytes)) });
const groupWord = g => t('un.dg.' + (ORDER.includes(g) ? g : 'other'), { group: g });

/* ---------- the library's parts, read one document or image at a time ---------- */
const items = new Map();
/** The library item (document or image) `id`: read once, then kept; null while it is read, false when absent. */
function item(id) {
  if (!items.has(id)) {
    items.set(id, null);
    data.libraryItems([id]).then(lib => {
      (lib ? lib.documents.concat(lib.images) : []).forEach(x => items.set(x.id, x));
      if (!items.get(id)) items.set(id, false);
      refresh();
    }, () => { items.set(id, false); refresh(); });
  }
  return items.get(id);
}
const textOf = doc => (doc.texts && doc.texts[prefs.lang]) || doc.text;

/* ---------- S-40 the library ---------- */
function imageRow(im) {
  return `<li><button class="row" data-act="sheet" data-sheet="img:${esc(enc(im.id))}" style="width:100%">${icon(im.kind === 'screen' ? 'screen' : im.kind === 'chart' ? 'status' : 'map', 'muted')}
    <span class="row__main"><span class="row__title small">${rich(L(im.title || im.path))}</span>
    <span class="row__meta" style="display:block">${code(im.path)}${im.phase ? `${t('list.sep')}${t('un.phase.' + im.phase)}` : ''}${im.viewport ? `${t('list.sep')}${t('un.vp.' + (im.viewport === 'phone' ? 'phone' : 'desk'))}` : ''}${im.batch ? `${t('list.sep')}${code(im.batch)}` : ''}</span></span>
    <span class="tag tag--state">${t('un.img.' + im.kind)}</span></button></li>`;
}
function docRow(d, heading) {
  return `<a class="row" href="${docLink(d.path, heading ? { at: heading } : null)}">${icon('file', 'muted')}<span class="row__main"><span class="row__title">${rich(titleOf(d))}</span>
    <span class="row__meta" style="display:block">${heading ? `${esc(heading)}${t('list.sep')}` : ''}${code(d.path)}${t('list.sep')}${esc(size(d))}</span></span>${icon('chev', 'icon--sm icon--dir muted')}</a>`;
}
function libraryPage(ctx) {
  if (ctx.state === 'empty') return emptyView('library');
  if (!data.section('docs')) return notMeasured('library', 'docs');
  const q = ctx.query, tab = q.tab === 'images' ? 'images' : 'docs';
  const all = docs(), images = (data.section('media') || {}).images || [];
  const ordered = all.filter(d => d.order != null).sort((a, b) => a.order - b.order);
  let body;
  if (tab === 'images') {
    const list = q.q ? images.filter(im => matches([im.path, L(im.title || ''), im.kind, im.route || ''].join(' '), q.q)) : images;
    const pg = page(list, imageRow);
    body = `<div class="listhead">${count(pg.shown, list.length)}</div>${list.length ? `<ul class="panel rows un-imgs">${pg.html}</ul>${pg.more}` : `<div class="panel empty"><p class="empty__title">${t('un.lib.none')}</p></div>`}`;
  } else if (q.q) {
    const m = s => matches(s, q.q);
    const hits = [];
    all.forEach(d => { if (m(`${titleOf(d)} ${d.title} ${d.path}`)) hits.push([d]); else { const h = (d.headings || []).find(x => m(x.text)); if (h) hits.push([d, h.text]); } });
    const pg = page(hits, x => docRow(x[0], x[1]));
    body = `<div class="listhead">${count(pg.shown, hits.length)}</div>${hits.length ? `<div class="panel rows">${pg.html}</div>${pg.more}` : `<div class="panel empty"><p class="empty__title">${t('un.lib.none')}</p><a class="btn btn--secondary" href="${href('/understand/library')}">${t('pb.clear')}</a></div>`}`;
  } else {
    const groups = [...new Set(all.map(d => d.group))].sort((a, b) => ((ORDER.indexOf(a) + 1 || 99) - (ORDER.indexOf(b) + 1 || 99)) || a.localeCompare(b));
    body = `${ordered.length ? `<section aria-labelledby="ro-h"><div class="section-head"><h2 id="ro-h">${t('un.lib.first')}</h2></div>
        <ol class="panel rows">${ordered.map(d => `<li><a class="row" href="${docLink(d.path)}"><span class="un-num num">${num(d.order)}</span><span class="row__main"><span class="row__title">${rich(titleOf(d))}</span><span class="row__meta" style="display:block">${esc(size(d))}</span></span>${icon('chev', 'icon--sm icon--dir muted')}</a></li>`).join('')}</ol></section>` : ''}
      <section class="section" aria-labelledby="bp-h"><div class="section-head"><h2 id="bp-h">${t('un.lib.bypurpose')}</h2></div><div class="panel">${groups.map(g => {
        const list = all.filter(d => d.group === g);
        return fold(esc(groupWord(g)), esc(tn('un.pl.doc', list.length)), `<div class="rows" style="margin-inline:-16px">${list.slice(0, 100).map(d => docRow(d)).join('')}</div>${list.length > 100 ? `<p class="small muted" style="margin-top:8px">${esc(t('un.lib.groupmore.v', { n: num(list.length - 100) }))}</p>` : ''}`);
      }).join('')}</div></section>`;
  }
  return `<div class="page page--wide">
    ${tabs('library')}
    <h1 class="lede">${esc(t('un.lib.lede', { n: tn('un.pl.doc', all.length), k: num(ordered.length) }))}</h1>
    <p class="guide">${t('un.lib.guide')}</p>
    <div class="ptools">${seg('tab', [['docs', t('un.lib.docs'), all.length], ['images', t('un.lib.images'), images.length]], tab, t('un.v.library'), { dflt: 'docs', cls: 'un-seg2' })}${search(q.q, t(tab === 'images' ? 'un.lib.search.img' : 'un.lib.search'))}</div>
    <div class="un-body">${body}</div>
  </div>`;
}
screen({ id: 'S-40', path: '/understand/library', place: 'understand', needs: NEEDS, title: () => t('un.v.library'), render: libraryPage, loading: () => loading(t('un.lib.loading')) });

/* ---------- S-41 one document ---------- */
function docPage(ctx) {
  if (!data.section('docs')) return notMeasured('library', 'docs');
  const d = docs().find(x => x.path === ctx.params.doc || x.id === ctx.params.doc);
  if (!d) return notFound(ctx.params.doc, '/understand/library', t('un.v.library'));
  const it = item(d.id);
  const order = docs().filter(x => x.order != null).sort((a, b) => a.order - b.order);
  const k = order.findIndex(x => x.path === d.path);
  const prev = k > 0 ? order[k - 1] : null, next = k >= 0 && k < order.length - 1 ? order[k + 1] : null;
  let body = '', toc = '', lang = '';
  if (it === null) body = `<div class="un-doc__body" aria-busy="true"><p class="small muted">${t('un.doc.reading')}</p></div>`;
  else if (it === false) body = `<div class="un-doc__body">${nm(t('un.doc.unread'), t('un.doc.unread.why'))}</div>`;
  else {
    const ctx = { path: d.path, docs: new Set(docs().map(x => x.path)), cards: new Set(model.problems().map(p => p.id)), diagram: (src, n) => mermaidBlock(src, ctx, n) };
    const drawn = markdown.render(textOf(it), ctx);
    body = `<div class="un-doc__body">${drawn.html}${it.truncated ? `<p class="small caution-ic">${t('un.doc.truncated')}</p>` : ''}</div>`;
    const heads = drawn.headings.filter(h => h.depth <= 3);
    toc = heads.length ? `<aside class="un-doc__toc"><details class="un-tocfold" open><summary class="block-title">${t('un.doc.contents')}</summary><nav class="un-toc" aria-label="${esc(t('un.doc.contents'))}"><ol>${heads.map(h => `<li class="un-toc__h${Math.min(h.depth + 1, 3)}"><a href="#" data-act="un-toc" data-target="${h.id}">${esc(h.text)}</a></li>`).join('')}</ol></nav></details></aside>` : '';
    lang = it.texts && !it.texts[prefs.lang] ? `<p class="small ink-2">${t('un.doc.onlyone')}</p>` : '';
  }
  return `<div class="page page--wide un-docpage">
    ${back('/understand/library', t('un.v.library'))}
    <article class="un-doc" aria-labelledby="doc-h">
      <header class="un-doc__head">
        <h1 class="lede un-lede-sm" id="doc-h">${rich(titleOf(d))}</h1>
        <p class="guide">${t('un.doc.guide')}</p>
        <p class="small muted">${code(d.path)}${t('list.sep')}${esc(size(d))}</p>
        ${lang}
      </header>
      <div class="un-doc__grid">
        ${toc}
        <div class="un-doc__main">${body}
          <nav class="un-doc__pn" aria-label="${esc(t('un.doc.order'))}">
            ${prev ? `<a class="row panel" href="${docLink(prev.path)}">${icon('back', 'icon--dir muted')}<span class="row__main"><span class="small muted">${t('un.doc.prev')}</span><span class="row__title" style="display:block">${rich(titleOf(prev))}</span></span></a>` : '<span></span>'}
            ${next ? `<a class="row panel" href="${docLink(next.path)}"><span class="row__main"><span class="small muted">${t('un.doc.next')}</span><span class="row__title" style="display:block">${rich(titleOf(next))}</span></span>${icon('chev', 'icon--dir muted')}</a>` : ''}
          </nav>
        </div>
      </div>
    </article>
  </div>`;
}
/** Opens the document at the heading the search found (?at=). */
function atHeading(main, ctx) {
  if (!ctx.query.at) return;
  const want = normalize.normalize(ctx.query.at);
  const h = Array.from(main.querySelectorAll('.un-doc__body h2, .un-doc__body h3, .un-doc__body h4')).find(x => normalize.normalize(x.textContent) === want);
  if (h) setTimeout(() => h.scrollIntoView({ block: 'start' }), 0);
}
screen({ id: 'S-41', path: '/understand/library/:doc', place: 'understand', needs: NEEDS, title: ctx => { const d = docs().find(x => x.path === ctx.params.doc); return (d ? titleOf(d) : ctx.params.doc) + ' - ' + t('un.v.library'); }, render: docPage, after: atHeading,
  loading: () => loading(t('un.lib.loading')) });
act('un-toc', el => { const h = document.getElementById(el.dataset.target); if (h) { h.setAttribute('tabindex', '-1'); h.scrollIntoView({ block: 'start' }); h.focus({ preventScroll: true }); } });

/* A document's diagram full screen (?sheet=diagram:<n>:<document>), zoom 0.7x to 8x. */
sheet('diagram', {
  kind: 'sheet', full: true,
  needs: ['docs'],
  render(arg) {
    const [n, path] = [arg.split(':')[0], decodeURIComponent(arg.split(':').slice(1).join(':'))];
    const d = docs().find(x => x.path === path);
    const it = d && item(d.id);
    const g = it ? parseFlowchart(mermaidOf(textOf(it), +n) || '') : null;
    return { title: esc(t('un.doc.diagram')), sub: esc(t('un.doc.diagram.sub')),
      body: g ? `<div class="un-mapwrap" data-zoom-root>${zoomBar()}<div class="un-dgbig">${flowchartSVG(g, true)}</div></div>` : `<p class="small muted" aria-busy="${it === null}">${t(it === null ? 'un.doc.reading' : 'un.doc.cannotdraw')}</p>` };
  },
  after: el => zoomable(el),
});

/* One image of the library (LIB-06): its picture, or its diagram drawn, from the library's carried data. */
sheet('img', {
  kind: 'drawer',
  needs: ['media'],
  render(arg) {
    const id = decodeURIComponent(arg);
    const im = ((data.section('media') || {}).images || []).find(x => x.id === id);
    if (!im) return { title: esc(t('pd.notfound', { id })), body: '' };
    const it = offline() ? false : item(id);
    let body;
    if (it === null) body = `<p class="small muted" aria-busy="true">${t('un.pic.loading')}</p>`;
    else if (!it) body = nm(t('un.img.notcarried'), t(offline() ? 'un.pic.offline' : 'un.img.notcarried.why'));
    else if (it.format === 'mermaid') { const g = parseFlowchart(it.source || ''); body = g ? flowchartSVG(g, false) : `<div class="code" style="padding:12px 16px;white-space:pre" tabindex="0">${esc(it.source || '')}</div>`; }
    else if (it.data) body = `<img src="${esc(it.data)}" alt="${esc(L(im.title || im.path))}" style="width:100%;height:auto;border:1px solid var(--line);border-radius:var(--r-sm)">`;
    else body = nm(t('un.img.notcarried'), esc(t('un.img.toobig', { kb: num(Math.round((it.bytes || 0) / 1024)) })));
    return { title: rich(L(im.title || im.path)), sub: `${code(im.path)}`, body: `${body}<p class="small muted">${t('un.img.' + im.kind)}${im.route ? `${t('list.sep')}${code(im.route)}` : ''}</p>` };
  },
});
