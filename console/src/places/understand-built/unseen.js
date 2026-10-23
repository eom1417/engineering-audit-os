// S-32 what the user sees against what runs unseen (SYS-11), on hidden.json: the screen areas on one side, the eight
// groups of unseen work on the other (jobs and triggers, routes that are not pages, server routes, writes, outside
// services, configuration, build and deploy, dead code), joined by what each area sets in motion where the check
// traced it; a group opens its items, "only what has no screen in front" narrows them.
import { t, tn, L, num, esc, icon, code, href, screen, data, parseHash } from 'eaos';
import { tabs, flow, page, loading, notMeasured, emptyView, readout, where, missingRow, enc } from '../understand-kit/kit.js';

const NEEDS = ['hidden', 'coverage'];
const H = () => data.section('hidden');

function unseenPage(ctx) {
  if (ctx.state === 'empty') return emptyView('unseen');
  const h = H();
  if (!h) return notMeasured('unseen', 'hidden');
  const q = ctx.query, r = parseHash();
  const noscreen = q.noscreen === '1';
  const focus = q.group || null, area = q.area || null;
  const groups = h.groups.filter(g => !noscreen || g.no_screen);
  const counts = h.counts || {}, v = k => (counts[k] ? counts[k].value : null);
  const links = h.links || [];
  const left = h.seen.filter(a => !area || a.id === area).map(a => ({ id: a.id, label: areaName(a), n: links.filter(l => l.from === a.id).reduce((s, l) => s + l.count, 0), tip: areaName(a) }));
  const right = groups.filter(g => !focus || g.id === focus).map(g => ({ id: g.id, label: t('un.grp.' + g.id), n: noscreen ? g.no_screen : g.count.value, tip: t('un.grp.' + g.id) }));
  const drawn = links.filter(l => left.some(x => x.id === l.from) && right.some(x => x.id === l.to)).map(l => [l.from, l.to, l.count, null, `${l.from} → ${t('un.grp.' + l.to)}: ${l.count}`]);
  const picture = drawn.length ? flow(left, right, drawn, { leftTitle: t('un.unseen.seen'), rightTitle: t('un.unseen.unseen'), label: t('un.unseen.svg') })
    : `<p class="small muted">${t('un.unseen.nolinks')}</p>`;
  const areaOf = id => h.seen.find(a => a.id === id);
  return `<div class="page page--wide">
    ${tabs('unseen')}
    <h1 class="lede">${esc(t('un.unseen.lede', { n: tn('un.pl.item', v('unseen') || h.items.length), k: num(v('no_screen')) }))}</h1>
    <p class="guide">${t('un.unseen.guide')}</p>
    <div class="ptools"><div class="un-tools">
      <a class="btn btn--secondary btn--sm ${noscreen ? 'is-on' : ''}" ${noscreen ? 'aria-current="true"' : ''} href="${href(r.path, Object.assign({}, q, { noscreen: noscreen ? null : '1' }))}">${icon('screen', 'icon--sm')}${t('un.unseen.only')}</a>
      ${area && areaOf(area) ? `<a class="fchip" href="${href(r.path, Object.assign({}, q, { area: null }))}">${esc(areaName(areaOf(area)))}${icon('x')}</a>` : ''}</div></div>
    ${picture}
    ${groupItems(h, q, r)}
    <div class="un-twocol section">
      <section aria-labelledby="ug-h"><div class="section-head"><h2 id="ug-h">${t('un.unseen.unseen')}</h2><span class="small muted">${esc(tn('un.pl.group', groups.length))}</span></div><div class="panel rows">${groups.map(g => groupRow(g, q, r)).join('')}</div></section>
      <section aria-labelledby="us-h"><div class="section-head"><h2 id="us-h">${t('un.unseen.seen')}</h2><span class="small muted">${esc(tn('un.pl.area', h.seen.length))}</span></div>
        <div class="panel rows">${h.seen.map(a => areaRow(a, q, r)).join('')}</div></section>
    </div>
    ${(h.missing || []).map(missingRow).join('')}
  </div>`;
}

const areaName = a => (a.name === '/' ? t('un.unseen.home') : a.name);

// One screen area: its screens and dialogs; it narrows the picture to itself, or back to every area when open
const areaRow = (a, q, r) => `<a class="row ${a.id === q.area ? 'is-open' : ''}" href="${href(r.path, Object.assign({}, q, { area: a.id === q.area ? null : a.id }))}"><span class="row__main"><span class="row__title">${esc(areaName(a))}</span><span class="row__meta" style="display:block">${esc(tn('un.pl.screen', a.screens.length))}${a.dialog_count ? `${t('list.sep')}${esc(tn('un.pl.dialog', a.dialog_count))}` : ''}</span></span>
  ${icon('chev', 'icon--sm icon--dir muted')}</a>`;

// One group of unseen work: what it is, how much, how much has no screen in front; it opens its items, or closes them
const groupRow = (g, q, r) => `<a class="row ${g.id === q.group ? 'is-open' : ''}" href="${href(r.path, Object.assign({}, q, { group: g.id === q.group ? null : g.id, n: null }))}">
  <span class="row__main"><span class="row__title">${t('un.grp.' + g.id)}</span><span class="row__meta" style="display:block">${t('un.grp.' + g.id + '.what')}</span></span>
  <span class="row__end">${g.no_screen ? `<span class="tag tag--caution">${esc(t('un.unseen.noscreen', { n: num(g.no_screen) }))}</span>` : ''}<b class="num">${num(g.count.value)}</b></span>${icon('chev', 'icon--sm icon--dir muted')}</a>`;

// One unseen item: its kind, name, where it is, and the card about it
const itemRow = it => `<li class="row" style="align-items:flex-start"><span class="tag tag--state">${esc(it.kind)}</span><span class="row__main"><span class="row__title">${code(it.name)}</span>
  <span class="row__meta" style="display:block">${it.file ? code(where(it.file, it.line)) : ''}${it.detail ? `${t('list.sep')}${esc(L(it.detail))}` : ''}${it.no_screen ? `${t('list.sep')}<span class="caution-ic">${t('un.unseen.noscreen1')}</span>` : ''}${it.component ? `${t('list.sep')}<a class="link" href="${href('/understand/components/' + enc(it.component))}">${code(it.component)}</a>` : ''}</span></span>
  ${it.card ? `<a class="link small" href="${href('/problems/' + enc(it.card))}">${code(it.card)}</a>` : ''}</li>`;

// The items of the open group (q.group), narrowed to those with no screen in front and to the chosen area; '' when none is open
function groupItems(h, q, r) {
  const focus = q.group, noscreen = q.noscreen === '1', area = q.area || null;
  if (!focus) return '';
  const items = h.items.filter(it => it.group === focus && (!noscreen || it.no_screen) && (!area || (it.areas || []).includes(area)));
  const pg = page(items, itemRow);
  return `<section class="section" aria-labelledby="gi-h"><div class="section-head"><h2 id="gi-h">${t('un.grp.' + focus)}</h2><a class="link" href="${href(r.path, Object.assign({}, q, { group: null, n: null }))}">${t('un.unseen.allgroups')}</a></div>
    ${items.length ? `<ul class="panel rows">${pg.html}</ul>${pg.more}` : `<p class="small muted">${t('un.unseen.noitems')}</p>`}</section>`;
}
screen({ id: 'S-32', path: '/understand/unseen', place: 'understand', needs: NEEDS, title: () => t('un.v.unseen'), render: unseenPage, after: readout, loading: () => loading(t('un.unseen.loading')) });
