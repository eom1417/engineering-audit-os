// S-39 the user's journeys (SYS-12), on journeys.json: every screen on EAOS's grid by clicks from the start, the links
// between screens with the file and line of each, the main tasks as paths, and the flags (broken link, no way in,
// dead end, duplicate). A task lights its path; a screen focused keeps its links in and out. The list by depth is the
// map's twin.
import { t, tn, L, num, esc, icon, code, href, screen, data, parseHash } from 'eaos';
import { tabs, fold, facts, enc, loading, notMeasured, emptyView, readout, q as query, where, missingRow } from '../understand-kit/kit.js';

const NEEDS = ['journeys', 'coverage'];
const J = () => data.section('journeys');
const scrLink = id => href('/understand/screens/' + enc(id));
const depthWord = d => (d == null || d < 0 ? t('un.flag.no_way_in') : d === 0 ? t('un.depth.start') : tn('un.depth.n', d));
const FLAGS = { broken: 'broken', no_way_in: 'no_way_in', dead_ends: 'dead_end', duplicates: 'duplicate', hidden_screens: 'hidden' };
const focusLink = (id, q, r) => `<a class="link" href="${href(r.path, Object.assign({}, q, { focus: id }))}">${code(id)}</a>`;

function mapSVG(j, task, focus) {
  const g = j.grid;
  const pages = j.screens.filter(s => s.x != null);
  const steps = task ? task.path : [];
  const lit = new Set(steps.slice(1).map((id, i) => steps[i] + '>' + id));
  const near = focus ? new Set(j.edges.filter(e => e.from === focus || e.to === focus).flatMap(e => [e.from, e.to])) : null;
  const links = j.edges.map(e => {
    const on = lit.has(e.from + '>' + e.to) || (focus && (e.from === focus || e.to === focus));
    return `<path class="un-j__link ${on ? 'is-on' : ''} ${(task || focus) && !on ? 'is-off' : ''}" d="${e.d}"><title>${esc(`${e.from} → ${e.to}: ${tn('un.pl.site', e.count)}`)}</title></path>`;
  }).join('');
  const boxes = pages.map(s => {
    const k = steps.indexOf(s.id);
    const flags = s.flags || [];
    const off = (task && k < 0) || (near && !near.has(s.id) && s.id !== focus);
    const tip = `${s.title} ${s.route}${flags.length ? ' - ' + flags.map(f => t('un.flag.' + f)).join(', ') : ''}`;
    const label = s.title.replace(/Page$/, '');
    return `<a href="${href('/understand/journeys', Object.assign({}, query(), { focus: s.id, task: null }))}" class="un-j__node ${k >= 0 ? 'is-lit' : ''} ${focus === s.id ? 'is-focus' : ''} ${flags.length ? 'has-flag' : ''} ${off ? 'is-off' : ''}" data-tip="${esc(tip)}" aria-label="${esc(tip)}">
      <rect x="${s.x}" y="${s.y}" width="${g.box_w}" height="${g.box_h}" rx="8"/><text x="${s.x + 10}" y="${s.y + 24}">${esc(label.length > 20 ? label.slice(0, 19) + '…' : label)}</text>
      <text x="${s.x + 10}" y="${s.y + 44}" class="un-j__route">${esc(s.route.length > 22 ? s.route.slice(0, 21) + '…' : s.route)}</text>
      ${k >= 0 ? `<circle cx="${s.x + g.box_w}" cy="${s.y}" r="11" class="un-j__step"/><text x="${s.x + g.box_w}" y="${s.y + 4}" class="un-j__stepn">${k + 1}</text>` : ''}
      ${flags.length && k < 0 ? `<circle cx="${s.x + g.box_w - 12}" cy="${s.y + 12}" r="4" class="un-j__flag"/>` : ''}<title>${esc(tip)}</title></a>`;
  }).join('');
  return `<div class="panel un-jmap only-desk" data-readout-root><svg viewBox="0 0 ${g.width} ${g.height}" role="group" aria-label="${esc(t('un.j.svg'))}">${links}${boxes}</svg>
    <p class="small muted un-readout" data-readout aria-live="polite">${t('un.map.hint')}</p></div>`;
}

function journeysPage(ctx) {
  if (ctx.state === 'empty') return emptyView('journeys');
  const j = J();
  if (!j) return notMeasured('journeys', 'journeys');
  const q = ctx.query, r = parseHash();
  const task = (j.tasks || []).find(x => x.id === q.task) || null;
  const focus = q.focus || null;
  const c = j.counts || {}, v = k => (c[k] ? c[k].value : null);
  const pages = j.screens.filter(s => s.kind === 'page');
  const taskChips = taskNav(j, task, q, r);
  const taskSteps = task ? taskPath(j, task) : '';
  const focusPart = focusSection(j, focus, q, r);
  const groups = byDepth(pages, focus);
  const flagRow = Object.keys(FLAGS).map(k => `<span class="un-diff"><b class="num">${num(v(k))}</b><span>${t('un.flag.' + FLAGS[k])}</span></span>`).join('');
  return `<div class="page page--wide">
    ${tabs('journeys')}
    <h1 class="lede">${esc(t('un.j.lede', { n: tn('un.pl.screen', v('screens') || pages.length), k: num(v('no_way_in')), b: num(v('broken')) }))}</h1>
    <p class="guide">${t('un.j.guide')}</p>
    <div style="margin-top:20px">${taskChips}</div>
    <div class="un-diffs un-diffs--5" role="list" style="margin-top:20px">${flagRow}</div>
    <div class="section" style="margin-top:20px">${mapSVG(j, task, focus)}</div>
    ${focusPart}
    ${taskSteps}
    <section class="section only-phone-list"><div class="section-head"><h2>${t('un.j.bydepth')}</h2></div><div class="panel">${groups}</div></section>
    <div class="panel section">${fold(t('un.j.counts'), esc(t('un.j.counts.sum', { l: num(v('links')), s: num(v('link_sites')) })), facts([[t('un.j.c.screens'), num(v('screens'))], [t('un.j.c.links'), num(v('links'))], [t('un.j.c.sites'), num(v('link_sites'))], [t('un.j.c.tasks'), num(v('tasks'))], [t('un.flag.broken'), num(v('broken'))], [t('un.flag.hidden'), num(v('hidden_screens'))]]))}
      ${(j.broken || []).length ? fold(t('un.j.broken'), esc(tn('un.pl.link', j.broken.length)), `<ul class="rows">${j.broken.map(b => `<li class="row small" style="padding-inline:0">${code(b.target)}<span class="row__main muted">${esc(where(b.file, b.line))}</span></li>`).join('')}</ul>`) : ''}</div>
    ${(j.missing || []).map(missingRow).join('')}
  </div>`;
}

// The main tasks as chips: one lights its path on the map, "no task" none
function taskNav(j, task, q, r) {
  if (!(j.tasks || []).length) return `<p class="small muted">${t('un.j.notasks')}</p>`;
  return `<nav class="un-chips" aria-label="${esc(t('un.j.tasks'))}"><a href="${href(r.path, Object.assign({}, q, { task: null }))}" ${!task ? 'aria-current="true"' : ''}>${t('un.j.notask')}</a>${j.tasks.map(x => `<a href="${href(r.path, Object.assign({}, q, { task: x.id, focus: null }))}" ${task === x ? 'aria-current="true"' : ''}>${esc(L(x.name))}</a>`).join('')}</nav>`;
}

// A task's screens in order, and whether it ends nowhere
function taskPath(j, task) {
  return `<section class="section" aria-labelledby="ts-h"><h2 class="h2" id="ts-h" style="margin-bottom:8px">${esc(L(task.name))}</h2><ol class="un-chain">${task.path.map((id, k) => {
    const s = j.screens.find(x => x.id === id);
    return `<li class="un-chain__step"><a class="un-chain__a" href="${scrLink(id)}"><span class="un-chain__n num">${k + 1}</span><span class="row__main"><span class="un-chain__label">${esc(s ? s.title : id)}</span><span class="small muted" style="display:block">${code(id)}</span></span></a></li>`;
  }).join('')}</ol>${task.dead ? `<p class="small caution-ic">${t('un.j.task.dead')}</p>` : ''}</section>`;
}

// The focused screen: its depth, the screens that lead to it and those it leads to, and its file; '' when none is focused
function focusSection(j, focus, q, r) {
  const focused = focus && j.screens.find(s => s.id === focus);
  if (!focused) return '';
  return `<section class="section panel panel__pad" aria-labelledby="jf-h"><h2 class="h2" id="jf-h">${esc(focused.title)} ${code(focused.route)}</h2>
    ${facts([
      [t('un.scr.depth'), esc(depthWord(focused.depth))],
      [t('un.j.in'), j.edges.filter(e => e.to === focus).map(e => focusLink(e.from, q, r)).join(' ') || t('un.none')],
      [t('un.j.out'), j.edges.filter(e => e.from === focus).map(e => focusLink(e.to, q, r)).join(' ') || t('un.none')],
      [t('un.fn.where'), focused.file ? code(focused.file) : '—'],
    ])}<div class="actions" style="margin-top:8px"><a class="btn btn--secondary btn--sm" href="${scrLink(focus)}">${t('un.j.open')}</a><a class="link" href="${href(r.path, Object.assign({}, q, { focus: null }))}">${t('flt.clear')}</a></div></section>`;
}

// The pages by their depth in clicks from the start, those with no way in last: the map's twin on a phone
const depthOf = s => (s.depth == null || s.depth < 0 ? -1 : s.depth);
function byDepth(pages, focus) {
  const depths = [...new Set(pages.map(depthOf))].sort((a, b) => (a < 0) - (b < 0) || a - b);
  return depths.map(d => {
    const list = pages.filter(s => depthOf(s) === d);
    return `<div class="group-head"><span>${esc(depthWord(d))}</span><span class="num">${num(list.length)}</span></div>
      <div class="rows">${list.map(s => `<a class="row ${focus === s.id ? 'is-open' : ''}" href="${scrLink(s.id)}"><span class="row__main"><span class="row__title small">${esc(s.title)}</span><span class="row__meta" style="display:block">${code(s.route)}${(s.flags || []).map(fl => `${t('list.sep')}<span class="caution-ic">${t('un.flag.' + fl)}</span>`).join('')}</span></span>${icon('chev', 'icon--sm icon--dir muted')}</a>`).join('')}</div>`;
  }).join('');
}
screen({ id: 'S-39', path: '/understand/journeys', place: 'understand', needs: NEEDS, title: () => t('un.v.journeys'), render: journeysPage, after: readout, loading: () => loading(t('un.j.loading')) });
