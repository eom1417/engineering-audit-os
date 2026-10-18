// S-19 the gap register (PLN-07) and S-20 one gap (PLN-08), on gaps.json: what separates each component from the
// target, the operation that closes it, its cards and how many are closed, their cover, steps, operations and
// decision. "Fix its problems…" picks the gap's open problems and opens the one Fix preview in Problems.
import { t, tn, L, num, esc, icon, code, href, rich, screen, data, model } from 'eaos';
import {
  tabs, seg, prov, search, count, opTag, opOf, facts, prow, fixBtn, enc, loading, notFound, back, matches, notMeasured, empty, openOf, decisionLink,
} from '../understand-kit/kit.js';
import { targetOf } from '../understand-kit/model.js';

const NEEDS = ['gaps', 'cards', 'system', 'operations', 'decisions', 'coverage'];
export const gapsOf = () => (data.section('gaps') || {}).gaps || [];
const SIZE = { rebuild: 4, merge: 3, delete: 3, modify: 2, introduce: 2, retain: 0 };

export function coverTag(c) {
  if (!c) return `<span class="tag tag--nm">${t('un.cover.none')}</span>`;
  return `<span class="tag ${c === 'covered' ? 'tag--ok' : c === 'partial' ? 'tag--state' : 'tag--caution'}">${t('un.cover.' + c)}</span>`;
}
const closes = g => (opOf(g.operation) === 'retain' ? t('un.gap.stays') : g.cards.length ? t('un.gap.closed', { k: num(g.cards_closed), n: num(g.cards.length) }) : t('un.gap.nocard.m'));

export function gapRow(g) {
  return `<a class="row un-gaprow" href="${href('/understand/gaps/' + enc(g.id))}">
    <span class="row__main"><span class="un-gaprow__top">${code(g.component)}${opTag(g.operation)}${g.to ? `<span class="un-to">${icon('chev', 'icon--sm icon--dir muted')}${code(g.to)}</span>` : ''}</span>
      <span class="row__meta" style="display:block">${esc(tn('pl.file', g.files))}${t('list.sep')}${esc(closes(g))}</span></span>
    <span class="row__end">${coverTag(g.cover)}</span>${icon('chev', 'icon--sm icon--dir muted')}</a>`;
}

function gapsPage(ctx) {
  if (ctx.state === 'empty') return empty(t('un.idx.empty'), t('un.idx.empty.guide'));
  if (!data.section('gaps')) return notMeasured('gaps', 'gaps');
  const q = ctx.query, all = gapsOf();
  const op = q.op || 'all', order = q.order || 'size';
  let rows = all.filter(g => op === 'all' || opOf(g.operation) === op);
  if (q.q) rows = rows.filter(g => matches([g.id, g.component, g.to, t('un.op.' + opOf(g.operation)), L(g.reason || ''), L(g.responsibility || '')].join(' '), q.q));
  rows = rows.slice().sort((a, b) => order === 'cards' ? b.cards.length - a.cards.length : order === 'files' ? b.files - a.files
    : (SIZE[opOf(b.operation)] * 1e5 + b.files) - (SIZE[opOf(a.operation)] * 1e5 + a.files));
  const ops = ['rebuild', 'modify', 'merge', 'delete', 'introduce', 'retain'].filter(o => all.some(g => opOf(g.operation) === o));
  const uncovered = all.filter(g => g.cover === 'missing' || g.cover === 'partial').length;
  return `<div class="page page--wide">
    ${tabs('gaps')}
    <h1 class="lede">${esc(t('un.gaps.lede', { n: tn('un.pl.gap', all.length), k: num(uncovered) }))}</h1>
    <p class="guide">${t('un.gaps.guide')}</p>
    ${prov((data.section('gaps') || {}).provenance)}
    <div class="ptools">
      ${search(q.q, t('un.gaps.search'))}
      ${seg('op', [['all', t('un.all'), all.length]].concat(ops.map(o => [o, t('un.op.' + o), all.filter(g => opOf(g.operation) === o).length])), op, t('un.gaps.byop'), { dflt: 'all', cls: 'un-seg-wrap' })}
      <div class="un-orderline"><span class="small muted">${t('un.order')}</span>${seg('order', [['size', t('un.order.size')], ['cards', t('un.order.cards')], ['files', t('un.order.files')]], order, t('un.order'), { dflt: 'size' })}</div>
    </div>
    <div class="listhead">${count(rows.length, all.length)}</div>
    ${rows.length ? `<div class="panel rows">${rows.map(gapRow).join('')}</div>` : `<div class="panel empty"><p class="empty__title">${t('un.gaps.none')}</p><a class="btn btn--secondary" href="${href('/understand/gaps')}">${t('pb.clear')}</a></div>`}
  </div>`;
}
screen({ id: 'S-19', path: '/understand/gaps', place: 'understand', needs: NEEDS, title: () => t('un.v.gaps'), render: gapsPage, loading: () => loading(t('un.gaps.loading')) });

const opsSection = () => (data.section('operations') || {}).operations || [];

function gapPage(ctx) {
  const g = gapsOf().find(x => x.id === ctx.params.id);
  if (!g) return notFound(ctx.params.id, '/understand/gaps', t('un.v.gaps'));
  const tg = g.to ? targetOf(g.to) : null;
  const carried = g.cards.map(id => model.problem(id)).filter(Boolean);
  const open = openOf(g.cards);
  const op = opOf(g.operation);
  const lede = t('un.gap.lede.' + op, { comp: code(g.component), to: g.to ? code(g.to) : '' });
  const closure = op === 'retain' ? t('un.gap.stays.long') : g.cards.length ? t('un.gap.closure', { k: num(g.cards_closed), n: num(g.cards.length) }) : t('un.gap.closure.none');
  const ops = opsSection().filter(o => (g.operations || []).includes(o.id));
  const merged = tg ? (tg.sources || []).filter(s => s !== g.component) : [];
  return `<div class="page">
    ${back('/understand/gaps', t('un.v.gaps'))}
    <div class="un-itemtags">${opTag(g.operation)}${coverTag(g.cover)}${code(g.id)}</div>
    <h1 class="lede un-lede-sm">${lede}</h1>
    <p class="guide">${esc(closure)}</p>
    <div class="actions">${fixBtn(g.cards, g.component, t('un.gap.fix'))}
      <a class="btn btn--quiet" href="${href('/understand/components', { mode: 'change', focus: g.component })}">${icon('map', 'icon--sm')}${t('un.gap.map')}</a>
      <p class="actions__note">${t(open.length ? 'un.gap.fix.note' : g.cards.length ? 'un.gap.fix.noopen' : 'un.gap.fix.nocard')}</p></div>
    ${g.reason ? `<section class="section"><h2 class="h2">${t('un.gap.why')}</h2><p style="margin-top:8px">${rich(L(g.reason))}</p></section>` : ''}
    <section class="section"><div class="section-head"><h2>${t('un.gap.cards')}</h2><span class="small muted">${g.cards.length ? esc(t('un.gap.closed', { k: num(g.cards_closed), n: num(g.cards.length) })) : ''}</span></div>
      ${carried.length ? `<div class="panel rows">${carried.slice(0, 50).map(p => prow(p)).join('')}</div>${carried.length > 50 ? `<p class="small muted" style="margin-top:8px">${esc(t('un.comp.andmore', { n: num(carried.length - 50) }))} <a class="link" href="${href('/problems', { comp: g.component })}">${t('un.comp.open')}</a></p>` : ''}`
        : `<p class="small muted">${t(op === 'retain' ? 'un.gap.stays.long' : 'un.gap.nocard.long')}</p>`}</section>
    <section class="section"><h2 class="h2" style="margin-bottom:12px">${t('un.gap.props')}</h2>
      <div class="panel panel__pad">${facts([
        [t('un.gap.becomes'), g.to ? `${code(g.to)}${tg && !(tg.sources || []).length ? ` <span class="tag tag--state">${t('un.op.introduce')}</span>` : ''}` : t('un.gap.removed')],
        g.responsibility || (tg && tg.responsibility) ? [t('un.gap.resp'), rich(L(g.responsibility || tg.responsibility))] : null,
        [t('un.gap.files'), esc(tn('pl.file', g.files))],
        [t('un.gap.cover'), coverTag(g.cover)],
        merged.length ? [t('un.gap.merged'), merged.map(code).join(' ')] : null,
        [t('un.gap.ops'), ops.length ? ops.map(o => `<a class="link" href="${href('/understand/operations', { sheet: 'op:' + o.order })}">#${num(o.order)}</a>`).join(' ') : `<span class="muted">${t('un.none')}</span>`],
        [t('un.gap.steps'), (g.steps || []).length ? g.steps.map(s => `<a class="link" href="${href('/problems/plan/' + enc(s))}">${code(s)}</a>`).join(' ') : `<span class="muted">${t('un.gap.nostep')}</span>`],
        [t('un.gap.decision'), decisionLink(g.decision)],
        g.closed && g.closed.value != null ? [t('un.gap.share'), Math.round(g.closed.value * 100) + '%'] : null,
      ])}</div></section>
  </div>`;
}
screen({ id: 'S-20', path: '/understand/gaps/:id', place: 'understand', needs: NEEDS, title: ctx => ctx.params.id + ' - ' + t('un.v.gaps'), render: gapPage, loading: () => loading(t('un.gaps.loading')) });
